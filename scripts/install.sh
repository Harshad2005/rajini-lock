#!/usr/bin/env bash
# Rajini-Lock installer — sets up the voice unlocker on your Mac.
#
# What it does:
#   1. Creates a virtualenv in ~/Library/Application Support/RajiniLock
#   2. Installs the Python package + dependencies
#   3. Drops a LaunchAgent so the lock screen runs automatically at login
#
# It does NOT:
#   • Touch system files outside your home directory
#   • Require sudo
#   • Replace your real macOS login window (that needs a SecurityAgent
#     plug-in — separate, riskier branch)
#
# To uninstall:    bash scripts/uninstall.sh
# Emergency off:   touch ~/.rajini_disable     (skips the lock at next login)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_SUPPORT="$HOME/Library/Application Support/RajiniLock"
LAUNCHAGENTS="$HOME/Library/LaunchAgents"
PLIST_LABEL="com.rajinilock.unlocker"
PLIST_DEST="$LAUNCHAGENTS/$PLIST_LABEL.plist"
INSTALL_DIR="$APP_SUPPORT/app"

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "\033[32m[✓]\033[0m %s\n" "$*"; }
info() { printf "\033[36m[i]\033[0m %s\n" "$*"; }
warn() { printf "\033[33m[!]\033[0m %s\n" "$*"; }
err()  { printf "\033[31m[x]\033[0m %s\n" "$*" >&2; }

bold "════════════════════════════════════════════════════════════"
bold "  RAJINI-LOCK INSTALLER  —  Voice-Activated Mac Lock Screen"
bold "  Inspired by Sivaji: The Boss (2007)"
bold "════════════════════════════════════════════════════════════"
echo

# ── Sanity checks
if [[ "$(uname)" != "Darwin" ]]; then
  err "This is macOS-only. You're on $(uname)."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  err "python3 not found. Install with:  brew install python@3.12"
  exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')
info "Using Python $PY_VERSION"

# ── Create folders
mkdir -p "$APP_SUPPORT" "$INSTALL_DIR" "$LAUNCHAGENTS"

# ── Copy app source
info "Copying app to $INSTALL_DIR ..."
rsync -a --delete \
    --exclude '.git' --exclude '__pycache__' --exclude '*.pyc' \
    --exclude 'demo' --exclude 'docs' \
    "$REPO_DIR/" "$INSTALL_DIR/"
ok "Source installed"

# ── Create venv
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
  info "Creating virtualenv ..."
  python3 -m venv "$INSTALL_DIR/venv"
fi

# ── Install dependencies
info "Installing Python dependencies (this takes a minute) ..."
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet "$INSTALL_DIR"
ok "Dependencies installed"

# ── Write the launcher shim
cat > "$INSTALL_DIR/run_lock.sh" <<EOF
#!/usr/bin/env bash
exec "$INSTALL_DIR/venv/bin/python" -m sivaji_unlocker
EOF
chmod +x "$INSTALL_DIR/run_lock.sh"

# ── Render the LaunchAgent plist with absolute paths
sed \
  -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" \
  -e "s|__APP_SUPPORT__|$APP_SUPPORT|g" \
  "$REPO_DIR/launchd/com.rajinilock.unlocker.plist" > "$PLIST_DEST"
ok "LaunchAgent installed at $PLIST_DEST"

# ── Load it (replace if already loaded)
launchctl unload "$PLIST_DEST" >/dev/null 2>&1 || true
launchctl load -w "$PLIST_DEST"
ok "LaunchAgent loaded — runs on every login"

echo
bold "── NEXT STEP: ENROLL YOUR VOICE ────────────────────────────"
echo
echo "Run this now to record your voiceprint (~30 seconds):"
echo
echo "    $INSTALL_DIR/venv/bin/rajini-enroll"
echo
bold "── EMERGENCY OFF SWITCHES ──────────────────────────────────"
echo
echo "If anything goes wrong:"
echo "  touch ~/.rajini_disable             # skip on next login"
echo "  bash $REPO_DIR/scripts/uninstall.sh # remove completely"
echo
echo "From Recovery Mode (⌘R at boot) → Terminal:"
echo "  touch /Users/$USER/.rajini_disable"
echo
ok "Install complete."
