"""Persist the end-user's LLM choice + key locally (no env vars needed in the GUI).

Stored at ~/.pagewright/settings.json. The desktop app's Settings screen writes here; the
pipeline reads it and feeds a Settings object. The end user pastes their own key — we never
ship one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.path.expanduser("~")) / ".pagewright"
CONFIG_PATH = CONFIG_DIR / "settings.json"

_DEFAULTS = {
    "llm": "",            # "anthropic" | "openai" (incl. local OpenAI-compatible)
    "model": "",
    "api_key": "",
    "base_url": "",       # for openai-compatible / local endpoints
    "target_lang": "zh-CN",
    "theme": "editorial",
}


def load() -> dict:
    data = dict(_DEFAULTS)
    if CONFIG_PATH.exists():
        try:
            data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return data


def save(values: dict) -> dict:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data = load()
    data.update({k: v for k, v in values.items() if k in _DEFAULTS})
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def public(values: Optional[dict] = None) -> dict:
    """Settings safe to send to the browser — the key is masked."""
    v = dict(values or load())
    key = v.get("api_key") or ""
    v["api_key_set"] = bool(key)
    v["api_key"] = ("•" * 8 + key[-4:]) if key else ""
    return v


def to_settings(values: Optional[dict] = None):
    """Build a pagewright Settings object from stored values + env fallback."""
    from ..config import load_settings

    v = values or load()
    overrides = {}
    if v.get("llm"):
        overrides["llm"] = v["llm"]
    if v.get("model"):
        overrides["model"] = v["model"]
    if v.get("api_key"):
        if v.get("llm") == "anthropic":
            overrides["anthropic_api_key"] = v["api_key"]
        else:
            overrides["openai_api_key"] = v["api_key"]
    s = load_settings(**overrides)
    # base_url is read from env by the OpenAI backend
    if v.get("base_url"):
        os.environ["OPENAI_BASE_URL"] = v["base_url"]
    return s
