"""Static contracts for Vast Fish Speech boot scripts."""

from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "scripts" / "vast-setup-native.sh").is_file():
            return candidate
    raise FileNotFoundError("repo root not found")


def _read(path: str) -> str:
    return (_repo_root() / path).read_text(encoding="utf-8")


def test_vast_native_installs_restart_prerequisites():
    script = _read("scripts/vast-setup-native.sh")
    restart = _read("scripts/vast-restart-services.sh")

    assert "zstd" in script
    assert "iproute2 psmisc" in script
    assert "nginx" in script
    assert "xdotool" in script
    assert "ss -tlnp" in script
    assert "fuser -k" in script
    assert 'die "nginx missing; rerun vast-setup-native.sh"' in restart


def test_vast_fish_model_download_matches_native_launcher():
    setup = _read("scripts/vast-setup-native.sh")
    restart = _read("scripts/vast-restart-services.sh")

    assert "repo_id='fishaudio/s2-pro'" in setup
    assert 'FISH_SPEECH_REF="${FISH_SPEECH_REF:-v2.0.0-beta}"' in setup
    assert 'git checkout --force "$FISH_SPEECH_REF"' in setup
    assert 'grep -q "fish_qwen3_omni"' in setup
    assert "local_dir='checkpoints/s2-pro'" in setup
    assert "/opt/fish-speech/checkpoints/s2-pro" in setup
    assert "/opt/fish-speech/checkpoints/s2-pro/codec.pth" in setup
    assert "/opt/fish-speech/checkpoints/s2-pro" in restart
    assert "/opt/fish-speech/checkpoints/s2-pro/codec.pth" in restart
    assert "repo_id='fishaudio/fish-speech-1.5'" not in setup

    assert '"$UV" python install 3.11 --quiet' in setup
    assert '"$UV" sync --python 3.11 --extra cu128 --no-dev --quiet' in setup
    assert '"$UV" run --no-sync --python 3.11 python -c' in setup
    assert '"$UV" run --no-sync --python 3.11 python tools/api_server.py' in setup
    assert 'die "uv missing; fish-speech requires uv-managed Python 3.11"' in restart
    assert '"$UV" sync --python 3.11 --extra cu128 --no-dev --quiet' in restart
    assert "run --no-sync --python 3.11 python tools/api_server.py" in restart
    assert "rerun vast-setup-native.sh" in restart
    assert "exec python3 tools/api_server.py" not in restart


def test_vast_docker_fish_model_download_matches_launcher():
    setup = _read("scripts/vast-setup.sh")
    compose = _read("docker-compose.vast.yml")

    assert "repo_id='fishaudio/s2-pro'" in setup
    assert "local_dir='/checkpoints/s2-pro'" in setup
    assert "--llama-checkpoint-path checkpoints/s2-pro" in compose
    assert "--decoder-checkpoint-path checkpoints/s2-pro/codec.pth" in compose
    assert "repo_id='fishaudio/fish-speech-1.5'" not in setup
    assert "--decoder-checkpoint-path checkpoints/codec.pth" not in compose


def test_vast_uv_lookup_does_not_use_head_pipeline_under_pipefail():
    native = _read("scripts/vast-setup-native.sh")
    restart = _read("scripts/vast-restart-services.sh")

    assert "-name uv -type f -print -quit" in native
    assert "-name uv -type f -print -quit" in restart
    assert "-name uv -type f 2>/dev/null | head -1" not in native
    assert "-name uv -type f 2>/dev/null | head -1" not in restart


def test_vast_obs_browser_url_can_target_one_page():
    native = _read("scripts/vast-setup-native.sh")
    restart = _read("scripts/vast-restart-services.sh")

    assert "OBS_BROWSER_URL=http://localhost:10517/one" in native
    assert 'if [ -z "${OBS_BROWSER_URL:-}" ]; then' in restart
    assert "export OBS_BROWSER_URL=http://localhost:10517/stage" in restart
    assert 'wait_http "$browser_url" "OBS browser URL"' in restart
    assert "streaming ${OBS_BROWSER_URL}" in restart
    assert "Browser source is always /stage" not in restart
