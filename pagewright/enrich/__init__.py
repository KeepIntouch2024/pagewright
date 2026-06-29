"""Enrichment orchestrator. Each step is independent and optional; order matters:
copywrite (draft missing copy) → classify (image roles) → icons (match real assets) →
cutout (transparent packshots) → translate (do last, so freshly written copy is translated too).
"""

from __future__ import annotations

from typing import Optional

from ..spec import ProductSpec


def run_enrich(
    spec: ProductSpec,
    *,
    settings,
    assets_dir: str,
    translate: bool = True,
    icons: bool = True,
    cutout: bool = False,
    classify: bool = True,
    copywrite: bool = False,
    icon_dir: Optional[str] = None,
) -> ProductSpec:
    from rich.console import Console

    console = Console()

    if copywrite:
        from .copywrite import copywrite as _cw

        spec = _cw(spec, settings=settings)
        console.print("  · copywrite: drafted missing copy")

    if classify and spec.images:
        from .classify_images import classify_images

        spec = classify_images(spec, settings=settings, assets_dir=assets_dir)
        console.print("  · classify: tagged image roles")

    if icons:
        if icon_dir:
            from .icons import match_icons

            spec = match_icons(spec, icon_dir=icon_dir, assets_dir=assets_dir)
            console.print(f"  · icons: matched against {icon_dir}")
        else:
            console.print("  · icons: skipped (pass --icon-dir to match a real icon library)")

    if cutout:
        from .cutout import cutout as _cut

        spec = _cut(spec, assets_dir=assets_dir)
        console.print("  · cutout: removed backgrounds")

    if translate and spec.meta.language.secondary:
        from .translate import translate as _tr

        spec = _tr(spec, settings=settings, target_lang=spec.meta.language.secondary)
        console.print(f"  · translate: filled {spec.meta.language.secondary} secondary text")

    return spec


__all__ = ["run_enrich"]
