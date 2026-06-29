"""Runtime configuration. Resolved from (in order): explicit kwargs > environment
(.env auto-loaded) > defaults. Keep this tiny — everything is overridable on the CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

try:  # auto-load a .env if python-dotenv is present
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass


_NO_LLM_MSG = (
    "No LLM backend selected. Set PAGEWRIGHT_LLM (in .env or the environment) or pass --llm. "
    "Options: 'anthropic' (Claude), 'openai' (OpenAI or any OpenAI-compatible/local endpoint). "
    "The compose/render stages need no LLM; only extract/enrich/verify do."
)


def _env(*keys: str, default: Optional[str] = None) -> Optional[str]:
    for k in keys:
        v = os.environ.get(k)
        if v:
            return v
    return default


@dataclass
class Settings:
    # --- LLM backend (no default vendor — must be chosen explicitly) ---
    llm: Optional[str] = field(default_factory=lambda: _env("PAGEWRIGHT_LLM"))
    model: Optional[str] = field(default_factory=lambda: _env("PAGEWRIGHT_MODEL"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    openai_api_key: Optional[str] = field(default_factory=lambda: _env("OPENAI_API_KEY"))

    # --- rendering ---
    width: int = field(default_factory=lambda: int(_env("PAGEWRIGHT_WIDTH", default="750")))
    scale: float = field(default_factory=lambda: float(_env("PAGEWRIGHT_SCALE", default="2")))
    # Chrome refuses screenshots taller than ~16384 device px; renderer falls back to
    # tiling above this and warns. Kept configurable for headroom experiments.
    max_screenshot_px: int = 16384

    # --- acquisition ---
    # CDP endpoint of a real, user-launched Chrome for tier-3 (Cloudflare/login walls).
    cdp_url: str = field(default_factory=lambda: _env("PAGEWRIGHT_CDP_URL", default="http://localhost:9222"))
    user_agent: str = field(
        default_factory=lambda: _env(
            "PAGEWRIGHT_UA",
            default=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
    )
    request_timeout: float = 30.0
    respect_robots: bool = field(
        default_factory=lambda: _env("PAGEWRIGHT_RESPECT_ROBOTS", default="1") not in ("0", "false")
    )
    rate_limit_s: float = field(default_factory=lambda: float(_env("PAGEWRIGHT_RATE_LIMIT", default="1.0")))

    # Per-vendor default model when PAGEWRIGHT_MODEL isn't set. None of these is a global
    # default — the vendor itself must be chosen first via PAGEWRIGHT_LLM / --llm.
    _VENDOR_DEFAULTS = {"anthropic": "claude-opus-4-8", "openai": "gpt-4o"}

    def default_model(self) -> str:
        if self.model:
            return self.model
        if not self.llm:
            raise RuntimeError(_NO_LLM_MSG)
        return self._VENDOR_DEFAULTS.get(self.llm, "")


def load_settings(**overrides) -> Settings:
    s = Settings()
    for k, v in overrides.items():
        if v is not None and hasattr(s, k):
            setattr(s, k, v)
    return s
