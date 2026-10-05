#!/bin/bash
# Remove Coding Agent Status Bar's app, plugin, Codex and Claude Code hooks, and status files.
set -euo pipefail

APP_NAME="Coding Agent Status Bar"
EXEC_NAME="CodingAgentStatusBar"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
APP="$HOME/Applications/$APP_NAME.app"
PLUGIN="$HOME/.config/opencode/plugins/coding-agent-status-bar.js"
MARKER="Installed by Coding Agent Status Bar"
CONFIG_DIR="$HOME/.config/coding-agent-status-bar"
LOG_DIR="$HOME/Library/Logs/CodingAgentStatusBar"
PURGE=0

usage() {
    cat <<EOF
Usage: ./uninstall.sh [--purge]

Removes "$APP_NAME.app", the OpenCode plugin, the Codex and Claude Code hooks, and
live status files.

  --purge   Also delete logs and this folder's .venv.
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

PY="$REPO/.venv/bin/python"
[ -x "$PY" ] || PY=python3
"$PY" "$REPO/integrations/coding-agent-status-bar-codex.py" uninstall ||
    echo "Could not remove the Codex hooks from ~/.codex/hooks.json; remove them yourself." >&2
"$PY" "$REPO/integrations/coding-agent-status-bar-claude.py" uninstall ||
    echo "Could not remove the Claude Code hooks from ~/.claude/settings.json; remove them yourself." >&2

rm -rf "$CONFIG_DIR/bridge" "$CONFIG_DIR/codex" "$CONFIG_DIR/claude" \
    "$CONFIG_DIR/claude-usage.json" "$CONFIG_DIR/dismissed-reminders.json"

if [ "$PURGE" = 1 ]; then
    # Logs from before the app was renamed from OpenCode Status Bar.
    rm -rf "$CONFIG_DIR" "$LOG_DIR" "$HOME/Library/Logs/OpenCodeStatusBar" "$REPO/.venv"
    echo "Removed logs and $REPO/.venv"
fi

cat <<EOF

Done. Quit and reopen OpenCode to unload the plugin; until then it keeps
writing status files to $CONFIG_DIR/bridge.
This project folder was left in place; delete it yourself if you no longer need it.
EOF
