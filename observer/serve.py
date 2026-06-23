#!/usr/bin/env python3
"""Observer server for the React/R3F app with legacy fallbacks."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DIST = Path(_ROOT) / "dist"
_SOURCE = Path(_ROOT)


class ObserverHandler(SimpleHTTPRequestHandler):
    def _gpu_headers(self) -> None:
        # Enable SharedArrayBuffer (used by WebGL GPU buffer transfers) in
        # sandboxed Chromium contexts. credentialless allows cross-origin
        # fetch to the runtime at :8888 without requiring CORP headers there.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        self.send_header("Access-Control-Allow-Origin", "*")

    def _serve_file(self, file_path: Path) -> None:
        if not file_path.exists() or not file_path.is_file():
            self.send_error(404, "File not found")
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self._gpu_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/") or "/"

        if path in ("/maku", "/classic"):
            return self._serve_file(_SOURCE / "maku.html" if path == "/maku" else _SOURCE / "stage.html")
        if path in ("/stage", "/one", "/"):
            if (_DIST / "index.html").exists():
                return self._serve_file(_DIST / "index.html")
            return self._serve_file(_SOURCE / "index.html")
        if path.startswith("/assets/"):
            dist_asset = _DIST / path.lstrip("/")
            if dist_asset.exists():
                return self._serve_file(dist_asset)
            return self._serve_file(_SOURCE / path.lstrip("/"))
        candidate = _DIST / path.lstrip("/")
        if candidate.exists():
            return self._serve_file(candidate)
        candidate = _SOURCE / path.lstrip("/")
        if candidate.exists():
            return self._serve_file(candidate)
        if (_DIST / "index.html").exists():
            return self._serve_file(_DIST / "index.html")
        return self._serve_file(_SOURCE / "stage.html")


def main() -> None:
    os.chdir(_ROOT)
    port = int(os.getenv("OBSERVER_PORT", "3000"))
    server = HTTPServer(("0.0.0.0", port), ObserverHandler)
    print(
        f"observer listening on :{port}  (/stage and /one → React app, /classic → stage.html, /maku → maku.html)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
