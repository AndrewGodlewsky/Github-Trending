"""Failure alerts via a Discord incoming webhook (ticket ⑦).

A webhook URL is just an address Discord gives you that posts a message into one
channel — no bot, no auth token to manage. We POST a small JSON body to it.
"""
from __future__ import annotations

import httpx

DISCORD_LIMIT = 1900  # Discord caps content at 2000 chars; stay under


def notify(webhook_url: str, message: str, username: str = "Trending Pipeline") -> None:
    """Post a message to the Discord channel behind `webhook_url`. Raises on failure."""
    r = httpx.post(
        webhook_url,
        json={"content": message[:DISCORD_LIMIT], "username": username},
        timeout=15.0,
    )
    r.raise_for_status()
