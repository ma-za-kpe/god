#!/usr/bin/env python3
"""Static observer server with /maku alias for the creator console and /stage for the stream overlay."""

from __future__ import annotations

import os
from http.server import HTTPServer, SimpleHTTPRequestHandler

_ROOT = os.path.dirname(os.path.abspath(__file__))


class ObserverHandler(SimpleHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in ("/maku", "/maku/"):
            self.path = "/maku.html"
        elif self.path in ("/stage", "/stage/"):
            self.path = "/stage.html"
        return super().do_GET()


def main() -> None:
    os.chdir(_ROOT)
    port = int(os.getenv("OBSERVER_PORT", "3000"))
    server = HTTPServer(("0.0.0.0", port), ObserverHandler)
    print(f"observer listening on :{port}  (/maku → maku.html, /stage → stage.html)", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
