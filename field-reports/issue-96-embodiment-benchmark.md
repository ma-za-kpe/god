# Issue #96 Real-Time Embodiment Benchmark

Date: 2026-06-27
Parent: #91
Candidate selected: MuseTalk
Integration path selected for first test: dedicated sidecar
Status: blocked, not measured

## Scope

Issue #96 requires one real-time embodiment candidate to be benchmarked before
committing to ComfyUI nodes or a dedicated sidecar. The current code-only pass
does not have permission to work on Vast.ai or load models, so the benchmark
run itself is blocked and recorded as such.

## Benchmark Contract Added

- Runtime benchmark record model: `runtime/src/avatar/embodiment_benchmark.py`
- Sidecar benchmark runner: `scripts/benchmark-embodiment-sidecar.py`
- Contract tests: `runtime/tests/test_embodiment_benchmark.py`

The runner sends a static portrait and Fish WAV fixture to `POST /embody` and
records:

- hardware profile;
- command/workflow;
- latency;
- peak VRAM;
- output notes;
- decision;
- provisioning or failure mode when blocked or failed.

## Blocker

Exact blocker:

- The prior Vast.ai instance was deleted.
- Current operator constraint forbids Vast/model-loading work during this
  code-only pass.
- No target GPU host with MuseTalk models and a sidecar service is available
  for `nvidia-smi` capture, dependency installation, or an `/embody` request.

Because of that, there is no valid latency, VRAM, output-quality, or failure
mode measurement from a live model run in this report.

## Command To Run When Target Host Exists

```bash
python scripts/benchmark-embodiment-sidecar.py \
  --candidate musetalk \
  --endpoint http://localhost:7861 \
  --portrait-file avatar.png \
  --audio-file fish.wav \
  --host-label vast-4090 \
  --gpu-name "RTX 4090" \
  --vram-total-mb 24576 \
  --out field-reports/issue-96-musetalk.json
```

## Decision

Do not integrate MuseTalk, LivePortrait, Wav2Lip, or any real-time embodiment
sidecar into the live path until a target GPU run records latency, VRAM, output
quality, and failure behavior. The observer should continue to rely on Fish
audio amplitude plus procedural life signals for the live baseline.
