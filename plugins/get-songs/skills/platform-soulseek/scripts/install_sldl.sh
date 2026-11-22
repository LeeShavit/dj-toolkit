#!/usr/bin/env bash
# Install the latest sldl / Sockseek release for this OS + CPU.
set -euo pipefail
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) ASSET=osx-arm64 ;;
  Darwin-x86_64) ASSET=osx-x64 ;;
  Linux-x86_64) ASSET=linux-x64 ;;
  Linux-arm*|Linux-aarch64) ASSET=linux-arm ;;
  *) echo "Unsupported platform $(uname -sm) - download manually from https://github.com/fiso64/sockseek/releases"; exit 1 ;;
esac
URL=$(curl -sL https://api.github.com/repos/fiso64/sockseek/releases/latest \
  | python3 -c "import json,sys;print(next(a['browser_download_url'] for a in json.load(sys.stdin)['assets'] if '$ASSET' in a['name']))")
DEST="$HOME/.local/share/sockseek"; mkdir -p "$DEST" "$HOME/.local/bin"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
echo "Downloading $URL"
curl -sSL "$URL" -o "$TMP/s.tgz"
tar -xzf "$TMP/s.tgz" -C "$TMP"
install -m 755 "$TMP/sockseek" "$DEST/sockseek"
ln -sf "$DEST/sockseek" "$HOME/.local/bin/sldl"
"$DEST/sockseek" --help >/dev/null 2>&1 && echo "Installed: $HOME/.local/bin/sldl" || echo "Installed, but it failed to run - check it manually"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "Note: add ~/.local/bin to PATH, or call $HOME/.local/bin/sldl" ;; esac
