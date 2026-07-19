"""Smoke check (framework-free): the schema initializes and the four tables
exist, with the ⑧ enrichment columns present on `snapshots`.

Run: `python tests/test_schema.py`  (exits non-zero on failure)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from github_trending.db import TABLES, connect, init_db


def test_schema() -> None:
    con = connect(":memory:")
    init_db(con)

    names = {r[0] for r in con.execute(
        "SELECT table_name FROM information_schema.tables"
    ).fetchall()}
    for t in TABLES:
        assert t in names, f"missing table: {t}"

    snap_cols = {r[1] for r in con.execute("PRAGMA table_info('snapshots')").fetchall()}
    for c in ("repo_id", "snapshot_date", "stars", "forks", "open_issues"):
        assert c in snap_cols, f"snapshots missing column: {c}"

    # init is idempotent
    init_db(con)

    print("OK: 4 tables created; snapshots enriched with forks/open_issues; init idempotent")


if __name__ == "__main__":
    test_schema()
