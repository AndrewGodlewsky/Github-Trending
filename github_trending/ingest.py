"""Phase 3 — live daily ingest: bucketed GitHub Search API sweep (ticket ①).

The Search API caps at 1,000 results/query and ~30 requests/min, so we can't ask
for "all repos ≥500★" at once. Instead we walk adaptive `stars:LOW..HIGH` bands,
each sized (by binary-searching HIGH on `total_count`) to stay under the cap, and
page through each. Every repo row carries `stargazers_count` inline, so one sweep
is a complete daily snapshot with zero per-repo calls.

Writes today's (UTC) rows into `snapshots` (dense) and upserts `repos`.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

import httpx

from .db import connect, init_db

log = logging.getLogger("github_trending.ingest")

API = "https://api.github.com"
CAP = 900          # keep each band comfortably under the 1,000-result ceiling
PER_PAGE = 100
SEARCH_RPM = 28    # just under the 30/min Search-API limit


class _Rate:
    """Simple pacer: never issue Search requests faster than SEARCH_RPM.
    Also counts every request issued (wait() is called once per request)."""
    def __init__(self, rpm: int) -> None:
        self.interval = 60.0 / rpm
        self.last = 0.0
        self.count = 0

    def wait(self) -> None:
        gap = time.monotonic() - self.last
        if gap < self.interval:
            time.sleep(self.interval - gap)
        self.last = time.monotonic()
        self.count += 1


def _client(token: str) -> httpx.Client:
    return httpx.Client(
        base_url=API,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "github-trending-ingest",
        },
        timeout=30.0,
    )


def _search(client: httpx.Client, rate: _Rate, q: str, page: int = 1) -> dict:
    """One Search API call, with backoff on primary/secondary rate limits."""
    for _ in range(6):
        rate.wait()
        r = client.get("/search/repositories", params={
            "q": q, "sort": "stars", "order": "asc", "per_page": PER_PAGE, "page": page,
        })
        if r.status_code == 200:
            return r.json()
        if r.status_code in (403, 429):
            retry_after = r.headers.get("retry-after")
            if retry_after:
                time.sleep(float(retry_after) + 1)
            else:
                reset = r.headers.get("x-ratelimit-reset")
                delay = max(1.0, float(reset) - time.time() + 1) if reset else 5.0
                time.sleep(min(delay, 90.0))
            continue
        r.raise_for_status()
    r.raise_for_status()
    raise RuntimeError("unreachable")


def _count(client: httpx.Client, rate: _Rate, low: int, high: int | None) -> int:
    q = f"stars:{low}..{high}" if high is not None else f"stars:>={low}"
    return _search(client, rate, q, page=1)["total_count"]


def _next_high(client: httpx.Client, rate: _Rate, low: int, ceiling: int) -> int:
    """Largest HIGH ≤ ceiling with count(low..HIGH) ≤ CAP.

    Exponential search to bracket the band, then binary search *within that small
    bracket* — so probes per band scale with the band's width, not with `ceiling`.
    (The old version binary-searched from `ceiling`=1e6 every time, ~20 probes/band.)
    """
    if _count(client, rate, low, ceiling) <= CAP:
        return ceiling  # everything remaining fits in one band
    # grow a window from `low` until it holds > CAP repos (or hits the ceiling)
    step = max(1, low // 50)
    hi = min(ceiling, low + step)
    while hi < ceiling and _count(client, rate, low, hi) <= CAP:
        step *= 2
        hi = min(ceiling, low + step)
    # binary search in [low, hi] for the largest high with count(low..high) ≤ CAP
    lo, hi2 = low, hi
    while lo < hi2:
        mid = (lo + hi2 + 1) // 2
        if _count(client, rate, low, mid) <= CAP:
            lo = mid
        else:
            hi2 = mid - 1
    return lo


def _rows(items: list[dict], today) -> tuple[list, list]:
    snaps, repos = [], []
    for it in items:
        rid = it["id"]
        snaps.append((rid, today, it.get("stargazers_count"),
                      it.get("forks_count"), it.get("open_issues_count")))
        owner = (it.get("owner") or {}).get("login")
        repos.append((rid, it.get("full_name"), owner, it.get("name"),
                      it.get("language"), it.get("description"),
                      it.get("topics") or [], it.get("created_at"), today, today, True))
    return snaps, repos


def _upsert(con, snaps: list, repos: list) -> None:
    con.executemany("""
        INSERT INTO snapshots (repo_id, snapshot_date, stars, forks, open_issues)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (repo_id, snapshot_date) DO UPDATE SET
            stars = excluded.stars, forks = excluded.forks, open_issues = excluded.open_issues
    """, snaps)
    con.executemany("""
        INSERT INTO repos (repo_id, full_name, owner, name, primary_language, description,
                           topics, created_at, first_seen_date, last_seen_date, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (repo_id) DO UPDATE SET
            full_name=excluded.full_name, owner=excluded.owner, name=excluded.name,
            primary_language=excluded.primary_language, description=excluded.description,
            topics=excluded.topics, created_at=excluded.created_at,
            last_seen_date=excluded.last_seen_date, is_active=TRUE
        -- first_seen_date deliberately preserved
    """, repos)


def sweep(con, token: str, min_stars: int = 500, ceiling: int | None = None,
          max_bands: int | None = None, mark_run: bool = True) -> dict:
    """Walk star bands from `min_stars` up, ingesting each. Returns run stats.

    `ceiling`/`max_bands` bound the sweep for testing. `mark_run=False` skips the
    `runs` row (use for partial test slices so real completeness isn't implied).
    """
    today = datetime.now(timezone.utc).date()
    rate = _Rate(SEARCH_RPM)
    seen, bands = 0, 0
    with _client(token) as client:
        top = ceiling if ceiling is not None else 1_000_000  # star ceiling; 1M > any repo
        low = min_stars
        while low <= top:
            if max_bands is not None and bands >= max_bands:
                break
            high = _next_high(client, rate, low, top)
            total = _count(client, rate, low, high)
            pages = min(10, -(-total // PER_PAGE))  # ceil, capped at 10
            for page in range(1, pages + 1):
                data = _search(client, rate, f"stars:{low}..{high}", page)
                items = data.get("items", [])
                if not items:
                    break
                snaps, repos = _rows(items, today)
                _upsert(con, snaps, repos)
                seen += len(items)
            bands += 1
            if bands % 25 == 0:
                log.info("ingest progress: %d bands · %d repos · %d requests (at stars≥%d)",
                         bands, seen, rate.count, low)
            low = high + 1
            if ceiling is None and _count(client, rate, low, None) == 0:
                break
    stats = {"run_date": today, "repos_seen": seen, "bands": bands, "requests": rate.count}
    if mark_run:
        con.execute("""
            INSERT INTO runs (run_date, started_at, finished_at, status, repos_seen, bucket_count)
            VALUES (?, ?, ?, 'complete', ?, ?)
            ON CONFLICT (run_date) DO UPDATE SET
                finished_at=excluded.finished_at, status='complete',
                repos_seen=excluded.repos_seen, bucket_count=excluded.bucket_count
        """, [today, datetime.now(timezone.utc), datetime.now(timezone.utc), seen, bands])
    return stats


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from .config import load_config, require
    cfg = load_config()
    con = connect(cfg.db_path)
    init_db(con)
    stats = sweep(con, require(cfg.github_token, "GITHUB_TOKEN"))
    print("sweep complete:", stats)
    con.close()


if __name__ == "__main__":
    main()
