# Issue 91 /one Live Design Audit - 2026-07-01

Scope: `/one` single-avatar alphabet recital and Vast native boot path.

Branch under test: `fix/one-alphabet-speaker`
Commit under test: `3bffeb7`
Vast instance: `43411625`
GPU observed: NVIDIA RTX PRO 6000 Blackwell Server Edition, 97887 MiB VRAM
Driver observed: `580.95.05`
Direct SSH endpoint used: `154.59.156.23:22928`

## Goal

The immediate product goal is narrow: `/one` should show one avatar reciting the alphabet until it gets it right.

This is part of issue #91's larger live avatar embodiment roadmap, but it should not depend on LTX, Wan, LipDub, or any offline cinematic workflow. The baseline live path must be:

1. runtime emits a single current speaker;
2. observer renders one avatar;
3. voice path produces speech or degrades visibly;
4. `/one` displays the target alphabet line;
5. screenshot/video proof confirms the visible result.

## Confirmed In Code Before Field Run

- `/one` React observer path selects the active voice/dialogue speaker instead of the first sorted agent.
- `/one` shows the deterministic alphabet line:
  `A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.`
- `/creator/one` and `/one` runtime bootstrap default to the alphabet line.
- Legacy `observer/stage.html` has the same one-avatar alphabet drill fallback.
- Focused Docker/runtime tests passed before deployment.
- `python -m pre_commit run --all-files` passed before the original `/one` commit.

## Live Field Findings

### Finding 1: Best available Vast host was not the cheapest acceptable host

The first acceptable host created for testing was an RTX 3090 Ti with 24 GB VRAM and reliability near `0.979`.

After ranking available offers by live-test criteria, the selected host was an RTX PRO 6000 S class machine with:

- 97887 MiB VRAM;
- CUDA capability reported by Vast as 13.0;
- reliability near `0.9994278`;
- static IP;
- high network throughput;
- direct SSH port available.

Decision: for live model validation, use explicit hardware and reliability facts instead of accepting the first cheap workable host.

### Finding 2: Vast SSH proxy can fail while direct SSH works

The Vast proxy endpoint stayed in banner-exchange timeout. Vast logs showed repeated:

```text
Error: remote port forwarding failed for listen port 11624
```

Direct SSH to the static public IP and mapped direct port worked:

```text
ssh -p 22928 root@154.59.156.23
```

Design impact: deployment instructions and operators should prefer facts from `vastai show instances --raw` and fall back to direct `public_ipaddr:HostPort` when `ssh_host:ssh_port` is unhealthy.

### Finding 3: Native setup was missing base OS packages required by its own boot flow

Observed failures:

- Ollama installer failed until `zstd` was installed.
- `vast-restart-services.sh` uses `ss` and `fuser`; the base image lacked `ss`.

Fix in this PR:

- add `zstd`;
- add `iproute2` for `ss`;
- add `psmisc` for `fuser`.

### Finding 4: `find ... | head -1` is brittle under `set -euo pipefail`

The native setup repeatedly stopped at Fish setup without useful logs after reaching the `uv` lookup. The `find | head -1` pattern is unsafe under `pipefail` because `find` can receive SIGPIPE after `head` exits.

Fix in this PR:

- replace the pipeline with `find ... -print -quit` in both Vast setup and restart scripts.

### Finding 5: Fish model generation was mismatched

Observed on the live host:

- setup downloaded `fishaudio/fish-speech-1.5` into `/opt/fish-speech/checkpoints`;
- restart launched Fish as S2-Pro:
  `/opt/fish-speech/checkpoints/s2-pro` plus `/opt/fish-speech/checkpoints/s2-pro/codec.pth`;
- Fish failed because `/opt/fish-speech/checkpoints/s2-pro` did not exist.

Manual attempt to launch Fish 1.5 from the root checkpoint with the current latest Fish code loaded the Llama weights but failed the decoder with state-dict size mismatch.

Upstream facts checked during the field run:

- current Fish S2-Pro model repository is `fishaudio/s2-pro`;
- its file list includes `codec.pth`;
- upstream server docs use `checkpoints/s2-pro` and `checkpoints/s2-pro/codec.pth`.

Fix in this PR:

- Vast native setup downloads `fishaudio/s2-pro` to `checkpoints/s2-pro`;
- Vast Docker setup downloads `fishaudio/s2-pro` to `/checkpoints/s2-pro`;
- Vast Docker override launches `checkpoints/s2-pro` and `checkpoints/s2-pro/codec.pth`;
- restart already launches S2-Pro paths and now matches setup.

### Finding 6: `/one` live visual proof is not complete yet

Setup reached:

- runtime readiness OK;
- Ollama health OK;
- ComfyUI startup OK;
- Fish model download and launch path reached after script fixes.

But proof is not complete until the corrected S2-Pro download and launch path is run again and `/one` is captured with:

- screenshot;
- short video;
- visible single avatar;
- alphabet caption/status;
- audible alphabet recital or explicit Fish failure fallback.

## Design Conclusion

The `/one` feature design is sound as a narrow observer/runtime behavior, but the live field run showed the deployment layer was still not production-tight:

- boot prerequisites were incomplete;
- Vast SSH connection selection needs to use observed direct-port facts;
- Fish setup and Fish launch paths were inconsistent;
- the PR must not claim live audio success until S2-Pro boots and `/one` is captured.

## Acceptance Criteria Remaining

- Vast setup completes from a fresh host without manual package installation.
- Fish `/v1/health` and real `/v1/tts` probe pass on CUDA.
- Runtime `/ready` reports voice readiness.
- `/one` is captured as screenshot and video from the live observer.
- If Fish fails, `/one` still visibly shows the alphabet line and a non-silent/fallback status.
