FROM fishaudio/fish-speech:latest

WORKDIR /app

# The upstream image runs `uv run` at container start, which syncs all
# dependencies (torch, CUDA libs, ~1.4 GB) on every fresh boot.
# Pre-syncing here bakes them into the image layer so startup is instant.
RUN UV_HTTP_TIMEOUT=300 uv sync --no-dev

# Skip the startup warm-up inference pass. The default model_manager.py runs
# a "Hello world." TTS inference on boot to warm the KV-cache. On a 16 GB
# host this warm-up spikes RAM past Docker's 13.65 GB limit and OOM-kills the
# container. The first real request will be ~10s slower; all subsequent are
# unaffected. Replace with our patched copy.
COPY model_manager.py /app/tools/server/model_manager.py
