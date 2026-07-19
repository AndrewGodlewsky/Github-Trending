"""Runtime configuration, loaded from environment / `.env`.

Secrets are read here and used at the point of the API call — never logged,
never committed. Per repo policy, we don't work around missing credentials;
a phase that needs a token fails loudly if it's absent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    data_dir: Path
    db_path: Path
    github_token: str | None
    google_api_key: str | None
    alert_webhook_url: str | None
    cloudflare_pages_project: str | None


def load_config() -> Config:
    return Config(
        data_dir=Path(os.getenv("DATA_DIR", "../data")).expanduser(),
        db_path=Path(os.getenv("DB_PATH", "github_trending.duckdb")).expanduser(),
        github_token=os.getenv("GITHUB_TOKEN"),
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL"),
        cloudflare_pages_project=os.getenv("CLOUDFLARE_PAGES_PROJECT"),
    )


def require(value: str | None, name: str) -> str:
    """Return a required secret or fail loudly (never silently proceed without it)."""
    if not value:
        raise RuntimeError(f"{name} is not set — add it to .env (see .env.example).")
    return value
