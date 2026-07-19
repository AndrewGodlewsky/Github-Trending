"""Live smoke test for Phase 5 — summarize the top 3 day-window trending repos,
then re-run to confirm the cache serves them with zero API calls."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from github_trending.config import load_config, require
from github_trending.db import connect
from github_trending.trending import compute_trending
from github_trending.summarize import run_summaries

cfg = load_config()
gh = require(cfg.github_token, "GITHUB_TOKEN")
key = require(cfg.google_api_key, "GOOGLE_API_KEY")
con = connect(cfg.db_path)

repos = compute_trending(con, "day", top_n=3)
print("summarizing:", [r["full_name"] for r in repos])

stats1 = run_summaries(con, gh, key, repos)
print("first run:", stats1)
print()
for r in con.execute("""
    SELECT rp.full_name, m.summary_text
    FROM summaries m JOIN repos rp USING (repo_id)
    WHERE rp.repo_id IN (SELECT repo_id FROM summaries)
    ORDER BY m.generated_at DESC LIMIT 3
""").fetchall():
    print(f"### {r[0]}\n{r[1]}\n")

stats2 = run_summaries(con, gh, key, repos)
print("second run (expect all cached):", stats2)
