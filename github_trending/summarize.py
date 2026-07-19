"""Phase 5 — Gemini summaries (ticket ②).

For each trending repo lacking a fresh summary, fetch its README + metadata,
ask Gemini for a plain-language paragraph, and cache it keyed by the README's
git-blob sha (+ model + prompt version). Cache hits cost nothing — only new or
changed READMEs hit the API, keeping the daily volume (and cost) tiny.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone

import httpx
from google import genai
from google.genai import types

MODEL = "gemini-2.5-flash-lite"
PROMPT_VERSION = "v1"
README_CHAR_CAP = 24_000  # ~6k tokens

PROMPT = """You explain software projects in plain language to a curious reader who is NOT a domain expert.

Using ONLY the information between the <source> tags below, write ONE paragraph of 2 to 4 sentences that explains what this project is and what it does.

Rules:
- Use only facts present in the source. Do NOT invent features, capabilities, benchmarks, or integrations that are not stated.
- If the source does not make clear what the project does, say so in a single sentence instead of guessing.
- Avoid jargon and acronyms; if a technical term is unavoidable, add a short plain-language gloss.
- No marketing or hype ("powerful", "seamless", "revolutionary"), no bullet points, no headings, no code, no emojis.
- Write in the present tense, third person. Output only the paragraph.

<source>
Repository: {full_name}
Description: {description}
Primary language: {language}
Topics: {topics}
Stars: {stars}
README (may be truncated):
{readme}
</source>"""


def fetch_readme(gh: httpx.Client, full_name: str) -> tuple[str | None, str | None]:
    """Return (sha, text) for the repo's README, or (None, None) if it has none."""
    r = gh.get(f"/repos/{full_name}/readme")
    if r.status_code == 404:
        return None, None
    r.raise_for_status()
    data = r.json()
    text = base64.b64decode(data["content"]).decode("utf-8", "replace")
    return data["sha"], text[:README_CHAR_CAP]


def build_prompt(meta: dict, readme: str | None) -> str:
    return PROMPT.format(
        full_name=meta["full_name"],
        description=meta.get("description") or "none",
        language=meta.get("primary_language") or "unknown",
        topics=", ".join(meta.get("topics") or []) or "none",
        stars=meta.get("stars_now", meta.get("stars", "unknown")),
        readme=readme or "(no README provided — summarize from the metadata above only)",
    )


def summarize_one(gc: genai.Client, prompt: str) -> str:
    import time
    cfg = types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=200,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )
    for attempt in range(4):
        try:
            resp = gc.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            return (resp.text or "").strip()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)  # backoff on transient / rate-limit errors
    raise RuntimeError("unreachable")


def _cached(con, repo_id: int, readme_sha: str | None) -> bool:
    row = con.execute(
        "SELECT readme_sha, model_id, prompt_version FROM summaries WHERE repo_id = ?",
        [repo_id],
    ).fetchone()
    return bool(row and row[0] == readme_sha and row[1] == MODEL and row[2] == PROMPT_VERSION)


def run_summaries(con, gh_token: str, google_key: str, repos: list[dict]) -> dict:
    gc = genai.Client(api_key=google_key)
    generated = cached = no_readme = 0
    with httpx.Client(
        base_url="https://api.github.com",
        headers={"Authorization": f"Bearer {gh_token}",
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "github-trending-summarize"},
        timeout=30.0,
    ) as gh:
        for meta in repos:
            sha, readme = fetch_readme(gh, meta["full_name"])
            if _cached(con, meta["repo_id"], sha):
                cached += 1
                continue
            if readme is None:
                no_readme += 1
            text = summarize_one(gc, build_prompt(meta, readme))
            con.execute("""
                INSERT INTO summaries (repo_id, readme_sha, model_id, prompt_version, summary_text, generated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (repo_id) DO UPDATE SET
                    readme_sha=excluded.readme_sha, model_id=excluded.model_id,
                    prompt_version=excluded.prompt_version, summary_text=excluded.summary_text,
                    generated_at=excluded.generated_at
            """, [meta["repo_id"], sha, MODEL, PROMPT_VERSION, text, datetime.now(timezone.utc)])
            generated += 1
    return {"generated": generated, "cached": cached, "no_readme": no_readme}
