"""Real-time embodiment benchmark contract tests."""

from __future__ import annotations

from avatar import (
    BenchmarkStatus,
    EmbodimentBenchmarkResult,
    EmbodimentCandidate,
    HardwareProfile,
    IntegrationPath,
    build_blocked_issue96_result,
    build_sidecar_contract,
)


def test_measured_benchmark_result_requires_issue96_evidence_fields():
    incomplete = EmbodimentBenchmarkResult(
        candidate=EmbodimentCandidate.MUSE_TALK,
        status=BenchmarkStatus.MEASURED,
        integration_path=IntegrationPath.SIDECAR,
        hardware=HardwareProfile(
            host_label="vast-4090",
            gpu_name="",
            vram_total_mb=0,
        ),
        command="python scripts/benchmark-embodiment-sidecar.py ...",
        workflow="POST /embody with Fish WAV",
        latency_ms=88.0,
    )

    assert incomplete.is_complete() is False
    assert incomplete.validation_gaps() == [
        "hardware.gpu",
        "peak_vram_mb",
        "output_notes",
        "decision",
    ]

    complete = EmbodimentBenchmarkResult(
        candidate=EmbodimentCandidate.MUSE_TALK,
        status=BenchmarkStatus.MEASURED,
        integration_path=IntegrationPath.SIDECAR,
        hardware=HardwareProfile(
            host_label="vast-4090",
            gpu_name="RTX 4090",
            vram_total_mb=24576,
        ),
        command="python scripts/benchmark-embodiment-sidecar.py ...",
        workflow="POST /embody with Fish WAV",
        latency_ms=88.0,
        peak_vram_mb=12100,
        output_notes="256x256 talking-face output, no black frames observed",
        decision="Eligible for a sidecar prototype.",
    )

    assert complete.is_complete() is True
    assert complete.live_readiness() == "live_candidate"
    assert complete.to_dict()["validation_gaps"] == []


def test_slow_measured_benchmark_is_not_live_ready():
    result = EmbodimentBenchmarkResult(
        candidate=EmbodimentCandidate.WAV2LIP,
        status=BenchmarkStatus.MEASURED,
        integration_path=IntegrationPath.SIDECAR,
        hardware=HardwareProfile(
            host_label="vast-4090",
            gpu_name="RTX 4090",
            vram_total_mb=24576,
        ),
        command="python scripts/benchmark-embodiment-sidecar.py ...",
        latency_ms=425.0,
        peak_vram_mb=8000,
        output_notes="Output completed but misses the live reaction target.",
        decision="Use only for offline/highlight jobs.",
    )

    assert result.is_complete() is True
    assert result.live_readiness() == "offline_or_background_only"


def test_blocked_issue96_result_records_exact_provisioning_blocker():
    result = build_blocked_issue96_result()

    assert result.candidate == EmbodimentCandidate.MUSE_TALK
    assert result.status == BenchmarkStatus.BLOCKED
    assert result.integration_path == IntegrationPath.SIDECAR
    assert result.is_complete() is True
    assert result.live_readiness() == "blocked"
    assert "Vast.ai instance was deleted" in result.failure_mode
    assert "No target GPU host" in result.provisioning_notes
    assert "validation_gaps" in result.to_dict()


def test_sidecar_contract_exposes_runtime_request_shape():
    contract = build_sidecar_contract(EmbodimentCandidate.MUSE_TALK)

    assert contract["candidate"] == "musetalk"
    assert contract["method"] == "POST"
    assert contract["path"] == "/embody"
    assert contract["health_path"] == "/health"
    assert contract["request_fields"]["audio_bytes"] == "base64 wav required"
    assert contract["response"]["latency_header"] == "X-Latency-Ms"
