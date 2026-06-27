"""Public IPFS proxy policy tests."""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types
import uuid

import pytest


def _runtime_src_dir() -> pathlib.Path:
    for candidate in (
        pathlib.Path("/app/src"),
        pathlib.Path(__file__).resolve().parents[1] / "src",
        pathlib.Path.cwd() / "src",
    ):
        if (candidate / "main.py").is_file():
            return candidate
    raise FileNotFoundError("runtime src/main.py not found")


def _load_runtime_main():
    src_dir = _runtime_src_dir()
    package_name = f"runtime_src_ipfs_{uuid.uuid4().hex}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(src_dir)]
    sys.modules[package_name] = package

    module_name = f"{package_name}.main"
    spec = importlib.util.spec_from_file_location(module_name, src_dir / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_ipfs_video_proxy_uses_video_limit_and_range(monkeypatch):
    main = _load_runtime_main()
    payload = b"\x00\x00\x00\x18ftypmp42" + (b"v" * 64)
    captured = {}

    async def fake_fetch(cid: str, *, max_bytes: int):
        captured["cid"] = cid
        captured["max_bytes"] = max_bytes
        return 200, payload

    monkeypatch.setattr(main, "_fetch_public_ipfs", fake_fetch)

    response = await main.ipfs_video_proxy("bafyvideo", range_header="bytes=4-11")

    assert captured == {
        "cid": "bafyvideo",
        "max_bytes": main.PUBLIC_IPFS_VIDEO_MAX_BYTES,
    }
    assert response.status_code == 206
    assert response.body == payload[4:12]
    assert response.headers["content-range"] == f"bytes 4-11/{len(payload)}"
    assert response.headers["accept-ranges"] == "bytes"
    assert response.media_type == "video/mp4"


@pytest.mark.asyncio
async def test_ipfs_portrait_proxy_keeps_small_limit(monkeypatch):
    main = _load_runtime_main()
    payload = b"\x89PNG" + (b"i" * 64)
    captured = {}

    async def fake_fetch(cid: str, *, max_bytes: int):
        captured["cid"] = cid
        captured["max_bytes"] = max_bytes
        return 200, payload

    monkeypatch.setattr(main, "_fetch_public_ipfs", fake_fetch)

    response = await main.ipfs_proxy("bafyportrait")

    assert captured == {
        "cid": "bafyportrait",
        "max_bytes": main.PUBLIC_IPFS_MAX_BYTES,
    }
    assert response.status_code == 200
    assert response.body == payload
    assert response.media_type == "image/png"
