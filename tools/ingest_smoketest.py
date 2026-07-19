"""Live smoke test for the ingest sweep — a bounded high-star slice into an
in-memory DB (never touches the real DB, never writes a `runs` row).
Verifies auth + adaptive banding + paging + upsert against the real API."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from github_trending.config import load_config, require
from github_trending.db import connect, init_db
from github_trending.ingest import sweep

cfg = load_config()
con = connect(":memory:")
init_db(con)

stats = sweep(con, require(cfg.github_token, "GITHUB_TOKEN"),
              min_stars=10_000, max_bands=2, mark_run=False)
print("sweep stats:", stats)
print("snapshot rows:", con.execute("SELECT count(*) FROM snapshots").fetchone()[0])
print("distinct repos:", con.execute("SELECT count(DISTINCT repo_id) FROM repos").fetchone()[0])
print("star range:", con.execute("SELECT min(stars), max(stars) FROM snapshots").fetchone())
print("top sample (public data):")
for r in con.execute("""
    SELECT r.full_name, s.stars, r.primary_language
    FROM snapshots s JOIN repos r USING (repo_id)
    ORDER BY s.stars DESC LIMIT 6
""").fetchall():
    print("   ", r)
