# Security

Pagewright is a **local-first** tool: it runs on your machine, and the only data that leaves it
are the LLM API calls you explicitly configure. This document covers the threat model, the
hardening already in place, and how to report issues.

## Reporting a vulnerability
Please open a private security advisory on GitHub (Security → Report a vulnerability) or email
the maintainers rather than filing a public issue. We aim to respond within a few days.

## Secrets & keys
- **No keys are bundled or committed.** You supply your own API key via `.env`, an environment
  variable, or the desktop app's Settings screen.
- The desktop app stores settings (including the key) at `~/.pagewright/settings.json` in plain
  text — standard for local developer tools. Protect that file with normal OS file permissions;
  it is never uploaded anywhere by Pagewright.
- `.gitignore` excludes `.env`, virtualenvs, build output, and `~/.pagewright` is outside the
  repo. The example ships placeholder keys only (`sk-ant-...`).

## Rendered-page injection (handled)
Spec text can originate from an LLM that read an **untrusted web page**, then gets composed into
HTML and screenshotted by a headless browser. To prevent injected `<script>` / `onerror` / etc.
from executing during rendering, all spec-derived text is passed through `safe_inline`
([`compose/composer.py`](pagewright/compose/composer.py)) — it HTML-escapes everything and then
re-permits only a small whitelist of inline tags (`b i br sub sup em strong span[class]`). Theme
color/font tokens use `|safe` but come from local `.toml` files you control, not from the web.

## Acquisition / SSRF
The fetcher retrieves URLs you provide (tiers 1–3). On your own machine this is the intended
behavior. **Do not expose the web server to untrusted users** — a remote user could otherwise
drive it to fetch internal/cloud-metadata URLs (SSRF). Mitigations in place:
- `pagewright serve` and the desktop server bind to `127.0.0.1` only; `serve` warns if you
  override the host.
- `robots.txt` is honored by default (`PAGEWRIGHT_RESPECT_ROBOTS=1`) and requests are
  rate-limited.
- Tier-3 attaches to a browser **you** launched and authenticated — Pagewright never solves a
  CAPTCHA or bypasses authentication.

## Local web server
- Binds `127.0.0.1`; no authentication (it is single-user, local-only).
- File downloads are restricted to a job's own temp output dir; the filename is reduced to its
  basename (no path traversal).
- Uploads are capped per-file and per-request to avoid runaway disk use.
- The optional `acquire/localserver.py` POST sink also binds localhost and writes only within a
  chosen directory (path-traversal guarded).

## Code execution
- The renderer launches a browser via `subprocess` with an **argument list** (no `shell=True`),
  so there is no shell-injection surface. Browser paths are a fixed allow-list.
- No `eval`/`exec` of untrusted input anywhere in the codebase.

## Dependencies
Runtime deps are mainstream and minimal (pydantic, jinja2, pillow, httpx, click). LLM SDKs,
Playwright, and rembg are **optional extras** — install only what you use.

## Third-party content
Material fetched from websites (icons, photos, copy) belongs to its owners and is **not**
redistributed by this project. Use Pagewright only on content you are authorized to access.
