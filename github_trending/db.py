"""DuckDB schema and connection.

Schema per ticket ③ (amended by ⑧ to enrich snapshots with forks/open_issues).
DuckDB chosen for its ASOF JOIN, which expresses gap-tolerant "latest snapshot
at or before N days ago" cleanly — the backbone of the ticket ④ trending math.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

SCHEMA = """
-- slow-changing dimension; overwrite-in-place (latest metadata wins). Key = stable GitHub numeric id.
CREATE TABLE IF NOT EXISTS repos (
    repo_id BIGINT PRIMARY KEY,
    full_name VARCHAR,
    owner VARCHAR,
    name VARCHAR,
    primary_language VARCHAR,
    description VARCHAR,
    topics VARCHAR[],
    created_at TIMESTAMP,
    first_seen_date DATE,
    last_seen_date DATE,
    is_active BOOLEAN
);

-- dense fact: one measurement per repo per run day (dense so a missing day is a real gap, not "unchanged").
CREATE TABLE IF NOT EXISTS snapshots (
    repo_id BIGINT,
    snapshot_date DATE,
    stars INTEGER,
    forks INTEGER,
    open_issues INTEGER,
    PRIMARY KEY (repo_id, snapshot_date)
);

-- Gemini summary cache (ticket ②): key by content + model + prompt version.
CREATE TABLE IF NOT EXISTS summaries (
    repo_id BIGINT PRIMARY KEY,
    readme_sha VARCHAR,
    model_id VARCHAR,
    prompt_version VARCHAR,
    summary_text VARCHAR,
    generated_at TIMESTAMP
);

-- authoritative run/completeness log — distinguishes a real gap from a partial/failed sweep; supports resumability.
CREATE TABLE IF NOT EXISTS runs (
    run_date DATE PRIMARY KEY,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    status VARCHAR,          -- 'running' | 'complete' | 'partial' | 'failed' | 'absent'
    repos_seen INTEGER,
    bucket_count INTEGER
);
"""

TABLES = ("repos", "snapshots", "summaries", "runs")


def connect(db_path: str | Path = ":memory:") -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(db_path))


def init_db(con: duckdb.DuckDBPyConnection) -> None:
    """Create all tables if absent. Idempotent."""
    con.execute(SCHEMA)
