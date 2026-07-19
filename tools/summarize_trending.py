"""Summarize the union of the top-N trending repos across all windows (deduped),
so latest.json ships with real summaries. Cache hits are skipped."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from github_trending.config import load_config, require
from github_trending.db import connect
from github_trending.summarize import run_summaries
from github_trending.trending import WINDOWS, compute_trending

TOP_N = int(sys.argv[1]) if len(sys.argv) > 1 else 20

cfg = load_config()
con = connect(cfg.db_path)

seen: dict[int, dict] = {}
for w in WINDOWS:
    for r in compute_trending(con, w, top_n=TOP_N):
        seen[r["repo_id"]] = r
repos = list(seen.values())

print(f"summarizing {len(repos)} distinct trending repos (top {TOP_N}/window) ...")
stats = run_summaries(
    con,
    require(cfg.github_token, "GITHUB_TOKEN"),
    require(cfg.google_api_key, "GOOGLE_API_KEY"),
    repos,
)
print("done:", stats)
