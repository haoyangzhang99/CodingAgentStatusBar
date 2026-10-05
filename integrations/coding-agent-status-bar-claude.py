"""Claude Code hooks for Coding Agent Status Bar.

Claude Code runs this script on its lifecycle events, with the event's JSON on stdin:

    python coding-agent-status-bar-claude.py <start|prompt|pre|permission|post|notify|stop|end>

Each Claude Code session gets one status file in ~/.config/coding-agent-status-bar/claude/ holding
only its status, project folder, Claude Code's process ID and a timestamp: never prompts,
messages, tool names, tool arguments or output. Hooks never print or block, so Claude Code
behaves as before.

`install` and `uninstall` add or remove these hooks in ~/.claude/settings.json, leaving other
hooks and settings untouched. Uses the standard library only, so it can run with `python -I -S`.
"""

import json
import os
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

BUNDLE_ID = "io.github.haoyangzhang99.CodingAgentStatusBar"
CONFIG_DIR = Path.home() / ".config" / "coding-agent-status-bar"
STATUS_DIR = CONFIG_DIR / "claude"
SETTINGS_FILE = Path.home() / ".claude" / "settings.json"
SCRIPT = Path(__file__).resolve()
# Our hook commands are recognized by this file name, or by its name before the app was
# renamed from OpenCode Status Bar.
MARKERS = ("coding-agent-status-bar-claude.py", "opencode-status-bar-claude.py")
TIMEOUT = 3
PRUNE_AFTER = 24 * 60 * 60
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"}
# The tool Claude uses to ask you a question; it waits for an answer, not an approval.
QUESTION_TOOL = "AskUserQuestion"

# Claude Code event -> argument passed to this script.
EVENTS = {
    "SessionStart": "start",
    "UserPromptSubmit": "prompt",
    "PreToolUse": "pre",
    "PermissionRequest": "permission",
    "PostToolUse": "post",
    "PostToolUseFailure": "post",
    "Notification": "notify",
    "Stop": "stop",
    "StopFailure": "stop",
    "SessionEnd": "end",
}
MATCHERS = {
    "PreToolUse": "*",
    "PermissionRequest": "*",
    "PostToolUse": "*",
    "PostToolUseFailure": "*",
    "Notification": "permission_prompt|idle_prompt|elicitation_dialog|elicitation_url_dialog",
}


# --- Hook events -------------------------------------------------------------------------


def host_pid() -> int:
    """The Claude Code process running this hook, skipping a shell that didn't exec us."""
    pid = os.getppid()
    try:
        result = subprocess.run(
            ["/bin/ps", "-o", "ppid=,comm=", "-p", str(pid)],
            capture_output=True, text=True, timeout=1,
        )
        parent, name = result.stdout.split(None, 1)
        if os.path.basename(name.strip()).lstrip("-") in SHELLS:
            return int(parent)
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return pid


def status_path(session_id: object) -> Path | None:
    if not isinstance(session_id, str):
        return None
    name = "".join(c for c in session_id if c.isalnum() or c in "-_")[:100]
    return STATUS_DIR / f"{name}.json" if name else None


