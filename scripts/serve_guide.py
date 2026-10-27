#!/usr/bin/env python3
"""Serve the project archive and the printable guides as a download site.

Usage:
    python3 scripts/serve_guide.py          # binds 0.0.0.0:8000
    PORT=8080 python3 scripts/serve_guide.py

The live preview proxy can reach it because it listens on 0.0.0.0 and uses
relative URLs only. Downloadable files are sent as attachments.
"""

from __future__ import annotations

import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ADMIN_PDF = "admin-channel-guide.pdf"
CHANNEL_PDF = "channel-admin-guide.pdf"
ADMIN_MD = "admin-channel-guide.md"
CHANNEL_MD = "channel-admin-guide.md"
PROJECT_ZIP = "tizgam-seminar-bot-final.zip"
ZIP_PATH = ROOT / "dist" / PROJECT_ZIP

UTF8_NAMES = {
    ADMIN_PDF: "راهنمای-ادمین-ربات.pdf",
    CHANNEL_PDF: "راهنمای-مدیران-کانالها.pdf",
    PROJECT_ZIP: PROJECT_ZIP,
}

ROUTES = {
    "/": (DOCS / "index.html", "text/html; charset=utf-8", None),
    "/index.html": (DOCS / "index.html", "text/html; charset=utf-8", None),
    f"/{ADMIN_PDF}": (DOCS / ADMIN_PDF, "application/pdf", ADMIN_PDF),
    f"/{CHANNEL_PDF}": (DOCS / CHANNEL_PDF, "application/pdf", CHANNEL_PDF),
    f"/{ADMIN_MD}": (DOCS / ADMIN_MD, "text/markdown; charset=utf-8", None),
    f"/{CHANNEL_MD}": (DOCS / CHANNEL_MD, "text/markdown; charset=utf-8", None),
    f"/{PROJECT_ZIP}": (ZIP_PATH, "application/zip", PROJECT_ZIP),
}


def disposition_for(download_name: str) -> str:
    ascii_name = {
        ADMIN_PDF: "bot-admin-guide.pdf",
        CHANNEL_PDF: "channel-admins-guide.pdf",
        PROJECT_ZIP: PROJECT_ZIP,
    }[download_name]
    return (
        f'attachment; filename="{ascii_name}"; '
        f"filename*=UTF-8''{quote(UTF8_NAMES[download_name])}"
    )


class GuideHandler(BaseHTTPRequestHandler):
    server_version = "NikmaneshGuide/1.1"

    def _send(self, status: int, body: bytes, content_type: str, disposition: str | None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _handle(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send(200, b"OK\n", "text/plain; charset=utf-8", None)
            return
        if path == "/favicon.ico":
            self._send(204, b"", "image/x-icon", None)
            return
        route = ROUTES.get(path)
        if route is None:
            body = "<h1 dir='rtl'>فایل پیدا نشد</h1>".encode()
            self._send(404, body, "text/html; charset=utf-8", None)
            return
        file_path, content_type, download_marker = route
        if not file_path.is_file():
            self._send(404, b"Not found", "text/plain; charset=utf-8", None)
            return
        disposition = disposition_for(download_marker) if download_marker else None
        self._send(200, file_path.read_bytes(), content_type, disposition)

    def do_GET(self) -> None:  # noqa: N802
        self._handle()

    def do_HEAD(self) -> None:  # noqa: N802
        self._handle()

    def log_message(self, fmt: str, *args) -> None:
        print(f"[guide] {self.address_string()} - {fmt % args}", flush=True)


def main() -> None:
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), GuideHandler)
    print(f"Serving project downloads from {DOCS} on http://0.0.0.0:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
