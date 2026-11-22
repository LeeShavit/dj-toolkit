#!/usr/bin/env bash
# Build "Setlist ID.zip" - a double-click app for friends (macOS .command + Windows .bat).
set -euo pipefail
SKILL="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HOME/Desktop}"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
APP="$TMP/Setlist ID"
mkdir -p "$APP/app"
cp "$SKILL/launchers/"* "$APP/"
cp "$SKILL/app/setlist_id.py" "$SKILL/app/app.py" "$APP/app/"
chmod +x "$APP/Setlist ID.command"
mkdir -p "$OUT"; rm -f "$OUT/Setlist ID.zip"
if command -v ditto >/dev/null; then   # macOS: keeps the executable bit on the .command file
  (cd "$TMP" && ditto -c -k --keepParent "Setlist ID" "$OUT/Setlist ID.zip")
else
  (cd "$TMP" && zip -qr "$OUT/Setlist ID.zip" "Setlist ID")
fi
echo "Built $OUT/Setlist ID.zip"
