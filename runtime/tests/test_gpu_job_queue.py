"""GPU job queue policy tests."""

from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import sys
import types
import uuid

import pytest

from gpu import GPUJobQueue, GPUJobRejected, JobPriority


async def _wait_until(predicate, *, timeout_s: float = 1.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout_s
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


@pytest.mark.asyncio
async def test_live_voice_runs_before_queued_background_job():
    queue = GPUJobQueue()
    release_holder = asyncio.Event()
    order: list[str] = []

    async def holder():
        async with queue.acquire(JobPriority.LIVE_LLM, job_name="holder"):
            order.append("holder")
            await release_holder.wait()

    async def background():
        async with queue.acquire(JobPriority.LTX_BACKGROUND, job_name="ltx"):
            order.append("background")

    async def live_voice():
        async with queue.acquire(JobPriority.LIVE_VOICE, job_name="voice"):
            order.append("voice")

    holder_task = asyncio.create_task(holder())
    await _wait_until(lambda: queue.diagnostics()["current_job"] == "holder")

    background_task = asyncio.create_task(background())
    await _wait_until(
        lambda: queue.diagnostics()["queue_depth_by_priority"].get("ltx_background") == 1
    )

    voice_task = asyncio.create_task(live_voice())
    await _wait_until(lambda: queue.diagnostics()["queue_depth_by_priority"].get("live_voice") == 1)

    release_holder.set()
    await asyncio.gather(holder_task, background_task, voice_task)

    assert order == ["holder", "voice", "background"]
    diagnostics = queue.diagnostics()
    assert diagnostics["total_completed"] == 3
    assert diagnostics["queue_depth"] == 0


@pytest.mark.asyncio
async def test_live_voice_requests_active_background_cancellation():
    queue = GPUJobQueue()
    background_started = asyncio.Event()
    order: list[str] = []
    cancel_reason = ""

    async def background():
        nonlocal cancel_reason
        async with queue.acquire(JobPriority.LTX_BACKGROUND, job_name="ltx") as lease:
            order.append("background")
            background_started.set()
            await _wait_until(lambda: lease.cancellation_requested)
            cancel_reason = lease.cancel_reason

    async def live_voice():
        async with queue.acquire(JobPriority.LIVE_VOICE, job_name="voice"):
            order.append("voice")

    background_task = asyncio.create_task(background())
    await background_started.wait()
    voice_task = asyncio.create_task(live_voice())

    await asyncio.gather(background_task, voice_task)

    assert order == ["background", "voice"]
    assert cancel_reason == "live_voice_requested"
    diagnostics = queue.diagnostics()
    assert diagnostics["total_preemptions_requested"] == 1
    assert diagnostics["last_cancel_reason"] == "live_voice_requested"


@pytest.mark.asyncio
async def test_live_mode_rejects_new_background_jobs_but_allows_live_work():
    queue = GPUJobQueue()
    queue.enter_live_mode(reason="youtube_live")

    with pytest.raises(GPUJobRejected) as exc_info:
        async with queue.acquire(JobPriority.WAN_BACKGROUND, job_name="wan"):
            pass

    assert "background_jobs_disabled" in str(exc_info.value)
    async with queue.acquire(JobPriority.REAL_TIME_EMBODIMENT, job_name="embodiment"):
        pass

    diagnostics = queue.diagnostics()
    assert diagnostics["background_jobs_allowed"] is False
    assert diagnostics["total_rejected"] == 1
    assert diagnostics["total_completed"] == 1


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
    package_name = f"runtime_src_gpu_{uuid.uuid4().hex}"
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
async def test_gpu_diagnostics_endpoint_reports_queue_state():
    main = _load_runtime_main()

    diagnostics = await main.gpu_diagnostics()

    assert diagnostics["max_concurrent"] == 1
    assert diagnostics["background_jobs_allowed"] is True
    assert diagnostics["queue_depth"] == 0
    assert "average_wait_seconds" in diagnostics
    assert "average_run_seconds" in diagnostics
