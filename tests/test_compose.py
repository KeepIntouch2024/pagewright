"""Composition produces valid, complete HTML from the SA example — no browser needed."""

from pathlib import Path

from pagewright.compose.composer import compose
from pagewright.spec import load_spec

EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "sa_infinity"
SPEC = EXAMPLE_DIR / "product_spec.json"


def _html():
    spec = load_spec(str(SPEC))
    return compose(spec, assets_dir=str(EXAMPLE_DIR), theme_path=str(EXAMPLE_DIR / "theme.toml"))


def test_compose_renders_all_sections():
    html = _html()
    assert html.lstrip().startswith("<!doctype html>")
    assert html.count('class="tcard"') == 12       # tech cards
    assert html.count('class="pcard') == 7          # product cards (+flagship variant)
    assert html.count('class="chip"') == 18         # attribute chips (1+3+5+9)
    assert html.count('class="crow') == 8           # how-to-choose rows
    assert "全部 7 款" in html                        # "used by all" shorthand
    assert 'class="pcard flagship"' in html         # flagship card present


def test_compose_resolves_assets_to_real_files():
    html = _html()
    # at least one icon and one product image resolve to file:// URIs that exist
    import re
    uris = re.findall(r'src="(file://[^"]+)"', html)
    assert uris, "expected file:// asset URIs"
    from urllib.parse import unquote, urlparse

    existing = [u for u in uris if Path(unquote(urlparse(u).path)).exists()]
    assert len(existing) >= 30  # 37 assets total, all copied into the example


def test_safe_inline_keeps_formatting_blocks_injection():
    from pagewright.compose.composer import safe_inline

    ok = str(safe_inline("a <b class='hl'>x</b> <span class=\"sub\">30ft</span> <i>y</i><br>"))
    assert "<b class='hl'>x</b>" in ok and '<span class="sub">30ft</span>' in ok and "<i>y</i>" in ok

    bad = str(safe_inline('<b>x</b><script>steal()</script><b onclick="e">z</b>'))
    assert "<b>x</b>" in bad
    assert "<script>" not in bad and "&lt;script&gt;" in bad      # script escaped to inert text
    assert "<b onclick" not in bad                                # event-handler tag escaped


def test_single_product_minimal_spec_composes():
    """A bare single-product spec (no variants/comparison) still renders."""
    from pagewright.spec import Product, ProductSpec

    spec = ProductSpec(product=Product(name="Demo Widget", summary="A simple thing."))
    html = compose(spec, assets_dir=str(EXAMPLE_DIR))
    assert "Demo Widget" in html
    assert html.count('class="pcard') == 0  # no variants → no product cards
