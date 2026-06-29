"""Pagewright CLI.

  pagewright run    URL | --spec spec.json | --manual DIR     # end-to-end
  pagewright acquire URL -o work/                              # [1] fetch raw material
  pagewright extract work/ -o spec.json                        # [2] LLM -> ProductSpec
  pagewright extract --manual DIR -o spec.json                 #     (uploads -> ProductSpec)
  pagewright enrich spec.json                                  # [3] translate/icons/cutout
  pagewright compose spec.json --theme editorial -o page.html  # [4] -> HTML
  pagewright render page.html -o out/                          # [5] HTML -> PNG + panels
  pagewright verify out/ spec.json                             # [6] multi-lens QA
  pagewright schema                                            # print the ProductSpec JSON Schema

Stages are independent and chainable; each persists a human-editable artifact so you can
fix the spec or HTML by hand and re-run downstream only.
"""

from __future__ import annotations

import os
import sys

import click
from rich.console import Console

from .config import load_settings
from .spec import ProductSpec, dump_spec, load_spec

console = Console()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option()
def main():
    """LLM-orchestrated e-commerce poster / 详情页 generator."""


# -- global LLM options shared by the LLM-using commands -----------------------------------
def _llm_opts(f):
    f = click.option("--llm", default=None, help="LLM backend (anthropic|openai).")(f)
    f = click.option("--model", default=None, help="Model id override.")(f)
    return f


@main.command()
def schema():
    """Print the ProductSpec JSON Schema (the data contract)."""
    click.echo(ProductSpec.json_schema_str())


@main.command()
@click.option("--port", default=8765, help="Port to serve on.")
@click.option("--host", default="127.0.0.1")
@click.option("--no-browser", is_flag=True, help="Don't auto-open the browser.")
def serve(port, host, no_browser):
    """Run the local web UI (open in a browser)."""
    from .app.server import serve as _serve

    console.print(f"[green]Pagewright UI[/] → http://{host}:{port}")
    _serve(host=host, port=port, open_browser=not no_browser)


@main.command()
def app():
    """Launch the desktop window (native webview)."""
    from .app.desktop import main as _desktop

    _desktop()


@main.group()
def library():
    """Browse the generation library (history / versions) at ~/.pagewright/library."""


@library.command("list")
def library_list():
    """List archived generations (newest first)."""
    from . import library as lib

    entries = lib.list_entries()
    if not entries:
        console.print("[dim]library is empty[/]")
        return
    from rich.table import Table

    t = Table(show_header=True, header_style="bold")
    for col in ("ID", "PROJECT", "VER", "TITLE", "CREATED", "SIZE"):
        t.add_column(col)
    for m in entries:
        sz = "×".join(map(str, m["full_size"])) if m.get("full_size") else "—"
        t.add_row(m["id"], m["project"], f"v{m['version']}", (m.get("title") or "")[:30],
                  m.get("created_at", "")[:19], sz)
    console.print(t)


@library.command("open")
@click.argument("entry_id")
def library_open(entry_id):
    """Open an entry's full image in the default viewer."""
    import subprocess
    import sys

    from . import library as lib

    p = lib.file_path(entry_id, "full.png")
    if not p:
        raise click.ClickException(f"no full.png for {entry_id}")
    opener = "open" if sys.platform == "darwin" else ("start" if os.name == "nt" else "xdg-open")
    subprocess.run([opener, str(p)])


@library.command("path")
@click.argument("entry_id")
def library_path(entry_id):
    """Print an entry's folder path."""
    from . import library as lib

    console.print(str(lib.entry_dir(entry_id)))


@library.command("rm")
@click.argument("entry_id")
def library_rm(entry_id):
    """Delete an entry."""
    from . import library as lib

    console.print("[green]deleted[/]" if lib.delete(entry_id) else "[red]not found[/]")


@main.command()
@click.argument("url")
@click.option("-o", "--out", "out_dir", default="work", help="Output dir for raw capture.")
@click.option("--tier", type=click.IntRange(1, 3), default=None, help="Force a fetch tier (1-3).")
@click.option("--no-images", is_flag=True, help="Skip downloading product images.")
def acquire(url, out_dir, tier, no_images):
    """[1] Fetch raw material from a product URL (layered fallback fetcher)."""
    from .acquire.fetcher import acquire as do_acquire

    s = load_settings()
    cap = do_acquire(url, out_dir, settings=s, force_tier=tier, download_images=not no_images)
    console.print(f"[green]captured[/] via tier {cap.tier} → {out_dir}  "
                  f"({len(cap.text)} chars text, {len(cap.screenshots)} shots, "
                  f"{len(cap.downloaded_images)} images)")


