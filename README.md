# github-trending · "Starling"

A daily pipeline **and** static website that surfaces **trending GitHub repositories**. Every day it snapshots every public repo with ≥ 500 stars, works out which are gaining stars fastest (day / week / month), writes a plain-language AI summary of each riser, and publishes the result to a static site.

Everything heavy — a ~120,000-repo database and weeks of history — stays on your machine. Only a tiny result (~140 KB of JSON) reaches the web. The public site is just static files reading that one file.

> **New here? Start with the visual guide:** open [`docs/architecture/index.html`](docs/architecture/index.html) in a browser — a plain-English, diagrammed walkthrough of the whole system.

---

## Contents

- [What it does](#what-it-does)
- [How it works — the daily loop](#how-it-works--the-daily-loop)
- [The data model](#the-data-model)
- [Project structure](#project-structure) ← file tree
- [Documentation index](#documentation-index) ← find any doc
- [Running it](#running-it)
- [Configuration](#configuration)
- [Status & what's left](#status--whats-left)
- [Design rationale](#design-rationale)

---

## What it does

1. **Collects** a daily star-count snapshot of every repo with ≥ 500 stars (~120k repos).
2. **Stores** those snapshots locally in DuckDB, building a time series.
3. **Ranks** repos by percentage star growth (gated by a minimum absolute gain) over three windows — day, week, month.
4. **Summarizes** each trending repo with Google Gemini — one honest, jargon-light paragraph from its README.
5. **Publishes** the top 50 per window, with summaries and sparklines, to a static website on Cloudflare Pages.

It runs unattended once a day via Windows Task Scheduler, and pings Discord if a run fails.

## How it works — the daily loop

Six stages run in order each night; each hands its output to the next. Every stage is one small module in `github_trending/`.

```
 GitHub Search API ──► ingest.py (bucketed sweep) ─┐
 ../data/*.csv (seed) ─► backfill.py (one-time) ────┴─► DuckDB
                                                        │
                                          trending.py (ASOF-join ranking)
                                                        │
                                    summarize.py (Gemini, new risers only, cached)
                                                        │
                                        assemble.py ──► site/data/latest.json
                                                        │
                          orchestrate.py ──► wrangler ──► Cloudflare Pages (site/)
```

| Stage | Module | What it does |
|-------|--------|--------------|
| Ingest | `ingest.py` | Crawls GitHub in adaptive `stars:LOW..HIGH` bands (to beat the 1,000-result / 30-req-min limits). ~2–3 h. |
| Backfill | `backfill.py` | One-time load of your existing CSV history so trends work from day one. |
| Rank | `trending.py` | Uses DuckDB **ASOF joins** — "compare to the latest snapshot at/before N days ago" — so missing days don't break the math. |
| Summarize | `summarize.py` | Gemini `flash-lite` writes a paragraph per trending repo; cached by README version, so re-runs are free. |
| Assemble | `assemble.py` | Writes `latest.json` — the contract the website reads (3 windows × 50 repos + summaries + sparklines). |
| Publish | `orchestrate.py` | Sequences all of the above, then uploads `site/` via `wrangler`. Publish is **last & gated on success** — a failed run keeps yesterday's site and alerts Discord. |

## The data model

One DuckDB file (`github_trending.duckdb`, gitignored), four tables:

| Table | Holds | Think of it as… |
|-------|-------|-----------------|
| `repos` | One row per repo: name, owner, language, topics, description | The address book |
| `snapshots` | One row per repo **per day**: stars, forks, open issues | The diary (the time series) |
| `summaries` | The Gemini paragraph + the README version it came from | The cache |
| `runs` | One row per day the pipeline ran + its status | The logbook (which days to trust) |

Snapshots are stored **densely** (every repo, every day) so a missed run is distinguishable from "stars didn't change."

## Project structure

```
Github-Trending/
├── github_trending/           # ── the pipeline (one module per stage) ──
│   ├── __init__.py
│   ├── config.py              # loads settings + secrets from .env
│   ├── db.py                  # DuckDB connection + the 4-table schema
│   ├── backfill.py            # Phase 2 · one-time load of the seed CSV history
│   ├── ingest.py              # Phase 3 · daily bucketed GitHub Search sweep
│   ├── trending.py            # Phase 4 · the ASOF-join trending algorithm  ← thresholds live here
│   ├── summarize.py           # Phase 5 · Gemini summaries + cache
│   ├── assemble.py            # Phase 6 · builds latest.json
│   ├── alerts.py              # Discord failure alerts
│   └── orchestrate.py         # Phase 8 · the daily runner (sequences all stages)
│
├── site/                      # ── the website (Phase 7) ──
│   ├── index.html             # static page; fetches data/latest.json
│   └── data/                  # generated (gitignored): latest.json + archive/YYYY-MM-DD.json
│
├── tools/                     # ── one-off scripts & helpers ──
│   ├── preflight.py           # check tokens are present (prints yes/no, never values)
│   ├── register-task.ps1      # register the daily Windows scheduled task
│   ├── test_alert.py          # send a test message to your Discord webhook
│   ├── summarize_trending.py  # summarize the current trending set on demand
│   ├── ingest_smoketest.py    # live test: a small ingest slice
│   └── summarize_smoketest.py # live test: summarize a few repos
│
├── tests/
│   └── test_schema.py         # schema smoke check
│
├── docs/                      # ── documentation (see index below) ──
│   ├── architecture/          # ★ visual, plain-English architecture guide — open index.html
│   │   ├── index.html         #   overview + the daily loop
│   │   ├── 01-ingestion.html  #   getting the data
│   │   ├── 02-database.html   #   DuckDB + the tables
│   │   ├── 03-trending.html   #   the trending algorithm
│   │   ├── 04-summaries.html  #   AI summaries
│   │   ├── 05-website.html    #   the artifact + site
│   │   ├── 06-operations.html #   scheduling, secrets, failures
│   │   └── style.css          #   shared styling for the guide
│   ├── LAUNCH.html            # step-by-step go-live checklist (interactive)
│   ├── deploy.md              # Cloudflare Pages + scheduler setup
│   └── discord-webhook.md     # how to create the Discord alert webhook
│
├── .env.example               # config template — copy to .env and fill in
├── .env                       # YOUR SECRETS — gitignored, never committed
├── pyproject.toml             # project metadata + dependencies (uv)
├── uv.lock                    # locked dependency versions
├── .gitignore
└── README.md                  # ← you are here
```

**Not in git (generated or private):** `.env` (secrets) · `github_trending.duckdb` (the database) · `site/data/*.json` (published artifact) · `logs/` (run logs) · `.venv/` · `../data/` (the 2.6 GB seed CSVs).

## Documentation index

| I want to… | Open | Format |
|------------|------|--------|
| **Understand the whole system** | [`docs/architecture/index.html`](docs/architecture/index.html) | visual guide (7 pages) |
| **Take it live, step by step** | [`docs/LAUNCH.html`](docs/LAUNCH.html) | interactive checklist |
| **Set up hosting + scheduling** | [`docs/deploy.md`](docs/deploy.md) | markdown |
| **Create the Discord alert webhook** | [`docs/discord-webhook.md`](docs/discord-webhook.md) | markdown |
| **See the design decisions & rationale** | `../.scratch/github-trending/` | see [Design rationale](#design-rationale) |

## Running it

```bash
# one-time setup
uv sync                                       # create the venv + install deps
cp .env.example .env                          # then fill in your tokens (see Configuration)

# run the full pipeline (ingest → … → publish) — the daily job does this
uv run python -m github_trending.orchestrate

# handy variants
uv run python -m github_trending.orchestrate --skip-ingest   # reuse today's snapshot, just rebuild + publish
uv run python -m github_trending.orchestrate --no-publish    # build the site locally, don't deploy

# individual stages / checks
uv run python -m github_trending.backfill     # load the seed CSV history (one time)
uv run python -m github_trending.trending     # print current trending (+ threshold calibration)
uv run python -m github_trending.assemble     # write site/data/latest.json
uv run python tools/preflight.py              # confirm tokens are present
python tests/test_schema.py                   # smoke-check the schema

# preview the site locally
python -m http.server 8000 --directory site   # then open http://localhost:8000
```

## Configuration

All settings come from `.env` (copy from `.env.example`). Secrets are read at call time — **never logged, never committed**.

| Variable | Needed for | Notes |
|----------|-----------|-------|
| `GITHUB_TOKEN` | Ingest + README fetch | public-repo read is enough |
| `GOOGLE_API_KEY` | Gemini summaries | from [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| `ALERT_WEBHOOK_URL` | Failure alerts | Discord webhook — see [`docs/discord-webhook.md`](docs/discord-webhook.md) |
| `CLOUDFLARE_PAGES_PROJECT` | Publishing | leave blank to build without deploying |
| `DATA_DIR` | Backfill | path to the seed CSVs (defaults to `../data`) |
| `DB_PATH` | Everything | DuckDB file (defaults to `github_trending.duckdb`) |

## Status & what's left

**All 9 build phases are complete and verified** (scaffold · schema · backfill · ingest · trending · summaries · artifact · website · orchestration). What remains is account/config setup only you can do — follow [`docs/LAUNCH.html`](docs/LAUNCH.html):

1. Connect Cloudflare Pages (`wrangler`) for publishing.
2. Register the daily task (`tools/register-task.ps1`).
3. Run the first full ~2–3 h sweep.

**Known operating facts:** a full sweep takes ~2–3 h (GitHub secondary rate limits — nightly-batch only, never on-demand). `gemini-2.5-flash-lite` is the summary model; cost is effectively zero at this volume. Trending thresholds start as sensible defaults in `trending.py` (`WINDOWS`) and are meant to be tuned once real results accrue.

## Design rationale

This project was planned before it was built, using a "wayfinder" decision map. The full **specification, the 9 decision tickets (with rationale), and the research** live in the planning workspace:

```
../.scratch/github-trending/
├── SPEC.md                    # consolidated spec + phased build plan
├── map.md                     # the decision index
├── issues/                    # the 9 decision tickets (why each choice was made)
└── research/                  # cited findings (GitHub API, Gemini, the data audit)
```

If you ever wonder *why* something is the way it is, that's where the answer is written down.
