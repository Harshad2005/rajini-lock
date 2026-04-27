#!/usr/bin/env bash
# Cleanly remove Rajini-Lock from your Mac.
set -euo pipefail

APP_SUPPORT="$HOME/Library/Application Support/RajiniLock"
PLIST="$HOME/Library/LaunchAgents/com.rajinilock.unlocker.plist"

echo "── Uninstalling Rajini-Lock ──"
launchctl unload "$PLIST" >/dev/null 2>&1 || true
[[ -f "$PLIST" ]] && rm "$PLIST" && echo "[✓] Removed LaunchAgent"
[[ -d "$APP_SUPPORT" ]] && rm -rf "$APP_SUPPORT" && echo "[✓] Removed app data"
[[ -f "$HOME/.rajini_disable" ]] && rm "$HOME/.rajini_disable"
echo "[✓] Uninstall complete. Reboot to confirm — you'll boot into normal macOS."
