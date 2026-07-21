"""Report where the DuckDB database is and what's in it. Read-only.
Run: uv run python tools/db_status.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

import duckdb

from github_trending.config import load_config

cfg = load_config()
db = cfg.db_path.resolve()
print(f"DB FILE:  {db}")
print(f"exists:   {db.exists()}", end="")
if db.exists():
    print(f"   size: {db.stat().st_size / 1024 / 1024:.1f} MB")
else:
    print("\n(no database yet — run backfill/ingest first)")
    sys.exit(0)

con = duckdb.connect(str(db), read_only=True)

print("\nTABLES (row counts):")
for t in ("repos", "snapshots", "summaries", "runs"):
    n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    print(f"   {t:<11} {n:>10,} rows")

d = con.execute("""
    SELECT count(DISTINCT repo_id), count(DISTINCT snapshot_date),
           min(snapshot_date), max(snapshot_date)
    FROM snapshots
""").fetchone()
print(f"\nSNAPSHOTS: {d[0]:,} distinct repos across {d[1]} days ({d[2]} → {d[3]})")

print("\nMost recent snapshot days (rows each):")
for r in con.execute("""
    SELECT snapshot_date, count(*) AS repos FROM snapshots
    GROUP BY 1 ORDER BY 1 DESC LIMIT 6
""").fetchall():
    print(f"   {r[0]}   {r[1]:>8,} repos")

print("\nRUN LOG (most recent):")
for r in con.execute("""
    SELECT run_date, status, repos_seen FROM runs ORDER BY run_date DESC LIMIT 8
""").fetchall():
    print(f"   {r[0]}   {r[1]:<9} {(r[2] or 0):>8,} repos")

print(f"\nSUMMARIES cached: {con.execute('SELECT count(*) FROM summaries').fetchone()[0]:,}")
con.close()