@main.command()
@click.argument("source", required=False)
@click.option("--manual", "manual_dir", default=None, help="Folder of images + description.md.")
@click.option("-o", "--out", "out_spec", default="spec.json", help="Output ProductSpec path.")
@click.option("--lang", default="en", help="Primary language of the source.")
@click.option("--target-lang", default=None, help="Secondary language for 中英对照.")
@_llm_opts
def extract(source, manual_dir, out_spec, lang, target_lang, llm, model):
    """[2] Turn raw capture (or manual uploads) into a ProductSpec via the LLM."""
    s = load_settings(llm=llm, model=model)
    if manual_dir:
        from .extract.manual import extract_manual

        spec = extract_manual(manual_dir, settings=s, primary=lang, secondary=target_lang)
    else:
        if not source:
            raise click.UsageError("Pass a work/ dir, or use --manual DIR.")
        from .extract.extractor import extract_from_capture

        spec = extract_from_capture(source, settings=s, primary=lang, secondary=target_lang)
    dump_spec(spec, out_spec)
    console.print(f"[green]wrote[/] {out_spec}  ({len(spec.variants)} variants, {len(spec.features)} features)")


@main.command()
@click.argument("spec_path")
@click.option("--translate/--no-translate", default=True, help="Fill 中英对照 secondary text.")
@click.option("--icons/--no-icons", default=True, help="Match features to real icon assets.")
@click.option("--cutout/--no-cutout", default=False, help="Background-remove product photos.")
@click.option("--classify/--no-classify", default=True, help="Tag image roles.")
@click.option("--copywrite/--no-copywrite", default=False, help="Draft missing copy (grounded).")
@click.option("--icon-dir", default=None, help="Real icon library to match features against.")
@click.option("--assets-dir", default=None, help="Where assets live (default: spec dir).")
@_llm_opts
def enrich(spec_path, translate, icons, cutout, classify, copywrite, icon_dir, assets_dir, llm, model):
    """[3] Optional enrichment: translate, classify images, match icons, cut out photos."""
    from .enrich import run_enrich

    s = load_settings(llm=llm, model=model)
    spec = load_spec(spec_path)
    spec = run_enrich(
        spec, settings=s, assets_dir=assets_dir or os.path.dirname(os.path.abspath(spec_path)),
        translate=translate, icons=icons, cutout=cutout, classify=classify,
        copywrite=copywrite, icon_dir=icon_dir,
    )
    dump_spec(spec, spec_path)
    console.print(f"[green]enriched[/] {spec_path}")


@main.command()
@click.argument("spec_path")
@click.option("-o", "--out", "out_html", default="page.html", help="Output HTML path.")
@click.option("--theme", default="editorial", help="Theme name (built-in) or path to a .toml.")
@click.option("--assets-dir", default=None, help="Where assets live (default: spec dir).")
def compose(spec_path, out_html, theme, assets_dir):
    """[4] ProductSpec + theme → a single self-contained HTML page."""
    from .compose.composer import compose_to_file

    spec = load_spec(spec_path)
    assets = assets_dir or os.path.dirname(os.path.abspath(spec_path))
    compose_to_file(spec, out_html, assets_dir=assets, theme_path=_resolve_theme(theme))
    console.print(f"[green]composed[/] {out_html}")


@main.command()
@click.argument("html_path")
@click.option("-o", "--out", "out_dir", default="output", help="Output dir for PNGs.")
@click.option("--width", default=None, type=int, help="Page width px (default 750).")
@click.option("--scale", default=None, type=float, help="Device scale factor (default 2).")
@click.option("--no-panels", is_flag=True, help="Only the full image, no panel slices.")
@click.option("--engine", type=click.Choice(["auto", "playwright", "chrome"]), default="auto")
def render(html_path, out_dir, width, scale, no_panels, engine):
    """[5] Render HTML → cropped full PNG + upload panels."""
    from .render.renderer import render as do_render

    s = load_settings(width=width, scale=scale)
    eng = "chrome_cli" if engine == "chrome" else engine
    res = do_render(
        html_path, out_dir, width=s.width, scale=s.scale, cap=s.max_screenshot_px,
        make_panels=not no_panels, engine=eng,
    )
    console.print(f"[green]rendered[/] {res['full']} {tuple(res['size'])} + {len(res['panels'])} panels")


@main.command()
@click.argument("out_dir")
@click.argument("spec_path")
@click.option("--report", default=None, help="Write the JSON report here.")
@_llm_opts
def verify(out_dir, spec_path, report, llm, model):
    """[6] Multi-lens QA over the rendered image + spec (fidelity/layout/localization)."""
    from .verify.reviewer import verify as do_verify

    s = load_settings(llm=llm, model=model)
    spec = load_spec(spec_path)
    rep = do_verify(out_dir, spec, settings=s,
                    assets_dir=os.path.dirname(os.path.abspath(spec_path)), report_path=report)
    status = "[green]PASS[/]" if rep.get("passed") else "[red]ISSUES[/]"
    console.print(f"{status}  {len(rep.get('findings', []))} findings"
                  + (f" → {report}" if report else ""))


