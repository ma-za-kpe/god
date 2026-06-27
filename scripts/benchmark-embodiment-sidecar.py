#!/usr/bin/env python3
"""Record a real-time embodiment sidecar benchmark result.

This client does not load model code. It sends a portrait/audio fixture to a
running sidecar that implements the /embody contract and writes a structured
benchmark record for issue #96.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "runtime" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from avatar.embodiment_benchmark import (  # noqa: E402
    BenchmarkStatus,
    EmbodimentBenchmarkResult,
    EmbodimentCandidate,
    HardwareProfile,
    IntegrationPath,
    build_blocked_issue96_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", choices=[item.value for item in EmbodimentCandidate])
    parser.add_argument("--endpoint", help="Sidecar base URL, for example http://localhost:7861")
    parser.add_argument("--portrait-file", help="Source portrait image file")
    parser.add_argument("--audio-file", help="Fish WAV/audio fixture")
    parser.add_argument("--portrait-cid", default="")
    parser.add_argument("--duration-ms", type=int, default=5000)
    parser.add_argument("--emotion", default="neutral")
    parser.add_argument("--motion-seed", type=int, default=42)
    parser.add_argument("--host-label", default="target GPU host")
    parser.add_argument("--gpu-name", default="")
    parser.add_argument("--vram-total-mb", type=int, default=0)
    parser.add_argument("--ram-total-mb", type=int)
    parser.add_argument("--disk-free-gb", type=float)
    parser.add_argument("--cuda-version", default="")
    parser.add_argument("--driver-version", default="")
    parser.add_argument("--os", default="")
    parser.add_argument("--peak-vram-mb", type=int)
    parser.add_argument("--output-notes", default="")
    parser.add_argument("--workflow", default="")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument("--out", help="Path to write benchmark JSON; stdout when omitted")
    parser.add_argument(
        "--write-current-blocker",
        action="store_true",
        help="Write the current code-only issue #96 blocker record instead of calling a sidecar",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.write_current_blocker:
        return write_result(build_blocked_issue96_result(), args.out)

    missing = [
        name
        for name in ("candidate", "endpoint", "portrait_file", "audio_file")
        if not getattr(args, name)
    ]
    if missing:
        raise SystemExit(f"missing required arguments: {', '.join(missing)}")

    candidate = EmbodimentCandidate(args.candidate)
    payload = {
        "portrait_cid": args.portrait_cid,
        "portrait_bytes": encode_file(args.portrait_file),
        "audio_bytes": encode_file(args.audio_file),
        "duration_ms": args.duration_ms,
        "emotion": args.emotion,
        "motion_seed": args.motion_seed,
    }

    command = " ".join(sys.argv)
    workflow = args.workflow or f"{candidate.value} sidecar POST /embody"
    hardware = HardwareProfile(
        host_label=args.host_label,
        gpu_name=args.gpu_name,
        vram_total_mb=args.vram_total_mb,
        ram_total_mb=args.ram_total_mb,
        disk_free_gb=args.disk_free_gb,
        cuda_version=args.cuda_version,
        driver_version=args.driver_version,
        os=args.os,
    )

    result = call_sidecar(
        endpoint=args.endpoint,
        payload=payload,
        timeout_s=args.timeout_s,
        candidate=candidate,
        command=command,
        workflow=workflow,
        hardware=hardware,
        peak_vram_mb=args.peak_vram_mb,
        output_notes=args.output_notes,
    )
    return write_result(result, args.out)


def encode_file(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def call_sidecar(
    *,
    endpoint: str,
    payload: dict[str, Any],
    timeout_s: float,
    candidate: EmbodimentCandidate,
    command: str,
    workflow: str,
    hardware: HardwareProfile,
    peak_vram_mb: int | None,
    output_notes: str,
) -> EmbodimentBenchmarkResult:
    url = f"{endpoint.rstrip('/')}/embody"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/octet-stream"},
        method="POST",
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            output = response.read()
            roundtrip_ms = (time.perf_counter() - started) * 1000.0
            response_latency_ms = parse_float_header(response.headers.get("X-Latency-Ms"))
            response_vram_mb = parse_int_header(response.headers.get("X-Peak-Vram-Mb"))
            content_type = response.headers.get("Content-Type", "")
            latency_ms = response_latency_ms if response_latency_ms is not None else roundtrip_ms
            return EmbodimentBenchmarkResult(
                candidate=candidate,
                status=BenchmarkStatus.MEASURED,
                integration_path=IntegrationPath.SIDECAR,
                hardware=hardware,
                command=command,
                workflow=workflow,
                recorded_at=utc_now(),
                latency_ms=latency_ms,
                peak_vram_mb=response_vram_mb or peak_vram_mb,
                output_notes=output_notes
                or f"{len(output)} bytes returned with content type {content_type or 'unknown'}",
                decision=(
                    "Candidate remains eligible for live integration."
                    if latency_ms <= 300
                    else "Candidate is too slow for the live path; keep it offline/background only."
                ),
                raw_metrics={
                    "http_status": response.status,
                    "content_type": content_type,
                    "response_bytes": len(output),
                    "roundtrip_latency_ms": round(roundtrip_ms, 3),
                    "response_latency_ms": response_latency_ms,
                },
            )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return failed_result(
            candidate=candidate,
            command=command,
            workflow=workflow,
            hardware=hardware,
            failure_mode=f"Sidecar returned HTTP {exc.code}: {detail[:500]}",
        )
    except OSError as exc:
        return failed_result(
            candidate=candidate,
            command=command,
            workflow=workflow,
            hardware=hardware,
            failure_mode=f"Sidecar request failed: {exc}",
        )


def failed_result(
    *,
    candidate: EmbodimentCandidate,
    command: str,
    workflow: str,
    hardware: HardwareProfile,
    failure_mode: str,
) -> EmbodimentBenchmarkResult:
    return EmbodimentBenchmarkResult(
        candidate=candidate,
        status=BenchmarkStatus.FAILED,
        integration_path=IntegrationPath.SIDECAR,
        hardware=hardware,
        command=command,
        workflow=workflow,
        recorded_at=utc_now(),
        failure_mode=failure_mode,
        provisioning_notes=(
            "The sidecar benchmark requires a running embodiment service with model weights loaded."
        ),
        decision="Do not integrate this candidate until the benchmark returns a complete result.",
    )


def parse_float_header(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_int_header(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def write_result(result: EmbodimentBenchmarkResult, out_path: str | None) -> int:
    payload = json.dumps(result.to_dict(), indent=2, sort_keys=True)
    if out_path:
        Path(out_path).write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if result.is_complete() else 2


if __name__ == "__main__":
    raise SystemExit(main())
