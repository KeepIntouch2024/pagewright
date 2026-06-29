"""Local web server behind the desktop app (and `pagewright serve`).

A tiny FastAPI app: serves the single-page UI, stores the user's LLM key locally, and runs the
pipeline in a background thread while the UI polls for progress. Everything runs on the user's
machine — uploads and keys never leave it (except the LLM calls the user configured).
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import traceback
import uuid
from pathlib import Path
from typing import Optional

from . import settings_store

try:
    from fastapi import FastAPI, File, Form, UploadFile
    from fastapi.responses import FileResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "The web UI needs FastAPI: pip install 'pagewright[app]' (or [desktop])."
    ) from e

_JOBS: dict[str, dict] = {}
_STATIC = Path(__file__).parent / "static"

# upload limits (the server is local/single-user, but bound resources anyway)
MAX_FILES = 30
MAX_FILE_BYTES = 25 * 1024 * 1024       # 25 MB per image
MAX_TOTAL_BYTES = 120 * 1024 * 1024     # 120 MB per request
MAX_DESC_CHARS = 40000


def _bounded_copy(src, dest, limit: int) -> int:
    """Copy at most `limit` bytes; truncate beyond it (defends against runaway uploads)."""
    written = 0
    with open(dest, "wb") as out:
        while True:
            chunk = src.read(1 << 20)
            if not chunk:
                break
            if written + len(chunk) > limit:
                out.write(chunk[: limit - written])
                break
            out.write(chunk)
            written += len(chunk)
    return written


def create_app():
    app = FastAPI(title="Pagewright")

    @app.get("/api/settings")
    def get_settings():
        return settings_store.public()

    @app.post("/api/settings")
    async def post_settings(payload: dict):
        # don't overwrite a stored key with the masked placeholder
        if payload.get("api_key", "").startswith("•"):
            payload.pop("api_key", None)
        settings_store.save(payload)
        return settings_store.public()

    @app.get("/api/health")
    def health():
        from ..render.renderer import _find_chrome, _has_playwright

        return {"renderer": bool(_find_chrome()) or _has_playwright(),
                "playwright": _has_playwright(),
                "configured": bool(settings_store.load().get("llm") and settings_store.load().get("api_key"))}

    @app.post("/api/generate")
    async def generate(
        mode: str = Form("manual"),
        description: str = Form(""),
        url: str = Form(""),
        target_lang: str = Form(""),
        theme: str = Form("editorial"),
        files: list[UploadFile] = File(default=[]),
    ):
        job_id = uuid.uuid4().hex[:12]
        work = Path(tempfile.mkdtemp(prefix=f"pw_{job_id}_"))
        imgs = work / "images"
        imgs.mkdir(parents=True, exist_ok=True)
        saved = []
        total = 0
        for f in files[:MAX_FILES]:
            dest = imgs / Path(f.filename or "upload").name  # basename only — no traversal
            written = _bounded_copy(f.file, dest, MAX_FILE_BYTES)
            total += written
            saved.append(str(dest))
            if total > MAX_TOTAL_BYTES:
                break
        if len(description) > MAX_DESC_CHARS:
            description = description[:MAX_DESC_CHARS]
        if description.strip():
            (work / "description.md").write_text(description, encoding="utf-8")

        _JOBS[job_id] = {"status": "running", "progress": ["queued"], "work": str(work),
                         "error": None, "result": None}
        t = threading.Thread(
            target=_run_job,
            args=(job_id, mode, str(work), url, target_lang or None, theme),
            daemon=True,
        )
        t.start()
        return {"job_id": job_id}

    @app.get("/api/jobs/{job_id}")
    def job_status(job_id: str):
        job = _JOBS.get(job_id)
        if not job:
            return JSONResponse({"error": "unknown job"}, status_code=404)
        return {k: job[k] for k in ("status", "progress", "error", "result")}

    @app.get("/api/jobs/{job_id}/file/{name}")
    def job_file(job_id: str, name: str):
        job = _JOBS.get(job_id)
        if not job or not job.get("result"):
            return JSONResponse({"error": "not ready"}, status_code=404)
        out = Path(job["work"]) / "output" / Path(name).name
        if not out.exists():
            return JSONResponse({"error": "no such file"}, status_code=404)
        return FileResponse(str(out))

    app.mount("/", StaticFiles(directory=str(_STATIC), html=True), name="static")
    return app


def _progress(job_id: str, msg: str):
    j = _JOBS.get(job_id)
    if j:
        j["progress"].append(msg)


def _run_job(job_id: str, mode: str, work: str, url: Optional[str],
             target_lang: Optional[str], theme: str):
    from ..compose.composer import compose_to_file
    from ..render.renderer import render
    from ..spec import dump_spec

    job = _JOBS[job_id]
    try:
        settings = settings_store.to_settings()

        # progress is emitted as stable KEYS; the client localizes them (i18n).
        if mode == "url":
            if not url:
                raise ValueError("Please enter a product URL.")
            _progress(job_id, "fetch")
            from ..acquire.fetcher import acquire as do_acquire

            do_acquire(url, work, settings=settings, download_images=True)
            _progress(job_id, "read")
            from ..extract.extractor import extract_from_capture

            spec = extract_from_capture(work, settings=settings, primary="en", secondary=target_lang)
        else:  # manual
            _progress(job_id, "read")
            from ..extract.manual import extract_manual

            spec = extract_manual(work, settings=settings, primary="en", secondary=target_lang)

        if target_lang:
            spec.meta.language.secondary = target_lang
            _progress(job_id, "translate")
            from ..enrich.translate import translate

            spec = translate(spec, settings=settings, target_lang=target_lang)

        dump_spec(spec, os.path.join(work, "spec.json"))
        _progress(job_id, "compose")
        html = os.path.join(work, "page.html")
        compose_to_file(spec, html, assets_dir=work, theme_path=_theme_path(theme))

        _progress(job_id, "render")
        res = render(html, os.path.join(work, "output"), width=settings.width,
                     scale=settings.scale, cap=settings.max_screenshot_px, make_panels=True)

        panels = [Path(p).name for p in res["panels"]]
        job["result"] = {"full": "full.png", "panels": panels, "size": res["size"],
                         "spec": "spec.json"}
        job["status"] = "done"
        _progress(job_id, "done")
    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["progress"].append("error: " + str(e))
        job["traceback"] = traceback.format_exc()


def _theme_path(theme: str) -> Optional[str]:
    if theme.endswith(".toml") and os.path.exists(theme):
        return theme
    builtin = Path(__file__).resolve().parents[1] / "compose" / "themes" / f"{theme}.toml"
    return str(builtin) if builtin.exists() else None


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True):
    import uvicorn

    if host not in ("127.0.0.1", "localhost"):
        print(f"⚠️  Binding to {host} exposes Pagewright beyond this machine. The server has no "
              "authentication and can fetch arbitrary URLs (SSRF). Only do this on a trusted "
              "network. See SECURITY.md.")
    if open_browser:
        import webbrowser

        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")
