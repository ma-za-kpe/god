"""Benchmark records for real-time avatar embodiment candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


LIVE_LATENCY_TARGET_MS = 300.0


class EmbodimentCandidate(str, Enum):
    """Supported real-time embodiment candidates for the benchmark spike."""

    MUSE_TALK = "musetalk"
    LIVE_PORTRAIT = "liveportrait"
    WAV2LIP = "wav2lip"


class BenchmarkStatus(str, Enum):
    """Benchmark outcome state."""

    MEASURED = "measured"
    FAILED = "failed"
    BLOCKED = "blocked"


class IntegrationPath(str, Enum):
    """Execution path being evaluated for a candidate."""

    SIDECAR = "sidecar"
    COMFYUI = "comfyui"
    BROWSER = "browser"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class HardwareProfile:
    """Hardware context required to make benchmark results comparable."""

    host_label: str
    gpu_name: str
    vram_total_mb: int
    ram_total_mb: int | None = None
    disk_free_gb: float | None = None
    cuda_version: str = ""
    driver_version: str = ""
    os: str = ""

    def has_gpu_measurement(self) -> bool:
        return bool(self.gpu_name and self.vram_total_mb > 0)


@dataclass
class EmbodimentBenchmarkResult:
    """Structured benchmark evidence for one embodiment candidate."""

    candidate: EmbodimentCandidate
    status: BenchmarkStatus
    integration_path: IntegrationPath
    hardware: HardwareProfile
    command: str = ""
    workflow: str = ""
    recorded_at: str = ""
    latency_ms: float | None = None
    peak_vram_mb: int | None = None
    output_duration_ms: int | None = None
    output_fps: float | None = None
    output_resolution: str = ""
    output_notes: str = ""
    provisioning_notes: str = ""
    failure_mode: str = ""
    decision: str = ""
    raw_metrics: dict[str, Any] = field(default_factory=dict)

    def validation_gaps(self) -> list[str]:
        gaps: list[str] = []
        if not self.command and not self.workflow:
            gaps.append("command_or_workflow")
        if not self.hardware.host_label:
            gaps.append("hardware.host_label")
        if self.status == BenchmarkStatus.MEASURED:
            gaps.extend(self._measured_gaps())
        if self.status in {BenchmarkStatus.FAILED, BenchmarkStatus.BLOCKED}:
            gaps.extend(self._failure_gaps())
        return gaps

    def is_complete(self) -> bool:
        return not self.validation_gaps()

    def live_readiness(self) -> str:
        if self.status == BenchmarkStatus.BLOCKED:
            return "blocked"
        if self.status == BenchmarkStatus.FAILED:
            return "failed"
        if self.latency_ms is None:
            return "unknown"
        if self.latency_ms <= LIVE_LATENCY_TARGET_MS:
            return "live_candidate"
        return "offline_or_background_only"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["candidate"] = self.candidate.value
        payload["status"] = self.status.value
        payload["integration_path"] = self.integration_path.value
        payload["validation_gaps"] = self.validation_gaps()
        payload["live_readiness"] = self.live_readiness()
        return payload

    def _measured_gaps(self) -> list[str]:
        gaps: list[str] = []
        if not self.hardware.has_gpu_measurement():
            gaps.append("hardware.gpu")
        if self.latency_ms is None or self.latency_ms < 0:
            gaps.append("latency_ms")
        if self.peak_vram_mb is None or self.peak_vram_mb <= 0:
            gaps.append("peak_vram_mb")
        if not self.output_notes:
            gaps.append("output_notes")
        if not self.decision:
            gaps.append("decision")
        return gaps

    def _failure_gaps(self) -> list[str]:
        gaps: list[str] = []
        if not self.failure_mode:
            gaps.append("failure_mode")
        if not self.provisioning_notes:
            gaps.append("provisioning_notes")
        if not self.decision:
            gaps.append("decision")
        return gaps


def build_sidecar_contract(
    candidate: EmbodimentCandidate,
    *,
    endpoint_path: str = "/embody",
    health_path: str = "/health",
) -> dict[str, Any]:
    """Return the stable sidecar API shape expected by the benchmark runner."""

    return {
        "candidate": candidate.value,
        "path": endpoint_path,
        "method": "POST",
        "content_type": "application/json",
        "health_path": health_path,
        "request_fields": {
            "portrait_cid": "string optional",
            "portrait_bytes": "base64 optional",
            "audio_bytes": "base64 wav required",
            "duration_ms": "integer",
            "emotion": "string",
            "motion_seed": "integer",
        },
        "response": {
            "success": "binary MP4/WebM bytes or JSON with audio/video metadata",
            "latency_header": "X-Latency-Ms",
            "vram_header": "X-Peak-Vram-Mb optional",
        },
    }


def build_blocked_issue96_result() -> EmbodimentBenchmarkResult:
    """Record the current code-only blocker for the first candidate benchmark."""

    return EmbodimentBenchmarkResult(
        candidate=EmbodimentCandidate.MUSE_TALK,
        status=BenchmarkStatus.BLOCKED,
        integration_path=IntegrationPath.SIDECAR,
        hardware=HardwareProfile(
            host_label="target Vast.ai GPU host",
            gpu_name="unavailable",
            vram_total_mb=0,
        ),
        command=(
            "python scripts/benchmark-embodiment-sidecar.py --candidate musetalk "
            "--endpoint http://localhost:7861 --portrait-file avatar.png "
            "--audio-file fish.wav --out field-reports/issue-96-musetalk.json"
        ),
        workflow="MuseTalk sidecar POST /embody using a static portrait and Fish WAV bytes.",
        failure_mode=(
            "The prior Vast.ai instance was deleted and the current operator constraint forbids "
            "Vast/model-loading work during this code-only pass."
        ),
        provisioning_notes=(
            "No target GPU host with MuseTalk models and sidecar service is available for "
            "nvidia-smi capture, dependency installation, or an /embody request."
        ),
        decision=(
            "Do not integrate MuseTalk or any real-time embodiment sidecar until a target GPU "
            "run records latency, VRAM, output quality, and failure behavior."
        ),
    )