@main.command()
@click.argument("source", required=False)
@click.option("--spec", "spec_path", default=None, help="Skip acquire/extract; use this spec.")
@click.option("--manual", "manual_dir", default=None, help="Manual uploads dir.")
@click.option("--out", "out_dir", default="out", help="Working/output dir.")
@click.option("--theme", default="editorial")
@click.option("--lang", default="en")
@click.option("--target-lang", default=None, help="Secondary language for 中英对照.")
@click.option("--icon-dir", default=None, help="Real icon library for feature matching.")
@click.option("--assets-dir", default=None)
@click.option("--no-enrich", is_flag=True, help="Skip the enrich stage.")
@click.option("--no-archive", is_flag=True, help="Don't save to the generation library.")
@click.option("--no-verify", is_flag=True)
@_llm_opts
@click.pass_context
def run(ctx, source, spec_path, manual_dir, out_dir, theme, lang, target_lang, icon_dir,
        assets_dir, no_enrich, no_archive, no_verify, llm, model):
    """End-to-end: (acquire→extract | manual | --spec) → enrich → compose → render → verify."""
    os.makedirs(out_dir, exist_ok=True)
    generated = not spec_path  # only enrich specs we just extracted, not user-supplied ones
    if not spec_path:
        spec_path = os.path.join(out_dir, "spec.json")
        if manual_dir:
            ctx.invoke(extract, source=None, manual_dir=manual_dir, out_spec=spec_path,
                       lang=lang, target_lang=target_lang, llm=llm, model=model)
        elif _looks_like_dir(source):
            # already-acquired work dir
            ctx.invoke(extract, source=source, manual_dir=None, out_spec=spec_path,
                       lang=lang, target_lang=target_lang, llm=llm, model=model)
        else:
            _acquire_then_extract(ctx, source, out_dir, spec_path, lang, target_lang, llm, model)
    if generated and not no_enrich:
        ctx.invoke(enrich, spec_path=spec_path, translate=bool(target_lang), icons=bool(icon_dir),
                   cutout=False, classify=True, copywrite=False, icon_dir=icon_dir,
                   assets_dir=assets_dir, llm=llm, model=model)
    html = os.path.join(out_dir, "page.html")
    ctx.invoke(compose, spec_path=spec_path, out_html=html, theme=theme, assets_dir=assets_dir)
    ctx.invoke(render, html_path=html, out_dir=os.path.join(out_dir, "output"),
               width=None, scale=None, no_panels=False, engine="auto")
    if not no_archive:
        from . import library

        entry = library.archive(os.path.join(out_dir, "output"), load_spec(spec_path),
                                mode="cli", theme=theme, target_lang=target_lang)
        console.print(f"[dim]archived to library:[/] {entry['id']} (v{entry['version']})")
    if not no_verify:
        try:
            ctx.invoke(verify, out_dir=os.path.join(out_dir, "output"), spec_path=spec_path,
                       report=os.path.join(out_dir, "verify.json"), llm=llm, model=model)
        except Exception as e:  # verify is best-effort
            console.print(f"[yellow]verify skipped:[/] {e}")
    console.print(f"[bold green]done[/] → {out_dir}/output/full.png")


def _acquire_then_extract(ctx, url, out_dir, spec_path, lang, target_lang, llm, model):
    if not url:
        raise click.UsageError("Provide a URL, --spec, or --manual.")
    work = os.path.join(out_dir, "work")
    ctx.invoke(acquire, url=url, out_dir=work, tier=None, no_images=False)
    ctx.invoke(extract, source=work, manual_dir=None, out_spec=spec_path,
               lang=lang, target_lang=target_lang, llm=llm, model=model)


def _looks_like_dir(source) -> bool:
    return bool(source) and os.path.isdir(source)


# -- helpers --------------------------------------------------------------------------------
def _resolve_theme(theme: str):
    """A built-in theme name or a path to a .toml."""
    if theme.endswith(".toml") and os.path.exists(theme):
        return theme
    from pathlib import Path

    builtin = Path(__file__).parent / "compose" / "themes" / f"{theme}.toml"
    if builtin.exists():
        return str(builtin)
    if os.path.exists(theme):
        return theme
    console.print(f"[yellow]theme {theme!r} not found, using defaults[/]")
    return None


if __name__ == "__main__":
    sys.exit(main())
