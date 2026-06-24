#!/usr/bin/env bash
# Open the GOD observer in Chrome with GPU sandbox disabled.
# Fixes: "Sandboxed = yes, BindToCurrentSequence failed" WebGL error
# when running inside restricted Electron/Chromium previews.
#
# Usage:
#   bash scripts/open-observer.sh            → opens /stage (default, OBS overlay)
#   bash scripts/open-observer.sh stage      → opens /stage (full ensemble)
#   bash scripts/open-observer.sh classic    → opens /classic (pure-HTML fallback)

MODE="${1:-stage}"
URL="http://localhost:3000/${MODE}"

# GPU sandbox flags:
#   --disable-gpu-sandbox  : allow GPU access from the browser process
#   --use-gl=desktop       : use the system's native OpenGL driver
#   --use-angle=gl         : ANGLE OpenGL backend (Linux)
# Swap --use-gl=desktop → --use-gl=swiftshader for software-only rendering
FLAGS="--disable-gpu-sandbox --use-gl=desktop --use-angle=gl"

for BIN in google-chrome google-chrome-stable chromium chromium-browser; do
  if command -v "$BIN" &>/dev/null; then
    echo "[open-observer] Opening ${URL} with ${BIN}"
    exec "$BIN" $FLAGS "$URL"
  fi
done

echo "[open-observer] Chrome/Chromium not found in PATH."
echo "  Open ${URL} manually with: ${FLAGS}"
exit 1
