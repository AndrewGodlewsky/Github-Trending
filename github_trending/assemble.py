"""Phase 6 — assemble the published artifact (ticket ⑤).

Reads the DB and writes `latest.json` (the file the site fetches) plus a dated
`archive/` copy. Each entry carries the ④ trending metrics, the ② summary (from
cache, may be null if not yet summarized), a derived avatar URL, and a `spark`
trajectory (the ⑥ sparkline) sourced from `snapshots` history.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .db import connect
from .trending import WINDOWS, compute_trending

SCHEMA_VERSION = 1
SPARK_DAYS = 30


def _now_date(con):
    return con.execute("SELECT max(run_date) FROM runs WHERE status='complete'").fetchone()[0]


def _spark(con, repo_id: int, now_date) -> list[int]:
    start = now_date - timedelta(days=SPARK_DAYS)
    rows = con.execute("""
        SELECT stars FROM snapshots
        WHERE repo_id = ? AND snapshot_date > ? AND snapshot_date <= ?
        ORDER BY snapshot_date
    """, [repo_id, start, now_date]).fetchall()
    return [r[0] for r in rows]


def _summary(con, repo_id: int) -> str | None:
    row = con.execute("SELECT summary_text FROM summaries WHERE repo_id = ?", [repo_id]).fetchone()
    return row[0] if row else None


def build_window(con, window: str, now_date, top_n: int = 50) -> dict:
    lag = WINDOWS[window][0]
    entries = []
    for rank, r in enumerate(compute_trending(con, window, top_n=top_n), 1):
        entries.append({
            "rank": rank,
            "full_name": r["full_name"], "owner": r["owner"], "name": r["name"],
            "html_url": f"https://github.com/{r['full_name']}",
            "avatar_url": f"https://github.com/{r['owner']}.png",
            "description": r["description"],
            "language": r["primary_language"],
            "topics": list(r["topics"] or [])[:6],
            "stars": r["stars_now"],
            "abs_gain": r["abs_gain"],
            "pct_gain": round(r["pct_gain"], 4),
            "elapsed_days": r["elapsed_days"],
            "summary": _summary(con, r["repo_id"]),
            "spark": _spark(con, r["repo_id"], now_date),
        })
    return {"boundary_date": str(now_date - timedelta(days=lag)),
            "count": len(entries), "repos": entries}


def assemble(con, top_n: int = 50) -> dict:
    now_date = _now_date(con)
    return {
        "version": SCHEMA_VERSION,
        "as_of": str(now_date),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "windows": {w: build_window(con, w, now_date, top_n) for w in WINDOWS},
    }


def write_artifact(payload: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir)
    (out / "archive").mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    latest = out / "latest.json"
    latest.write_text(body, encoding="utf-8")
    (out / "archive" / f"{payload['as_of']}.json").write_text(body, encoding="utf-8")
    return latest


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    from .config import load_config
    cfg = load_config()
    con = connect(cfg.db_path)
    payload = assemble(con)
    path = write_artifact(payload, Path("site") / "data")
    size = path.stat().st_size
    have_summary = sum(1 for w in payload["windows"].values()
                       for e in w["repos"] if e["summary"])
    total = sum(w["count"] for w in payload["windows"].values())
    print(f"wrote {path} ({size/1024:.0f} KB)")
    print(f"  windows: " + ", ".join(f"{w}={payload['windows'][w]['count']}" for w in WINDOWS))
    print(f"  summaries present: {have_summary}/{total}")
    print(f"  as_of={payload['as_of']} generated_at={payload['generated_at']}")
    con.close()


if __name__ == "__main__":
    main()
