"""Anthropic (Claude) backend — the default.

- ``complete`` supports interleaved text + images (vision).
- ``structured`` forces a schema-valid object via tool-use: we expose a single tool whose
  ``input_schema`` is the target JSON Schema and require the model to call it, then return
  the validated tool input. This is far more reliable than parsing free-form JSON.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from .base import Content, ImageRef


class AnthropicBackend:
    name = "anthropic"

    def __init__(self, settings):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "Anthropic backend needs the 'anthropic' package: pip install 'pagewright[anthropic]'"
            ) from e
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set (put it in .env or the environment).")
        self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self._model = settings.default_model()

    # ---- message assembly -----------------------------------------------------------
    def _blocks(self, prompt: Union[str, list[Content]]) -> list[dict]:
        if isinstance(prompt, str):
            return [{"type": "text", "text": prompt}]
        blocks: list[dict] = []
        for part in prompt:
            if isinstance(part, ImageRef):
                mt, b64 = part.to_b64()
                blocks.append(
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": mt, "data": b64},
                    }
                )
            else:
                blocks.append({"type": "text", "text": str(part)})
        return blocks

    # ---- API ------------------------------------------------------------------------
    def complete(
        self,
        prompt: Union[str, list[Content]],
        *,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.4,
    ) -> str:
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "",
            messages=[{"role": "user", "content": self._blocks(prompt)}],
        )
        return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")

    def structured(
        self,
        prompt: Union[str, list[Content]],
        *,
        schema: dict[str, Any],
        schema_name: str = "result",
        system: Optional[str] = None,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        tool = {
            "name": schema_name,
            "description": f"Return the {schema_name} object. Use ONLY information present in "
            "the provided material; never invent facts, prices, icons or specs.",
            "input_schema": schema,
        }
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            temperature=0,
            system=system or "",
            tools=[tool],
            tool_choice={"type": "tool", "name": schema_name},
            messages=[{"role": "user", "content": self._blocks(prompt)}],
        )
        for b in resp.content:
            if getattr(b, "type", None) == "tool_use" and b.name == schema_name:
                return b.input  # already JSON, validated against input_schema by the API
        raise RuntimeError("Model did not return the structured tool call.")
