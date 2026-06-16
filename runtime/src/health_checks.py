"""Shared readiness and probe helpers for runtime adapters."""

from __future__ import annotations

import json
import socket
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


def probe_url(url: str | None, timeout: float = 1.5) -> dict[str, Any]:
    if not url:
        return {"ok": False, "probe": "skipped", "reason": "not_configured"}
    try:
        with urlopen(url, timeout=timeout) as response:
            body = response.read(256)
            parsed = None
            try:
                parsed = json.loads(body.decode("utf-8")) if body else None
            except Exception:
                parsed = None
            return {
                "ok": 200 <= getattr(response, "status", 200) < 400,
                "probe": "http",
                "url": url,
                "status_code": int(getattr(response, "status", 200)),
                "body": parsed,
            }
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
