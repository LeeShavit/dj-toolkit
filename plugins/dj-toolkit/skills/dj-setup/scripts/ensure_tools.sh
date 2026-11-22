#!/usr/bin/env bash
# Make sure the DJ toolkit runtime is present: uv (runs every script with its own deps) + ffmpeg.
set -uo pipefail
if command -v uv >/dev/null 2>&1; then
  echo "uv: $(uv --version)"
elif [ -x "$HOME/.local/bin/uv" ]; then
  echo "uv: installed at ~/.local/bin/uv (not on PATH - call it by full path or add ~/.local/bin to PATH)"
else
  echo "Installing uv (https://astral.sh/uv)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null && echo "uv: installed to ~/.local/bin/uv" || echo "uv: INSTALL FAILED"
fi
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  echo "ffmpeg: $(ffmpeg -version | head -1 | cut -d' ' -f3)"
else
  echo "ffmpeg: MISSING - macOS: brew install ffmpeg · Linux: apt install ffmpeg · Windows: winget install ffmpeg"
fi
command -v python3 >/dev/null 2>&1 && echo "python3: $(python3 --version 2>&1)" || echo "python3: missing (uv can provide one)"
