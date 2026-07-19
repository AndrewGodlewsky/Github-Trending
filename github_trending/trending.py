"""Phase 4 — trending computation (ticket ④).

For each window (day/week/month), rank repos by percentage star gain, gated by a
minimum absolute gain. Uses DuckDB ASOF JOIN so the baseline is "the latest
snapshot at or before the window boundary" — gap-tolerant by construction. Only
snapshots on `complete` run days are eligible (partial/absent days excluded as
baselines). The day window normalizes to a per-day rate when a gap widens the span.

Thresholds are calibratable starting points — see `calibrate()`.
"""
from __future__ import annotations

import duckdb

# window -> (lag_days, min_abs_gain, min_pct_gain)
WINDOWS: dict[str, tuple[int, int, float]] = {
    "day":   (1, 15, 0.01),
    "week":  (7, 75, 0.05),
    "month": (30, 200, 0.12),
}

FIELDS = ("repo_id", "full_name", "owner", "name", "primary_language", "description",
          "topics", "stars_now", "stars_then", "abs_gain", "pct_gain", "elapsed_days")


def compute_trending(con: duckdb.DuckDBPyConnection, window: str, top_n: int = 50) -> list[dict]:
    lag, min_abs, min_pct = WINDOWS[window]
    rank_key = "pct_gain / GREATEST(elapsed_days, 1)" if window == "day" else "pct_gain"
    sql = f"""
    WITH nowd AS (SELECT max(run_date) AS d FROM runs WHERE status = 'complete'),
         clean AS (
            SELECT s.* FROM snapshots s
            JOIN runs r ON s.snapshot_date = r.run_date AND r.status = 'complete'
         ),
         cur AS (
            SELECT repo_id, stars, (SELECT d FROM nowd) - {lag} AS boundary
            FROM clean WHERE snapshot_date = (SELECT d FROM nowd)
         )
    SELECT * FROM (
        SELECT c.repo_id, rp.full_name, rp.owner, rp.name, rp.primary_language,
               rp.description, rp.topics,
               c.stars AS stars_now, b.stars AS stars_then,
               c.stars - b.stars AS abs_gain,
               (c.stars - b.stars) * 1.0 / b.stars AS pct_gain,
               date_diff('day', b.snapshot_date, (SELECT d FROM nowd)) AS elapsed_days
        FROM cur c
        ASOF LEFT JOIN clean b
            ON c.repo_id = b.repo_id AND c.boundary >= b.snapshot_date
        JOIN repos rp ON rp.repo_id = c.repo_id
        WHERE b.stars IS NOT NULL
    ) t
    WHERE abs_gain >= {min_abs} AND pct_gain >= {min_pct}
    ORDER BY ({rank_key}) DESC, abs_gain DESC, stars_now DESC
    LIMIT {top_n};
    """
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def calibrate(con: duckdb.DuckDBPyConnection, window: str) -> dict:
    """How many repos clear the gate, and the gain distribution — to tune thresholds."""
    lag, min_abs, min_pct = WINDOWS[window]
    sql = f"""
    WITH nowd AS (SELECT max(run_date) AS d FROM runs WHERE status='complete'),
         clean AS (SELECT s.* FROM snapshots s JOIN runs r
                   ON s.snapshot_date=r.run_date AND r.status='complete'),
         cur AS (SELECT repo_id, stars, (SELECT d FROM nowd)-{lag} AS boundary
                 FROM clean WHERE snapshot_date=(SELECT d FROM nowd)),
         deltas AS (
            SELECT c.stars - b.stars AS abs_gain,
                   (c.stars - b.stars)*1.0/b.stars AS pct_gain
            FROM cur c ASOF LEFT JOIN clean b
              ON c.repo_id=b.repo_id AND c.boundary >= b.snapshot_date
            WHERE b.stars IS NOT NULL
         )
    SELECT count(*) FILTER (WHERE abs_gain >= {min_abs} AND pct_gain >= {min_pct}) AS over_gate,
           count(*) AS total,
           round(quantile_cont(pct_gain, 0.99)*100, 1) AS p99_pct,
           round(quantile_cont(pct_gain, 0.999)*100, 1) AS p999_pct,
           max(abs_gain) AS max_abs
    FROM deltas;
    """
    row = con.execute(sql).fetchone()
    return {"window": window, "over_gate": row[0], "total": row[1],
            "p99_pct": row[2], "p999_pct": row[3], "max_abs": row[4]}


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")  # console may default to cp1252 on Windows
    from .config import load_config
    from .db import connect
    con = connect(load_config().db_path)
    for w in WINDOWS:
        c = calibrate(con, w)
        print(f"\n=== {w.upper()}  (gate: ≥{WINDOWS[w][1]}★ & ≥{WINDOWS[w][2]*100:g}%) "
              f"→ {c['over_gate']:,} over gate of {c['total']:,} eligible "
              f"| p99={c['p99_pct']}% p99.9={c['p999_pct']}% maxΔ={c['max_abs']:,} ===")
        for i, r in enumerate(compute_trending(con, w, top_n=10), 1):
            print(f"  {i:2}. {r['full_name']:<38} {r['stars_now']:>7,}★  "
                  f"+{r['abs_gain']:>5,}  +{r['pct_gain']*100:5.1f}%"
                  f"{'  ('+str(r['elapsed_days'])+'d)' if r['elapsed_days']>WINDOWS[w][0] else ''}"
                  f"  [{r['primary_language'] or '—'}]")
    con.close()


if __name__ == "__main__":
    main()
