# github-trending

A daily pipeline + static site that surfaces **trending GitHub repositories** — every day it snapshots public repos with ≥500 stars, computes which are rising fastest (day / week / month), writes a plain-language LLM summary of each riser, and publishes the result to a static website.

Full specification & rationale live in the planning workspace: **`../.scratch/github-trending/SPEC.md`** (map + 9 decision tickets + research).

## Architecture

```
GitHub Search API ─► ingest (bucketed) ─┐
data/*.csv (seed)  ─► backfill ──────────┴─► DuckDB ─► trending (ASOF joins)
                                                          │
                                          Gemini summaries (new risers, cached)
                                                          │
                                          latest.json ─► Cloudflare Pages
```

## Build status

| Phase | What | Status |
|------:|------|--------|
| 0 | Scaffold + config | ✅ done |
| 1 | DuckDB schema | ✅ done |
| 2 | Backfill (load `data/` CSVs) | ✅ done — 120,641 repos, 62 days verified |
| 4 | Trending algorithm | ✅ done — runs on real history (built ahead of 3; offline) |
| 3 | Ingestion (Search API sweep) | ⬜ needs `GITHUB_TOKEN` |
| 5 | Gemini summaries | ⬜ needs `GOOGLE_API_KEY` |
| 6 | Artifact assembly (`latest.json`) | ⬜ offline-buildable |
| 7 | Website | ⬜ offline-buildable |
| 8 | Orchestration + scheduler | ⬜ ties it together |

## Quickstart

```bash
uv sync                       # create venv + install deps
cp .env.example .env          # then fill in tokens (Phases 3/5) — never commit .env
python tests/test_schema.py   # smoke-check the schema
```

Configuration is read from `.env` (see `.env.example`). Secrets are never logged or committed.
