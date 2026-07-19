"""Phase 8 — daily orchestration (ticket ⑦).

Runs the whole pipeline once, in order, unattended:
    ingest → summarize (new trending only) → assemble latest.json → publish

Guarantees:
  - publish is LAST and only runs if every prior step succeeded, so a failure
    leaves the live site on yesterday's good data (never a half-computed day);
  - a successful ingest keeps `runs.status='complete'` even if a later step
    fails (the snapshot is valid; only the publish didn't happen);
  - any failure fires a Discord alert (if configured) and re-raises.
"""
from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import assemble, ingest, summarize
from .alerts import notify
from .config import Config, load_config, require
from .db import connect, init_db
from .trending import WINDOWS, compute_trending

log = logging.getLogger("github_trending")


def _setup_logging() -> None:
    Path("logs").mkdir(exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    handlers = [logging.StreamHandler(sys.stdout),
                logging.FileHandler(Path("logs") / f"run-{day}.log", encoding="utf-8")]
    logging.basicConfig(level=logging.INFO, handlers=handlers,
                        format="%(asctime)s %(levelname)s %(message)s")
    sys.stdout.reconfigure(encoding="utf-8")


def _trending_union(con, top_n: int) -> list[dict]:
    seen: dict[int, dict] = {}
    for w in WINDOWS:
        for r in compute_trending(con, w, top_n=top_n):
            seen[r["repo_id"]] = r
    return list(seen.values())


def _publish(as_of: str) -> None:
    """Publish = commit + push latest.json. Cloudflare Pages is connected to this
    GitHub repo (production branch `main`, output dir `site`), so it auto-deploys
    on push. No Wrangler / no direct upload — GitHub is the deploy trigger.
    """
    subprocess.run(["git", "add", "site/data/latest.json"], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        log.info("latest.json unchanged — nothing to publish")
        return
    subprocess.run(["git", "commit", "-m", f"data: trending update {as_of}"], check=True)
    subprocess.run(["git", "push"], check=True)
    log.info("pushed latest.json — Cloudflare Pages will redeploy")


def run_daily(cfg: Config, *, skip_ingest: bool = False, publish: bool = True,
              top_n: int = 50) -> dict:
    con = connect(cfg.db_path)
    init_db(con)
    today = datetime.now(timezone.utc).date()
    try:
        if skip_ingest:
            log.info("skip_ingest=True — using existing snapshots")
        else:
            log.info("Phase 3 — ingest sweep (this takes ~2-3h due to API rate limits)")
            ingest.sweep(con, require(cfg.github_token, "GITHUB_TOKEN"))

        log.info("Phase 5 — summarize new trending repos")
        stats = summarize.run_summaries(
            con,
            require(cfg.github_token, "GITHUB_TOKEN"),
            require(cfg.google_api_key, "GOOGLE_API_KEY"),
            _trending_union(con, top_n),
        )
        log.info("summaries: %s", stats)

        log.info("Phase 6 — assemble latest.json")
        payload = assemble.assemble(con, top_n)
        site_dir = Path("site")
        assemble.write_artifact(payload, site_dir / "data")

        if publish:
            _publish(payload["as_of"])

        log.info("daily run complete for %s (as_of=%s)", today, payload["as_of"])
        return {"ok": True, "as_of": payload["as_of"], "summaries": stats}

    except Exception as exc:  # noqa: BLE001 — top-level guard: log, alert, re-raise
        log.exception("daily run FAILED")
        # Preserve a good ingest: only stamp 'failed' when the snapshot isn't already complete.
        try:
            con.execute("""
                INSERT INTO runs (run_date, status) VALUES (?, 'failed')
                ON CONFLICT (run_date) DO UPDATE SET
                    status = CASE WHEN runs.status = 'complete' THEN 'complete' ELSE 'failed' END
            """, [today])
        except Exception:
            log.exception("could not record failed run")
        if cfg.alert_webhook_url:
            try:
                notify(cfg.alert_webhook_url,
                       f"🔴 github-trending daily run FAILED ({today}): "
                       f"{type(exc).__name__}: {exc}")
            except Exception:
                log.exception("failure alert could not be sent")
        raise
    finally:
        con.close()


def main() -> None:
    _setup_logging()
    ap = argparse.ArgumentParser(description="Run the github-trending daily pipeline.")
    ap.add_argument("--skip-ingest", action="store_true",
                    help="reuse existing snapshots (skip the ~3h sweep)")
    ap.add_argument("--no-publish", action="store_true", help="build the site but don't deploy")
    ap.add_argument("--top-n", type=int, default=50)
    args = ap.parse_args()
    run_daily(load_config(), skip_ingest=args.skip_ingest,
              publish=not args.no_publish, top_n=args.top_n)


if __name__ == "__main__":
    main()
