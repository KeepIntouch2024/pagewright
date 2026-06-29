"""Pluggable LLM backend protocol.

Pagewright needs three capabilities from "a general large model":
  1. text  — write/translate/critique given text.
  2. vision — reason over screenshots / product photos (extraction, image-role
     classification, visual QA of the rendered page).
  3. structured — return an object that validates against a JSON Schema (used to force a
     schema-clean ProductSpec; implemented via tool-use / response_format under the hood).

Backends implement LLMBackend. The default is Anthropic (Claude); an OpenAI backend ships
to prove the seam. Pick via PAGEWRIGHT_LLM.
"""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Protocol, Union


@dataclass
class ImageRef:
    """An image to attach to a vision call — a local path or raw bytes."""

    path: Optional[str] = None
    data: Optional[bytes] = None
    media_type: Optional[str] = None

    def to_b64(self) -> tuple[str, str]:
        if self.data is not None:
            mt = self.media_type or "image/png"
            return mt, base64.b64encode(self.data).decode("ascii")
        assert self.path, "ImageRef needs path or data"
        mt = self.media_type or mimetypes.guess_type(self.path)[0] or "image/png"
        return mt, base64.b64encode(Path(self.path).read_bytes()).decode("ascii")


Content = Union[str, ImageRef]


class LLMBackend(Protocol):
    name: str

    def complete(
        self,
        prompt: Union[str, list[Content]],
        *,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.4,
    ) -> str:
        """Free-form text (optionally multimodal) → text."""
        ...

    def structured(
        self,
        prompt: Union[str, list[Content]],
        *,
        schema: dict[str, Any],
        schema_name: str = "result",
        system: Optional[str] = None,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Free-form (optionally multimodal) → a dict validating against ``schema``."""
        ...


def get_backend(settings) -> LLMBackend:
    """Factory keyed on settings.llm. No vendor is assumed — the user must choose one."""
    if not settings.llm:
        from ..config import _NO_LLM_MSG

        raise RuntimeError(_NO_LLM_MSG)
    if settings.llm == "anthropic":
        from .anthropic_backend import AnthropicBackend

        return AnthropicBackend(settings)
    if settings.llm == "openai":
        from .openai_backend import OpenAIBackend

        return OpenAIBackend(settings)
    raise ValueError(f"Unknown LLM backend: {settings.llm!r} (try 'anthropic' or 'openai')")
