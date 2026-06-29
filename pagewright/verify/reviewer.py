"""Multi-lens QA — the project's signature move (a generalization of the source project's
4-lens adversarial review). Two layers:

  1. Deterministic integrity checks (no LLM): every asset referenced by the spec resolves to a
     real file; variant feature_ids exist; comparison column counts line up. These catch the
     failure mode that motivated the whole project — a referenced icon/photo that isn't actually
     there — without spending a token.

  2. Optional LLM lenses over the rendered panels + spec: fact/data fidelity, icon/asset
     fidelity, layout/visual sanity, localization completeness.

Returns a report dict and (optionally) writes it as JSON. `passed` is False if any integrity
error or any high-severity LLM finding is present.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from ..llm.base import ImageRef, get_backend
from ..spec import ProductSpec

_LENSES = {
    "fidelity": "Check FACT fidelity: does every number, price, spec and claim shown also appear "
    "in the spec JSON? Flag anything on the page not supported by the spec.",
    "icons": "Check ICON/ASSET fidelity: do the visible icons and photos plausibly match their "
    "adjacent labels? Flag a mismatch (e.g. an icon that doesn't correspond to its title).",
    "layout": "Check LAYOUT: flag overflowing/clipped text, broken grids, overlap, empty slots, "
    "or images that failed to load.",
    "localization": "Check LOCALIZATION: is the bilingual text complete and natural? Flag missing "
    "translations or untranslated leftovers.",
}

_FINDINGS_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["high", "medium", "low"]},
                    "message": {"type": "string"},
                },
                "required": ["severity", "message"],
            },
        }
    },
    "required": ["findings"],
}


def _integrity_checks(spec: ProductSpec, assets_dir: str) -> list[dict]:
    findings: list[dict] = []

    def resolve(path: str) -> bool:
        if path.startswith(("http://", "https://", "data:")):
            return True
        p = path if os.path.isabs(path) else os.path.join(assets_dir, path)
        return os.path.exists(p)

    for a in spec.all_assets():
        ref = a.asset or a.url
        if a.asset and not resolve(a.asset):
            findings.append({"lens": "integrity", "severity": "high",
                             "message": f"missing asset file: {a.asset}"})

    feat_ids = {f.id for f in spec.features}
    for v in spec.variants:
        for fid in v.feature_ids:
            if fid not in feat_ids:
                findings.append({"lens": "integrity", "severity": "high",
                                 "message": f"variant {v.id!r} references unknown feature {fid!r}"})

    if spec.comparison and spec.comparison.rows:
        ncols = len(spec.comparison.columns)
        for r in spec.comparison.rows:
            if len(r.cells) != ncols:
                findings.append({"lens": "integrity", "severity": "medium",
                                 "message": f"comparison row {r.label!r} has {len(r.cells)} cells, "
                                            f"expected {ncols}"})
    return findings


def _llm_lenses(out_dir: str, spec: ProductSpec, settings) -> list[dict]:
    panels = sorted(Path(out_dir).glob("panel_*.png"))
    images = [ImageRef(path=str(p)) for p in panels[:6]]
    if not images:
        full = Path(out_dir, "full.png")
        if full.exists():
            images = [ImageRef(path=str(full))]
    if not images:
        return [{"lens": "llm", "severity": "low", "message": "no rendered image to review"}]

    backend = get_backend(settings)
    spec_json = spec.model_dump_json(exclude_none=True)[:16000]
    out: list[dict] = []
    for lens, instruction in _LENSES.items():
        prompt = [
            f"You are reviewing a rendered e-commerce detail page (panels below) against its "
            f"source spec.\n\n{instruction}\n\nSPEC JSON (truncated):\n{spec_json}",
            *images,
        ]
        try:
            res = backend.structured(prompt, schema=_FINDINGS_SCHEMA, schema_name="review")
            for f in res.get("findings", []):
                out.append({"lens": lens, **f})
        except Exception as e:
            out.append({"lens": lens, "severity": "low", "message": f"lens skipped: {e}"})
    return out


def verify(
    out_dir: str,
    spec: ProductSpec,
    *,
    settings,
    assets_dir: Optional[str] = None,
    report_path: Optional[str] = None,
    use_llm: bool = True,
) -> dict:
    assets_dir = assets_dir or out_dir
    findings = _integrity_checks(spec, assets_dir)
    if use_llm:
        try:
            findings += _llm_lenses(out_dir, spec, settings)
        except Exception as e:
            findings.append({"lens": "llm", "severity": "low", "message": f"LLM review skipped: {e}"})

    passed = not any(f["severity"] == "high" for f in findings)
    report = {"passed": passed, "findings": findings,
              "counts": {sev: sum(1 for f in findings if f["severity"] == sev)
                         for sev in ("high", "medium", "low")}}
    if report_path:
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
