#!/usr/bin/env python3
"""Observer server for the React/R3F app with legacy fallbacks."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

_ROOT = os.path.dirname(os.path.abspath(__file__))
_DIST = Path(_ROOT) / "dist"
_SOURCE = Path(_ROOT)
_DIST_ROOT = _DIST.resolve()
_SOURCE_ROOT = _SOURCE.resolve()
_ALLOW_ORIGIN = os.getenv("OBSERVER_ALLOW_ORIGIN", "").strip()
_OLLAMA_PROXY_URL = os.getenv("OLLAMA_PROXY_URL", "http://host.docker.internal:11434").rstrip("/")


def _contained_path(root: Path, request_path: str) -> Path | None:
    try:
        candidate = (root / request_path.lstrip("/")).resolve()
        candidate.relative_to(root)
    except (OSError, ValueError):
        return None
    return candidate


class ObserverHandler(SimpleHTTPRequestHandler):
    def _gpu_headers(self) -> None:
        # Enable SharedArrayBuffer (used by WebGL GPU buffer transfers) in
        # sandboxed Chromium contexts. credentialless allows cross-origin
        # fetch to the runtime at :8888 without requiring CORP headers there.
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "credentialless")
        if _ALLOW_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", _ALLOW_ORIGIN)

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

    def _proxy_ollama(self) -> None:
        path = unquote(urlsplit(self.path).path)
        upstream_path = path.replace("/ollama", "", 1) or "/"
        query = urlsplit(self.path).query
        upstream_url = f"{_OLLAMA_PROXY_URL}{upstream_path}"
        if query:
            upstream_url = f"{upstream_url}?{query}"

        body = None
        if self.command in ("POST", "PUT", "PATCH"):
            length = int(self.headers.get("Content-Length", "0") or "0")
            body = self.rfile.read(length) if length > 0 else b""

        headers = {
            "Content-Type": self.headers.get("Content-Type", "application/json"),
            "Accept": self.headers.get("Accept", "application/json"),
        }
        request = Request(upstream_url, data=body, headers=headers, method=self.command)
        try:
            with urlopen(request, timeout=120) as response:
                data = response.read()
                self.send_response(response.status)
                self.send_header("Content-Type", response.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self._gpu_headers()
                self.end_headers()
                self.wfile.write(data)
        except Exception as exc:
            data = (f'{{"error":"ollama proxy failed","detail":{str(exc)!r}}}').encode("utf-8")
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self._gpu_headers()
            self.end_headers()
            self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
        self._gpu_headers()
        self.end_headers()

    def do_GET(self) -> None:
        path = unquote(urlsplit(self.path).path).rstrip("/") or "/"
        if "\x00" in path:
            self.send_error(400, "Invalid path")
            return

        if path == "/ollama" or path.startswith("/ollama/"):
            return self._proxy_ollama()

        if path in ("/maku", "/classic"):
            return self._serve_file(_SOURCE / "maku.html" if path == "/maku" else _SOURCE / "stage.html")
        if path in ("/stage", "/one", "/"):
            if (_DIST / "index.html").exists():
                return self._serve_file(_DIST / "index.html")
            return self._serve_file(_SOURCE / "index.html")
        if path.startswith("/assets/"):
            dist_asset = _contained_path(_DIST_ROOT, path)
            if dist_asset and dist_asset.exists():
                return self._serve_file(dist_asset)
            source_asset = _contained_path(_SOURCE_ROOT, path)
            if source_asset:
                return self._serve_file(source_asset)
            self.send_error(404, "File not found")
            return
        candidate = _contained_path(_DIST_ROOT, path)
        if candidate and candidate.exists():
            return self._serve_file(candidate)
        candidate = _contained_path(_SOURCE_ROOT, path)
        if candidate and candidate.exists():
            return self._serve_file(candidate)
        if (_DIST / "index.html").exists():
            return self._serve_file(_DIST / "index.html")
        return self._serve_file(_SOURCE / "stage.html")

    def do_POST(self) -> None:
        path = unquote(urlsplit(self.path).path).rstrip("/") or "/"
        if path == "/ollama" or path.startswith("/ollama/"):
            return self._proxy_ollama()
        self.send_error(404, "File not found")


def main() -> None:
    os.chdir(_ROOT)
    port = int(os.getenv("OBSERVER_PORT", "3000"))
    host = os.getenv("OBSERVER_HOST", "127.0.0.1")
    server = HTTPServer((host, port), ObserverHandler)
    print(
        f"observer listening on {host}:{port}  (/stage and /one -> React app, /classic -> stage.html, /maku -> maku.html)",
        flush=True,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
