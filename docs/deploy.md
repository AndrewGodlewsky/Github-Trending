# Deploying & scheduling

Two one-time setup steps, then the pipeline runs itself daily.

## 1. Publish target — Cloudflare Pages

The daily job uploads the built `site/` folder to Cloudflare Pages via `wrangler`.

1. Create a free Cloudflare account: https://dash.cloudflare.com/sign-up
2. Install Node.js (https://nodejs.org) if you don't have it, then Wrangler:
   ```bash
   npm install -g wrangler
   ```
3. Log in (opens a browser):
   ```bash
   wrangler login
   ```
4. Create the Pages project once (Direct Upload):
   ```bash
   wrangler pages project create github-trending --production-branch main
   ```
5. Put the project name in `.env`:
   ```
   CLOUDFLARE_PAGES_PROJECT=github-trending
   ```
6. First manual deploy to confirm it works (build the site first if needed):
   ```bash
   uv run python -m github_trending.assemble
   wrangler pages deploy site --project-name github-trending
   ```
   Cloudflare prints your live URL (`https://github-trending.pages.dev`). A custom domain can be added later in the Pages dashboard.

> Until `CLOUDFLARE_PAGES_PROJECT` is set, the daily run still builds `site/data/latest.json` locally — it just skips the upload.

## 2. Schedule the daily run — Windows Task Scheduler

From an **elevated** PowerShell in the repo root:

```powershell
./tools/register-task.ps1            # daily at 3am
./tools/register-task.ps1 -Time 6am  # or pick a time
```

This registers `github-trending-daily` with **catch-up on a missed start** (a sleeping/off laptop runs it on next wake — a late snapshot, not a gap) and a 6-hour limit (the sweep takes ~2–3h).

Test it immediately:
```powershell
Start-ScheduledTask -TaskName github-trending-daily
```

## Running it by hand

```bash
uv run python -m github_trending.orchestrate                 # full run (ingest → … → publish)
uv run python -m github_trending.orchestrate --skip-ingest   # reuse today's snapshot, just rebuild + publish
uv run python -m github_trending.orchestrate --no-publish    # build the site but don't deploy
```

## The first full run

The very first `orchestrate` run (or scheduled fire) does the full ~2–3h ingest sweep of all ≥500★ repos, appending today's snapshot after the backfilled history (which ends 2026-07-18). Watch `logs/run-YYYY-MM-DD.log`. If anything fails, you'll get a Discord alert and the live site stays on the previous day's data.
