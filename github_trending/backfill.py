"""Phase 2 — one-time backfill: load the seed CSV corpus into DuckDB.

Applies the ⑨ audit's cleaning rules:
  - load only 2026-05-17 .. 2026-07-18 (earlier days used a ~1000-star floor)
  - drop 2026-07-06 (corrupted 160 MB file) — excluded from the read entirely
  - dedup duplicate (github_id, snapshot_date) rows (keep the max-stars row)
  - split pipe-delimited `topics` into a list; ignore `watchers` (== stars)
  - runs log: 2026-06-26 / 06-27 = 'partial' (partial scans), 07-06 = 'absent', else 'complete'

Reads the CSV corpus exactly once (into a deduped staging table), then fans out
into `snapshots`, `repos`, and `runs`.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from .db import connect, init_db

DROP_FILE = "output_2026-07-06.csv"  # corrupted; must be excluded from the read
START, END = "2026-05-17", "2026-07-18"


def csv_files(data_dir: Path) -> list[str]:
    """All seed CSVs except the corrupted July-6 file, as forward-slash paths."""
    files = sorted(p for p in data_dir.glob("output*.csv") if p.name != DROP_FILE)
    if not files:
        raise FileNotFoundError(f"no output*.csv found in {data_dir}")
    return [p.as_posix() for p in files]


def _sql_list(files: list[str]) -> str:
    return "[" + ", ".join("'" + f.replace("'", "''") + "'" for f in files) + "]"


def load_backfill(con: duckdb.DuckDBPyConnection, files: list[str]) -> None:
    lst = _sql_list(files)

    # 1) read once → deduped, type-coerced, date-filtered staging table
    con.execute(f"""
        CREATE OR REPLACE TEMP TABLE staging AS
        SELECT * FROM (
            SELECT
                TRY_CAST(github_id AS BIGINT)      AS repo_id,
                TRY_CAST(snapshot_date AS DATE)    AS snapshot_date,
                TRY_CAST(stars AS INTEGER)         AS stars,
                TRY_CAST(forks AS INTEGER)         AS forks,
                TRY_CAST(open_issues AS INTEGER)   AS open_issues,
                full_name, name, language, description, topics, created_at,
                row_number() OVER (
                    PARTITION BY TRY_CAST(github_id AS BIGINT), TRY_CAST(snapshot_date AS DATE)
                    ORDER BY TRY_CAST(stars AS INTEGER) DESC
                ) AS rn
            FROM read_csv({lst}, union_by_name=true, header=true, ignore_errors=true)
        )
        WHERE rn = 1
          AND repo_id IS NOT NULL AND snapshot_date IS NOT NULL AND stars IS NOT NULL
          AND snapshot_date BETWEEN DATE '{START}' AND DATE '{END}';
    """)

    # 2) snapshots (dense fact)
    con.execute("""
        INSERT INTO snapshots (repo_id, snapshot_date, stars, forks, open_issues)
        SELECT repo_id, snapshot_date, stars, forks, open_issues FROM staging;
    """)

    # 3) repos (dimension): latest metadata per repo + first/last seen
    con.execute("""
        INSERT OR REPLACE INTO repos
            (repo_id, full_name, owner, name, primary_language, description,
             topics, created_at, first_seen_date, last_seen_date, is_active)
        WITH ranked AS (
            SELECT *, row_number() OVER (PARTITION BY repo_id ORDER BY snapshot_date DESC) AS mrn
            FROM staging
        ),
        span AS (
            SELECT repo_id, min(snapshot_date) AS fs, max(snapshot_date) AS ls
            FROM staging GROUP BY repo_id
        )
        SELECT r.repo_id, r.full_name, split_part(r.full_name, '/', 1) AS owner,
               COALESCE(r.name, split_part(r.full_name, '/', 2)) AS name,
               r.language, r.description,
               CASE WHEN r.topics IS NULL OR r.topics = '' THEN CAST([] AS VARCHAR[])
                    ELSE string_split(r.topics, '|') END,
               TRY_CAST(r.created_at AS TIMESTAMP), s.fs, s.ls, TRUE
        FROM ranked r JOIN span s USING (repo_id)
        WHERE r.mrn = 1;
    """)

    # 4) runs completeness log — one row per calendar day in the window
    con.execute(f"""
        INSERT OR REPLACE INTO runs (run_date, status, repos_seen)
        SELECT d::DATE,
               CASE WHEN d::DATE IN (DATE '2026-06-26', DATE '2026-06-27') THEN 'partial'
                    WHEN d::DATE = DATE '2026-07-06' THEN 'absent'
                    ELSE 'complete' END,
               (SELECT count(*) FROM snapshots s WHERE s.snapshot_date = d::DATE)
        FROM generate_series(DATE '{START}', DATE '{END}', INTERVAL 1 DAY) t(d);
    """)

    con.execute("DROP TABLE staging;")


def verify(con: duckdb.DuckDBPyConnection) -> dict:
    q = con.execute("""
        SELECT
            (SELECT count(DISTINCT repo_id) FROM snapshots),
            (SELECT count(DISTINCT snapshot_date) FROM snapshots),
            (SELECT min(snapshot_date) FROM snapshots),
            (SELECT max(snapshot_date) FROM snapshots),
            (SELECT count(*) FROM snapshots WHERE snapshot_date = DATE '2026-07-06'),
            (SELECT min(stars) FROM snapshots),
            (SELECT count(*) FROM repos)
    """).fetchone()
    runs = dict(con.execute("SELECT status, count(*) FROM runs GROUP BY status").fetchall())
    return {"distinct_repos": q[0], "distinct_dates": q[1], "min_date": q[2], "max_date": q[3],
            "july6_rows": q[4], "min_stars": q[5], "repos": q[6], "runs": runs}


def main() -> None:
    from .config import load_config
    cfg = load_config()
    con = connect(cfg.db_path)
    init_db(con)
    files = csv_files(cfg.data_dir)
    print(f"loading {len(files)} files from {cfg.data_dir} into {cfg.db_path} ...")
    load_backfill(con, files)
    stats = verify(con)
    for k, v in stats.items():
        print(f"  {k}: {v}")
    con.close()


if __name__ == "__main__":
    main()
