#!/bin/bash
# Install Coding Agent Status Bar: the menu bar app, its OpenCode plugin, and its Codex and
# Claude Code hooks.
# Safe to re-run; use it again after `git pull` or after moving this folder.
set -euo pipefail

APP_NAME="Coding Agent Status Bar"
EXEC_NAME="CodingAgentStatusBar"
BUNDLE_ID="io.github.haoyangzhang99.CodingAgentStatusBar"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP_DIR="$HOME/Applications"
APP="$APP_DIR/$APP_NAME.app"
PLUGIN_DIR="$HOME/.config/opencode/plugins"
PLUGIN="$PLUGIN_DIR/coding-agent-status-bar.js"
MARKER="Installed by Coding Agent Status Bar"
CONFIG_DIR="$HOME/.config/coding-agent-status-bar"
PYTHON_VERSION="${CASB_PYTHON:-3.12}"
LAUNCH=1

usage() {
    cat <<EOF
Usage: ./install.sh [--no-launch]

Builds "$APP_NAME.app" into ~/Applications, installs the OpenCode plugin
into ~/.config/opencode/plugins, and adds Codex hooks to ~/.codex/hooks.json
and Claude Code hooks to ~/.claude/settings.json if those apps are installed.
Requires macOS, uv, and Xcode Command Line Tools.

  --no-launch   Install without starting the app afterwards.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --no-launch) LAUNCH=0 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'Warning: %s\n' "$*" >&2; }
fail() { printf '\nError: %s\n' "$*" >&2; exit 1; }

# Stop only the copy installed at the given app path, never another build of the app.
# Usage: stop_installed_app <app path> <executable name>
stop_installed_app() {
    local pid
    for pid in $(pgrep -f "/Contents/MacOS/$2" 2>/dev/null || true); do
        case "$(ps -o command= -p "$pid" 2>/dev/null)" in
            "$1/Contents/MacOS/$2"*)
                kill "$pid" 2>/dev/null || true
                for _ in 1 2 3 4 5 6 7 8 9 10; do
                    kill -0 "$pid" 2>/dev/null || break
                    sleep 0.5
                done
                ;;
        esac
    done
}

step "Checking requirements"
[ "$(uname -s)" = Darwin ] || fail "Coding Agent Status Bar only runs on macOS."
command -v uv >/dev/null 2>&1 ||
    fail "uv is required. Install it with 'brew install uv' (see https://docs.astral.sh/uv/), then re-run this script."
xcode-select -p >/dev/null 2>&1 ||
    fail "Xcode Command Line Tools are required. Run 'xcode-select --install', then re-run this script."
case "$REPO" in
    *\"*|*\\*) fail "Move this folder to a path without quotes or backslashes: $REPO" ;;
esac
if [ ! -d "/Applications/OpenCode.app" ] && [ ! -d "$HOME/Applications/OpenCode.app" ]; then
    warn "The OpenCode desktop app was not found. The status bar needs OpenCode running with the plugin loaded."
fi

step "Installing Python $PYTHON_VERSION and dependencies"
# uv-managed Python ships the shared libpython that the native launcher embeds.
(cd "$REPO" && UV_PYTHON_PREFERENCE=only-managed uv sync --no-dev --locked --python "$PYTHON_VERSION")
PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || fail "uv did not create $PY."

step "Building $APP_NAME.app"
INCLUDE="$("$PY" -c 'import sysconfig; print(sysconfig.get_path("include"))')"
LIBDIR="$("$PY" -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR"))')"
PYVER="$("$PY" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
VERSION="$("$PY" -c 'import importlib.metadata as m; print(m.version("coding-agent-status-bar"))')"
[ -f "$LIBDIR/libpython$PYVER.dylib" ] || fail "libpython$PYVER.dylib not found in $LIBDIR."

BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
STAGE="$BUILD/$APP_NAME.app"
mkdir -p "$STAGE/Contents/MacOS" "$STAGE/Contents/Resources"
cp "$REPO/assets/AppIcon.icns" "$STAGE/Contents/Resources/AppIcon.icns"
clang -O2 "$REPO/integrations/launcher.m" -o "$STAGE/Contents/MacOS/$EXEC_NAME" \
    -framework Foundation -I"$INCLUDE" -L"$LIBDIR" -Wl,-rpath,"$LIBDIR" -lpython"$PYVER" \
    -DPYTHON_EXECUTABLE="\"$PY\""
