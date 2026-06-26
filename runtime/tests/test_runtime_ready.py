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
    package_name = f"runtime_src_ready_{uuid.uuid4().hex}"
    package = types.ModuleType(package_name)
    package.__path__ = [str(src_dir)]
    sys.modules[package_name] = package

    module_name = f"{package_name}.main"
    spec = importlib.util.spec_from_file_location(
        module_name,
        src_dir / "main.py",
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_fish_ready_uses_configured_timeout(monkeypatch):
    main = _load_runtime_main()
    captured = {}

    class _Response:
        status_code = 200
        content = b"RIFF"

    class _Client:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            captured["url"] = url
            captured["payload"] = json
            return _Response()

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_HEALTH_TIMEOUT_SECONDS", "75")
    monkeypatch.setattr(main.httpx, "AsyncClient", _Client)

    result = await main._fish_synthesis_ready()

    assert result["ok"] is True
    assert result["timeout_seconds"] == 75.0
    assert captured["timeout"] == 75.0
    assert captured["url"] == "http://fish-speech:7860/v1/tts"
    assert captured["payload"]["references"][0]["audio"]


@pytest.mark.asyncio
async def test_fish_ready_reports_exception_class_for_empty_message(monkeypatch):
    main = _load_runtime_main()

    class _EmptyMessageError(Exception):
        def __str__(self):
            return ""

    class _Client:
        def __init__(self, timeout):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json):
            raise _EmptyMessageError()

    monkeypatch.setenv("TTS_ENDPOINT", "http://fish-speech:7860")
    monkeypatch.setenv("VOICE_HEALTH_TIMEOUT_SECONDS", "30")
    monkeypatch.setattr(main.httpx, "AsyncClient", _Client)

    result = await main._fish_synthesis_ready()

    assert result["ok"] is False
    assert result["reason"] == "_EmptyMessageError"
    assert result["timeout_seconds"] == 30.0
