"""Optional localhost POST sink — an alternative tier-3 channel for browser-EXTENSION users.

The pattern (from the source project): from inside a page that already has Cloudflare
clearance, `fetch()` the same-origin asset → POST the bytes to http://127.0.0.1:<port>/<path>;
this script writes the body to disk. An HTTPS page may POST to localhost (it's a
"potentially trustworthy" origin), and CORS doesn't block *sending* a body. Useful when you
can't attach via CDP but can run a snippet / extension in your logged-in browser.

Run:  python -m pagewright.acquire.localserver --dir ./capture --port 8799
Then, in your browser console (on the cleared origin):

    const buf = await (await fetch(ASSET_URL)).arrayBuffer();
    await fetch("http://127.0.0.1:8799/images/hero.jpg", {method:"POST", body: buf});
"""

from __future__ import annotations

import argparse
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def make_handler(root: str):
    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")

        def do_OPTIONS(self):  # CORS preflight
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length) if length else b""
            rel = self.path.lstrip("/") or "body.bin"
            dest = os.path.normpath(os.path.join(root, rel))
            if not dest.startswith(os.path.abspath(root)):
                self.send_response(403)
                self._cors()
                self.end_headers()
                return
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "wb") as f:
                f.write(body)
            self.send_response(200)
            self._cors()
            self.end_headers()
            self.wfile.write(f"wrote {len(body)} bytes to {rel}\n".encode())

        def log_message(self, *a):  # quieter
            pass

    return Handler


def serve(root: str, port: int = 8799):
    root = os.path.abspath(root)
    os.makedirs(root, exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(root))
    print(f"POST sink on http://127.0.0.1:{port}  →  {root}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


def main():
    ap = argparse.ArgumentParser(description="Pagewright localhost POST sink")
    ap.add_argument("--dir", default="capture")
    ap.add_argument("--port", type=int, default=8799)
    a = ap.parse_args()
    serve(a.dir, a.port)


if __name__ == "__main__":
    main()
