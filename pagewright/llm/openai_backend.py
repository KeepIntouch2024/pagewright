"""OpenAI backend — ships to prove the LLMBackend seam is real ("通用大模型能力").

Uses the Chat Completions API with vision content parts and ``response_format`` json_schema
for structured output. Any OpenAI-compatible endpoint (set OPENAI_BASE_URL) works too.
"""

from __future__ import annotations

import json
import re
from typing import Any, Optional, Union

from .base import Content, ImageRef


def _extract_json(text: str) -> dict:
    """Best-effort: pull the first balanced {...} object out of free-form text."""
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object found in model output")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])
    raise ValueError("unterminated JSON object in model output")


class OpenAIBackend:
    name = "openai"

    def __init__(self, settings):
        try:
            import openai
        except ImportError as e:  # pragma: no cover
            raise ImportError(
                "OpenAI backend needs the 'openai' package: pip install 'pagewright[openai]'"
            ) from e
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set (put it in .env or the environment).")
        import os

        self._client = openai.OpenAI(
            api_key=settings.openai_api_key, base_url=os.environ.get("OPENAI_BASE_URL") or None
        )
        self._model = settings.default_model()

    def _content(self, prompt: Union[str, list[Content]]) -> Union[str, list[dict]]:
        if isinstance(prompt, str):
            return prompt
        parts: list[dict] = []
        for p in prompt:
            if isinstance(p, ImageRef):
                mt, b64 = p.to_b64()
                parts.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{b64}"}})
            else:
                parts.append({"type": "text", "text": str(p)})
        return parts

    def complete(
        self,
        prompt: Union[str, list[Content]],
        *,
        system: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.4,
    ) -> str:
        msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": self._content(prompt)}
        ]
        resp = self._client.chat.completions.create(
            model=self._model, messages=msgs, max_tokens=max_tokens, temperature=temperature
        )
        return resp.choices[0].message.content or ""

    def structured(
        self,
        prompt: Union[str, list[Content]],
        *,
        schema: dict[str, Any],
        schema_name: str = "result",
        system: Optional[str] = None,
        max_tokens: int = 8192,
    ) -> dict[str, Any]:
        """Three-tier degradation so ANY OpenAI-compatible endpoint works (incl. local
        Ollama / vLLM / LM Studio): json_schema → json_object → plain + JSON extraction."""
        base_msgs = ([{"role": "system", "content": system}] if system else []) + [
            {"role": "user", "content": self._content(prompt)}
        ]

        def call(response_format, extra_system=None):
            msgs = list(base_msgs)
            if extra_system:
                msgs = [{"role": "system", "content": extra_system}] + msgs
            kwargs = dict(model=self._model, messages=msgs, max_tokens=max_tokens, temperature=0)
            if response_format:
                kwargs["response_format"] = response_format
            resp = self._client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""

        schema_hint = (
            "Respond with a single JSON object that conforms to this JSON Schema. Output ONLY the "
            "JSON, no prose, no code fences.\nSchema:\n" + json.dumps(schema)
        )
        # 1) strict json_schema (OpenAI, recent vLLM)
        try:
            rf = {"type": "json_schema",
                  "json_schema": {"name": schema_name, "schema": schema, "strict": False}}
            return json.loads(call(rf))
        except Exception:
            pass
        # 2) plain json_object mode (Ollama, most local servers) + schema in the prompt
        try:
            return json.loads(call({"type": "json_object"}, extra_system=schema_hint))
        except Exception:
            pass
        # 3) no response_format at all — extract the JSON object from free text
        return _extract_json(call(None, extra_system=schema_hint))
