"""Desktop entry point — what the double-clickable .app/.exe runs.

Starts the local server on a free port in a background thread, then opens a native window
(pywebview, using the OS's built-in webview — no bundled browser) pointed at it. No terminal,
no Python install, no Docker for the end user.
"""

from __future__ import annotations

import socket
import threading
import time


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _wait_up(host: str, port: int, timeout: float = 15.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def main():
    import os

    from .server import create_app

    # Headless mode (CI / smoke-testing the bundle): run the server in the foreground, no window.
    if os.environ.get("PAGEWRIGHT_HEADLESS"):
        import uvicorn

        port = int(os.environ.get("PAGEWRIGHT_PORT", "8765"))
        print(f"[pagewright] headless server on http://127.0.0.1:{port}", flush=True)
        uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
        return

    host, port = "127.0.0.1", _free_port()

    def run():
        import uvicorn

        uvicorn.run(create_app(), host=host, port=port, log_level="warning")

    threading.Thread(target=run, daemon=True).start()
    _wait_up(host, port)

    import webview

    webview.create_window("Pagewright", f"http://{host}:{port}", width=1180, height=860,
                          min_size=(900, 640))
    webview.start()


if __name__ == "__main__":
    main()
