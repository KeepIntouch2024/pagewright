"""Fill the bilingual (中英对照) secondary text.

Walks the ProductSpec for every ``field`` that has an empty ``field_secondary`` sibling
(plus list pairs like ``columns``/``columns_secondary``), batch-translates them in one
structured call, and writes the results back. The English original is preserved; the
secondary language is the translation — exactly the 中英对照 convention the templates expect.
"""

from __future__ import annotations

from typing import Iterator

from pydantic import BaseModel

from ..llm.base import get_backend
from ..spec import ProductSpec


def _model_iter(obj) -> Iterator[BaseModel]:
    """Yield obj and every nested BaseModel (through lists and dict values)."""
    if isinstance(obj, BaseModel):
        yield obj
        for name in type(obj).model_fields:
            yield from _model_iter(getattr(obj, name))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _model_iter(v)
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _model_iter(v)


def _str_pairs(spec: ProductSpec):
    """(model, base_field) for str fields with an empty *_secondary sibling."""
    for m in _model_iter(spec):
        fields = type(m).model_fields
        for name in fields:
            if name.endswith("_secondary") or f"{name}_secondary" not in fields:
                continue
            val = getattr(m, name)
            sec = getattr(m, f"{name}_secondary")
            if isinstance(val, str) and val.strip() and not sec:
                yield m, name


def _list_pairs(spec: ProductSpec):
    """(model, base_field) for list[str] fields with an empty/short *_secondary sibling."""
    for m in _model_iter(spec):
        fields = type(m).model_fields
        for name in fields:
            if name.endswith("_secondary") or f"{name}_secondary" not in fields:
                continue
            val = getattr(m, name)
            sec = getattr(m, f"{name}_secondary")
            if isinstance(val, list) and val and all(isinstance(x, str) for x in val):
                if not sec or len(sec) < len(val):
                    yield m, name


def translate(spec: ProductSpec, *, settings, target_lang: str) -> ProductSpec:
    # collect units
    units: list[str] = []
    apply: list = []  # (kind, model, field, idx)

    for m, f in _str_pairs(spec):
        apply.append(("str", m, f, None))
        units.append(getattr(m, f))
    for m, f in _list_pairs(spec):
        for i, s in enumerate(getattr(m, f)):
            apply.append(("list", m, f, i))
            units.append(s)

    if not units:
        return spec

    backend = get_backend(settings)
    payload = {str(i): t for i, t in enumerate(units)}
    schema = {
        "type": "object",
        "properties": {
            "translations": {"type": "object", "additionalProperties": {"type": "string"}}
        },
        "required": ["translations"],
    }
    system = (
        f"Translate each value into {target_lang} for a premium e-commerce detail page. "
        "Keep any inline HTML tags (e.g. <b>) intact. Keep product/brand names and units as-is "
        "where idiomatic. Return the SAME keys. Do not add or drop keys."
    )
    prompt = (
        "Translate the values of this JSON object. Return {\"translations\": {<same keys>: "
        f"<translated string>}}.\n\n{_json(payload)}"
    )
    out = backend.structured(prompt, schema=schema, schema_name="translation", system=system)
    tr = out.get("translations", {})

    for idx, (kind, m, f, i) in enumerate(apply):
        t = tr.get(str(idx))
        if not t:
            continue
        if kind == "str":
            setattr(m, f"{f}_secondary", t)
        else:
            sec = list(getattr(m, f"{f}_secondary") or [])
            while len(sec) <= i:
                sec.append("")
            sec[i] = t
            setattr(m, f"{f}_secondary", sec)
    return spec


def _json(obj) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=1)
