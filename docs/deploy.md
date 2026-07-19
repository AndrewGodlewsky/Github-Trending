# Deploying & scheduling

Hosting model: **Cloudflare Pages, deployed from GitHub.** Cloudflare serves the
site (fast CDN + easy custom domain); it watches this GitHub repo and redeploys
automatically whenever `main` is pushed. The daily job "publishes" simply by
committing the new `latest.json` and pushing — no Wrangler, no manual upload.

```
 daily job → git push (latest.json) → GitHub → Cloudflare Pages auto-build → live site
```

## 1. Connect Cloudflare Pages to the repo (one time)

1. Create a free Cloudflare account: https://dash.cloudflare.com/sign-up
2. In the dashboard: **Workers & Pages → Create → Pages → Connect to Git**.
3. Authorize GitHub and pick the **`Github-Trending`** repository.
4. Build settings:
   - **Production branch:** `main`
   - **Framework preset:** None
   - **Build command:** *(leave empty — it's a static site, no build)*
   - **Build output directory:** `site`
5. **Save and Deploy.** Cloudflare builds and gives you a URL like
   `https://github-trending-xxx.pages.dev`. Open it — you should see the board
   (it serves the `latest.json` that's committed in the repo).

From now on, every push to `main` triggers a redeploy — including the daily
`data: trending update …` commits the pipeline makes.

## 2. Point your domain at it — `aitrendingskills.com`

Easiest path is to let Cloudflare manage the domain's DNS:

1. In the Cloudflare dashboard: **Add a site → `aitrendingskills.com`** (Free plan).
2. Cloudflare shows you **two nameservers**. Go to wherever you bought the domain
   (the registrar) and replace its nameservers with those two. (DNS propagation
   can take anywhere from minutes to a few hours.)
3. Back in your **Pages project → Custom domains → Set up a custom domain →**
   enter `aitrendingskills.com` (and optionally `www`). Cloudflare adds the DNS
   records and provisions HTTPS automatically.

> If you'd rather keep DNS at your current registrar, you can instead add a `CNAME`
> record pointing `aitrendingskills.com` to your `*.pages.dev` hostname — but
> moving the domain to Cloudflare is simpler and gives automatic HTTPS.

## 3. Schedule the daily run — Windows Task Scheduler

From an **elevated** PowerShell in the repo root:

```powershell
./tools/register-task.ps1            # daily at 3am
./tools/register-task.ps1 -Time 6am  # or pick a time
```

Registered with **catch-up on a missed start** (a sleeping/off laptop runs it on
next wake) and a 6-hour limit (the sweep takes ~2–3h). Test it:

```powershell
Start-ScheduledTask -TaskName github-trending-daily
```

> **Git auth for the unattended push:** the daily job runs `git push`, so your
> git credentials must be cached (Git Credential Manager stores them after your
> first manual push — which is already done). If a scheduled push ever fails auth,
> run one manual `git push` to refresh the stored credential.

## Running it by hand

```bash
uv run python -m github_trending.orchestrate                 # full run (ingest → … → push)
uv run python -m github_trending.orchestrate --skip-ingest   # reuse today's snapshot, rebuild + push
uv run python -m github_trending.orchestrate --no-publish    # build latest.json but don't commit/push
```

## The first full run

The first `orchestrate` run does the full ~2–3h ingest sweep of all ≥500★ repos,
appends today's snapshot after the backfilled history (which ends 2026-07-18),
rebuilds `latest.json`, and pushes it — Cloudflare then redeploys. Watch
`logs/run-YYYY-MM-DD.log`. If anything fails, you get a Discord alert and the live
site keeps the previous day's data.
