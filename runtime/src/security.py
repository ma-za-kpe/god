"""
security.py — Production vs local-dev gates for dangerous endpoints.
"""

from __future__ import annotations

import hmac
import os

from fastapi.responses import JSONResponse


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes")


def local_dev_mode() -> bool:
    return _truthy("LOCAL_DEV_MODE", "false")


def insecure_local_endpoints_allowed() -> bool:
    """Endpoints that accept private keys in request bodies."""
    return local_dev_mode() and _truthy("ALLOW_INSECURE_LOCAL_ENDPOINTS", "false")


def verify_creator_token(header_token: str | None) -> bool:
    """Require X-Creator-Token for creator/admin HTTP actions.

    Local tokenless mode is available only when explicitly opted in. This keeps
    production and accidentally exposed Docker stacks deny-by-default.
    """
    expected = (
        os.getenv("CREATOR_GENESIS_TOKEN", "").strip() or os.getenv("CREATOR_TOKEN", "").strip()
    )
    if not expected:
        return local_dev_mode() and _truthy("ALLOW_TOKENLESS_CREATOR", "false")
    return bool(header_token) and hmac.compare_digest(header_token.strip(), expected)


def deny_insecure_endpoint(endpoint: str) -> JSONResponse | None:
    if insecure_local_endpoints_allowed():
        return None
    return JSONResponse(
        status_code=403,
        content={
            "error": f"{endpoint} disabled in production",
            "hint": "Set ALLOW_INSECURE_LOCAL_ENDPOINTS=true only on trusted local machines",
        },
    )


def deny_creator_action(header_token: str | None) -> JSONResponse | None:
    if verify_creator_token(header_token):
        return None
    return JSONResponse(
        status_code=403,
        content={
            "error": "Creator authentication required",
            "hint": "Set X-Creator-Token header matching CREATOR_GENESIS_TOKEN (or legacy CREATOR_TOKEN)",
        },
    )
