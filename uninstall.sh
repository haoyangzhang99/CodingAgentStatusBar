#!/bin/bash
# Remove OpenCode Status Bar's app, plugin, and status files.
set -euo pipefail

APP_NAME="OpenCode Status Bar"
EXEC_NAME="OpenCodeStatusBar"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP="$HOME/Applications/$APP_NAME.app"
PLUGIN="$HOME/.config/opencode/plugins/opencode-status-bar.js"
MARKER="Installed by OpenCode Status Bar"
CONFIG_DIR="$HOME/.config/opencode-status-bar"
LOG_DIR="$HOME/Library/Logs/OpenCodeStatusBar"
PURGE=0

usage() {
    cat <<EOF
Usage: ./uninstall.sh [--purge]

Removes "$APP_NAME.app", the OpenCode plugin, and live status snapshots.

  --purge   Also delete logs, settings, and this folder's .venv.
EOF
}

for arg in "$@"; do
    case "$arg" in
        --purge) PURGE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) usage >&2; exit 2 ;;
    esac
done

for pid in $(pgrep -f "/Contents/MacOS/$EXEC_NAME" 2>/dev/null || true); do
    case "$(ps -o command= -p "$pid" 2>/dev/null)" in
        "$APP/Contents/MacOS/$EXEC_NAME"*) kill "$pid" 2>/dev/null || true ;;
    esac
done

if [ -d "$APP" ]; then
    rm -rf "$APP"
    echo "Removed $APP"
fi

if [ -e "$PLUGIN" ]; then
    if grep -q "$MARKER" "$PLUGIN"; then
        rm -f "$PLUGIN"
        echo "Removed $PLUGIN"
    else
        echo "Left $PLUGIN in place: it was not created by install.sh." >&2
    fi
fi

rm -rf "$CONFIG_DIR/bridge"

if [ "$PURGE" = 1 ]; then
    rm -rf "$CONFIG_DIR" "$LOG_DIR" "$REPO/.venv"
    echo "Removed logs, settings, and $REPO/.venv"
fi

cat <<EOF

Done. Quit and reopen OpenCode to unload the plugin; until then it keeps
writing status files to $CONFIG_DIR/bridge.
This project folder was left in place; delete it yourself if you no longer need it.
EOF