cat >"$STAGE/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>$APP_NAME</string>
    <key>CFBundleDisplayName</key>
    <string>$APP_NAME</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleExecutable</key>
    <string>$EXEC_NAME</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>$VERSION</string>
    <key>CFBundleVersion</key>
    <string>$VERSION</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <key>LSUIElement</key>
    <true/>
</dict>
</plist>
EOF
plutil -lint -s "$STAGE/Contents/Info.plist" || fail "Generated Info.plist is invalid."
codesign --force --sign - "$STAGE" 2>"$BUILD/codesign.log" ||
    fail "Code signing failed: $(cat "$BUILD/codesign.log")"
"$STAGE/Contents/MacOS/$EXEC_NAME" --check || fail "The app failed its self-check."

stop_installed_app "$APP" "$EXEC_NAME"
mkdir -p "$APP_DIR"
rm -rf "$APP"
mv "$STAGE" "$APP"
echo "Installed $APP"

# This app was called OpenCode Status Bar before. Remove that install; the hook scripts
# replace its Codex and Claude Code hooks below.
LEGACY_APP="$APP_DIR/OpenCode Status Bar.app"
LEGACY_PLUGIN="$PLUGIN_DIR/opencode-status-bar.js"
LEGACY_CONFIG="$HOME/.config/opencode-status-bar"
if [ -d "$LEGACY_APP" ] || [ -e "$LEGACY_PLUGIN" ] || [ -d "$LEGACY_CONFIG" ]; then
    step "Removing OpenCode Status Bar, this app's previous name"
    stop_installed_app "$LEGACY_APP" OpenCodeStatusBar
    rm -rf "$LEGACY_APP"
    if [ -e "$LEGACY_PLUGIN" ] && grep -q "Installed by OpenCode Status Bar" "$LEGACY_PLUGIN"; then
        rm -f "$LEGACY_PLUGIN"
    fi
    if [ -e "$LEGACY_CONFIG/no-autolaunch" ]; then
        mkdir -p "$CONFIG_DIR"
        mv "$LEGACY_CONFIG/no-autolaunch" "$CONFIG_DIR/no-autolaunch"
    fi
    rm -rf "$LEGACY_CONFIG"
    echo "Removed the old app, plugin, and status files. Old logs stay in ~/Library/Logs/OpenCodeStatusBar."
fi

step "Installing the OpenCode plugin"
mkdir -p "$PLUGIN_DIR"
if [ -e "$PLUGIN" ] && ! grep -q "$MARKER" "$PLUGIN"; then
    BACKUP="$PLUGIN.backup-$(date +%Y%m%d%H%M%S)"
    mv "$PLUGIN" "$BACKUP"
    warn "Moved an existing, unrelated $PLUGIN to $BACKUP."
fi
PLUGIN_URL="$("$PY" -c 'import pathlib, sys; print(pathlib.Path(sys.argv[1]).as_uri())' \
    "$REPO/integrations/coding-agent-status-bar.js")"
# Load the plugin from this folder, so `git pull` updates it on the next OpenCode restart.
printf '// %s. Re-run install.sh if you move the project folder.\nexport { default } from "%s";\n' \
    "$MARKER" "$PLUGIN_URL" >"$PLUGIN.tmp"
mv "$PLUGIN.tmp" "$PLUGIN"
echo "Installed $PLUGIN"

step "Installing the Codex hooks"
"$PY" "$REPO/integrations/coding-agent-status-bar-codex.py" install ||
    warn "Could not add the Codex hooks. The rest of the status bar still works."

step "Installing the Claude Code hooks"
"$PY" "$REPO/integrations/coding-agent-status-bar-claude.py" install ||
    warn "Could not add the Claude Code hooks. The rest of the status bar still works."

if [ "$LAUNCH" = 1 ]; then
    open "$APP"
fi

cat <<EOF

Done. Next steps:
  Fully quit OpenCode (Cmd+Q) and reopen it, so it loads the plugin.
  Until then the dropdown shows "No OpenCode instances". After that, OpenCode
  opens "$APP_NAME" automatically whenever it starts.

  For Codex: start a new Codex session, run /hooks and trust the
  Coding Agent Status Bar hooks. Codex skips them until you do.

  For Claude Code: nothing to do. New sessions report their status.

If the icon is hidden behind the notch or other menu bar icons, hold Command
and drag it further right.
EOF
