"""Shared readiness and probe helpers for runtime adapters."""

from __future__ import annotations

import json
import http.client
import socket
from typing import Any
from urllib.error import URLError
from urllib.parse import urlparse


def probe_url(url: str | None, timeout: float = 1.5) -> dict[str, Any]:
    if not url:
        return {"ok": False, "probe": "skipped", "reason": "not_configured"}
    try:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            return {
                "ok": False,
                "probe": "http",
                "url": url,
                "reason": "unsupported_scheme",
            }
        if not parsed_url.hostname:
            return {"ok": False, "probe": "http", "url": url, "reason": "missing_host"}

        path = parsed_url.path or "/"
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"

        connection_cls = (
            http.client.HTTPSConnection
            if parsed_url.scheme == "https"
            else http.client.HTTPConnection
        )
        conn = connection_cls(parsed_url.hostname, parsed_url.port, timeout=timeout)
        try:
            conn.request("GET", path)
            response = conn.getresponse()
            body = response.read(256)
            parsed = None
            try:
                parsed = json.loads(body.decode("utf-8")) if body else None
            except Exception:
                parsed = None
            return {
                "ok": 200 <= response.status < 400,
                "probe": "http",
                "url": url,
                "status_code": int(response.status),
                "body": parsed,
            }
        finally:
            conn.close()
    except URLError as exc:
        return {"ok": False, "probe": "http", "url": url, "reason": str(exc)}
    except Exception as exc:
        return {"ok": False, "probe": "http", "url": url, "reason": str(exc)}


def probe_tcp(host: str | None, port: int | None, timeout: float = 1.5) -> dict[str, Any]:
    if not host or not port:
        return {"ok": False, "probe": "skipped", "reason": "not_configured"}
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return {"ok": True, "probe": "tcp", "host": host, "port": int(port)}
    except Exception as exc:
        return {"ok": False, "probe": "tcp", "host": host, "port": int(port), "reason": str(exc)}
