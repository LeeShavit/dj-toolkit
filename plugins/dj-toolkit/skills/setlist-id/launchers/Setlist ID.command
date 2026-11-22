#!/bin/bash
# Double-click to start Setlist ID. The first run downloads everything it needs
# (into the "app" folder next to this file) – later runs start in a few seconds.
cd "$(dirname "$0")/app" || exit 1
export PYTHONUTF8=1 UV_NO_MODIFY_PATH=1
export UV_INSTALL_DIR="$PWD/tools" UV_CACHE_DIR="$PWD/tools/cache" UV_PYTHON_INSTALL_DIR="$PWD/tools/python"
UV="$UV_INSTALL_DIR/uv"

fail() { echo; echo "$1"; read -n1 -rsp "Press any key to close this window."; exit 1; }

if [ ! -x "$UV" ]; then
  echo "First-time setup – this takes a minute or two..."
  curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null || fail "Setup failed. Check your internet connection and try again."
fi
"$UV" run --quiet --upgrade-package yt-dlp app.py || fail "Setlist ID stopped because of an error (see above)."
