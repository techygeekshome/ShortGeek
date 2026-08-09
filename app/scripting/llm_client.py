"""Optional LLM polish step. Only used if the user has pasted their own API
key into Settings -- otherwise the heuristic writer in writer.py handles
everything with zero external calls. Never raises up to the caller: any
failure (network, bad key, rate limit) just falls back to the heuristic
result, so a flaky connection never breaks a render.
"""
from __future__ import annotations

import json
from typing import Optional

import requests

_TIMEOUT = 30


def polish_script(provider: str, api_key: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    if not api_key:
        return None
    try:
        if provider == "anthropic":
            return _anthropic(api_key, system_prompt, user_prompt)
        if provider == "openai":
            return _openai(api_key, system_prompt, user_prompt)
    except Exception:
        return None
    return None


def _anthropic(api_key: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 400,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    parts = data.get("content", [])
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return text.strip() or None


def _openai(api_key: str, system_prompt: str, user_prompt: str) -> Optional[str]:
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "content-type": "application/json"},
        json={
            "model": "gpt-4o-mini",
            "max_tokens": 400,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
        timeout=_TIMEOUT,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        return None
    return choices[0]["message"]["content"].strip() or None
