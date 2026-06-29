"""Light, grounded copywriting — fill MISSING narrative only, never overwrite or invent facts.

Drafts a product ``summary`` and section ``leads`` (intro paragraphs) when absent, using only
what's already in the spec (features, variants, attributes). Existing copy is left untouched.
Marketing tone, but every claim must be supported by the spec — this is not a license to
hallucinate specs.
"""

from __future__ import annotations

from ..llm.base import get_backend
from ..spec import Lead, ProductSpec

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "leads": {"type": "object", "additionalProperties": {"type": "string"}},
    },
}

SYSTEM = (
    "You are an e-commerce copywriter. Using ONLY the facts in the given ProductSpec JSON, write "
    "concise, vivid copy in the product's primary language. Do not introduce any spec, number, or "
    "claim that isn't already present. Return a 'summary' (2-3 sentences) only if one is missing, "
    "and 'leads' = a map of section-name -> one intro sentence, only for the sections listed."
)


def copywrite(spec: ProductSpec, *, settings) -> ProductSpec:
    missing_sections = [
        name for name, present in {
            "highlights": bool(spec.highlights),
            "features": bool(spec.features),
            "attributes": bool(spec.attributes),
            "variants": bool(spec.variants),
        }.items()
        if present and name not in spec.leads
    ]
    if spec.product.summary and not missing_sections:
        return spec

    backend = get_backend(settings)
    ask = {
        "need_summary": not spec.product.summary,
        "need_leads_for": missing_sections,
        "spec": spec.model_dump(exclude_none=True, include={"product", "features", "variants", "attributes", "highlights"}),
    }
    import json

    out = backend.structured(
        "Write the requested copy.\n\n" + json.dumps(ask, ensure_ascii=False)[:12000],
        schema=_SCHEMA, schema_name="copy", system=SYSTEM,
    )
    if out.get("summary") and not spec.product.summary:
        spec.product.summary = out["summary"]
    for name, text in (out.get("leads") or {}).items():
        if name in missing_sections and text:
            spec.leads[name] = Lead(text=text)
    return spec