def read_status(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_status(
    path: Path, payload: dict, pid: int, status: str, permission: bool, question: bool
) -> None:
    cwd = payload.get("cwd")
    data = {
        "version": 1,
        "pid": pid,
        "updated": int(time.time() * 1000),
        "directory": cwd if isinstance(cwd, str) else "",
        "status": status,
        "permission": permission,
        "question": question,
    }
    STATUS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(STATUS_DIR, 0o700)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump(data, file)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prune() -> None:
    """Remove files left by sessions that ended without a SessionEnd event."""
    cutoff = time.time() - PRUNE_AFTER
    try:
        for path in STATUS_DIR.iterdir():
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
    except OSError:
        pass


def launch_app() -> None:
    """Open the menu bar app in the background, without waiting for it."""
    if (CONFIG_DIR / "no-autolaunch").exists():
        return
    app = Path.home() / "Applications" / "Coding Agent Status Bar.app"
    # Fall back to the install path if macOS hasn't indexed the app's ID yet.
    subprocess.Popen(
        ["/bin/sh", "-c", 'open -g -b "$1" || open -g "$2"', "sh", BUNDLE_ID, str(app)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def handle(event: str, payload: dict) -> None:
    path = status_path(payload.get("session_id"))
    if path is None:
        return
    if event == "end":
        path.unlink(missing_ok=True)
        return
    previous = read_status(path)
    pid = host_pid()
    permission = previous.get("permission") is True
    question = previous.get("question") is True
    asks = payload.get("tool_name") == QUESTION_TOOL

    def write(status: str, permission: bool = False, question: bool = False) -> None:
        write_status(path, payload, pid, status, permission, question)

    if event == "start":
        # Compaction restarts a session in the middle of a turn; nothing changes for the user.
        if payload.get("source") == "compact":
            return
        prune()
        launch_app()
        # Keep a status this process already wrote; replace one left by an earlier process.
        if previous.get("pid") != pid:
            write("ready")
    elif event in ("prompt", "post"):
        write("busy")
    elif event == "pre":
        # Other tools, such as a sub-agent's, may run while a request waits for you.
        write("busy", permission, question or asks)
    elif event == "permission":
        write("busy", permission or not asks, question or asks)
    elif event == "notify":
        kind = payload.get("notification_type")
        if kind == "idle_prompt":
            # Pressing Esc ends a turn without an event; this arrives a minute later.
            if previous.get("status") != "idle":
                write("ready")
        elif kind == "permission_prompt":
            write("busy", True, question)
        elif kind in ("elicitation_dialog", "elicitation_url_dialog"):
            write("busy", permission, True)
    elif event == "stop":
        write("idle")


# --- Install and uninstall ---------------------------------------------------------------


def is_ours(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = str(handler.get("command", ""))
    return any(marker in command for marker in MARKERS)


def our_group(event: str) -> dict:
    command = f"{shlex.quote(sys.executable)} -I -S {shlex.quote(str(SCRIPT))} {EVENTS[event]}"
    group: dict = {"hooks": [{"type": "command", "command": command, "timeout": TIMEOUT}]}
    if event in MATCHERS:
        group = {"matcher": MATCHERS[event], **group}
    return group


def without_ours(groups: list) -> list:
    result = []
    for group in groups:
        handlers = [h for h in group.get("hooks", []) if not is_ours(h)]
        if handlers:
            result.append({**group, "hooks": handlers})
    return result


def load_settings() -> dict:
    """Read settings.json, refusing to rewrite a file with an unexpected shape."""
    settings = json.loads(SETTINGS_FILE.read_text()) if SETTINGS_FILE.exists() else {}
    if not isinstance(settings, dict) or not isinstance(settings.get("hooks", {}), dict):
        raise ValueError("expected an object whose \"hooks\" is an object")
    for event, groups in settings.get("hooks", {}).items():
        if not isinstance(groups, list) or not all(
            isinstance(g, dict) and isinstance(g.get("hooks", []), list) for g in groups
        ):
            raise ValueError(f"unexpected entries for {event}")
    return settings


def save_settings(settings: dict) -> None:
    backup = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".bak-coding-agent-status-bar")
    # A backup made under the app's previous name predates all of our hooks, so keep it.
    legacy = SETTINGS_FILE.with_name(SETTINGS_FILE.name + ".bak-opencode-status-bar")
    if legacy.exists() and not backup.exists():
        legacy.rename(backup)
    if SETTINGS_FILE.exists() and not backup.exists():
        backup.write_bytes(SETTINGS_FILE.read_bytes())
    temporary = SETTINGS_FILE.with_name(f"{SETTINGS_FILE.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(settings, indent=2) + "\n")
    if SETTINGS_FILE.exists():
        os.chmod(temporary, stat.S_IMODE(SETTINGS_FILE.stat().st_mode))
    os.replace(temporary, SETTINGS_FILE)


def install() -> int:
    if not SETTINGS_FILE.parent.is_dir():
        print("Claude Code not found (no ~/.claude folder); skipped the Claude Code hooks.")
        return 0
    try:
        settings = load_settings()
    except ValueError as exc:
        print(f"Could not read {SETTINGS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    hooks = settings.setdefault("hooks", {})
    changed = False
    for event in EVENTS:
        groups = hooks.get(event, [])
        mine = [g for g in groups if any(is_ours(h) for h in g.get("hooks", []))]
        if mine == [our_group(event)]:
            continue
        hooks[event] = without_ours(groups) + [our_group(event)]
        changed = True
    if changed:
        save_settings(settings)
        print(f"Added the Claude Code hooks to {SETTINGS_FILE}.")
    else:
        print(f"The Claude Code hooks in {SETTINGS_FILE} are up to date.")
    return 0


def uninstall() -> int:
    if not SETTINGS_FILE.exists():
        return 0
    try:
        settings = load_settings()
    except ValueError as exc:
        print(f"Could not read {SETTINGS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    hooks = settings.get("hooks", {})
    changed = False
    for event in list(hooks):
        groups = without_ours(hooks[event])
        if groups != hooks[event]:
            changed = True
            if groups:
                hooks[event] = groups
            else:
                del hooks[event]
    if changed:
        if not hooks:
            del settings["hooks"]
        save_settings(settings)
        print(f"Removed the Claude Code hooks from {SETTINGS_FILE}.")
    return 0


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    if command == "install":
        return install()
    if command == "uninstall":
        return uninstall()
    try:
        payload = json.load(sys.stdin)
        if isinstance(payload, dict):
            handle(command, payload)
    except Exception:
        # A status bar must never disrupt Claude Code.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
