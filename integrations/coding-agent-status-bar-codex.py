"""Codex hooks for Coding Agent Status Bar.

Codex runs this script on its lifecycle events, with the event's JSON on stdin:

    python coding-agent-status-bar-codex.py <start|prompt|tool|permission|stop|end>

Each Codex session gets one status file in ~/.config/coding-agent-status-bar/codex/ holding only
its status, project folder, Codex's process ID and a timestamp: never prompts, messages, tool
names, tool arguments or output. Hooks never print or block, so Codex behaves as before.

`install` and `uninstall` add or remove these hooks in ~/.codex/hooks.json, leaving other
hooks untouched. Uses the standard library only, so Codex can run it with `python -I -S`.
"""

import json
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

BUNDLE_ID = "io.github.haoyangzhang99.CodingAgentStatusBar"
CONFIG_DIR = Path.home() / ".config" / "coding-agent-status-bar"
STATUS_DIR = CONFIG_DIR / "codex"
HOOKS_FILE = Path.home() / ".codex" / "hooks.json"
SCRIPT = Path(__file__).resolve()
# Our hook commands are recognized by this file name, or by its name before the app was
# renamed from OpenCode Status Bar.
MARKERS = ("coding-agent-status-bar-codex.py", "opencode-status-bar-codex.py")
# SessionEnd and Interrupt hooks may not run longer than 3 seconds.
TIMEOUT = 3
PRUNE_AFTER = 24 * 60 * 60
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"}

# Codex event -> argument passed to this script. Tool events need a matcher.
EVENTS = {
    "SessionStart": "start",
    "UserPromptSubmit": "prompt",
    "PreToolUse": "tool",
    "PermissionRequest": "permission",
    "PostToolUse": "tool",
    "Stop": "stop",
    "Interrupt": "stop",
    "SessionEnd": "end",
}
MATCHED = {"PreToolUse", "PermissionRequest", "PostToolUse"}

# Argument -> (status, waiting for approval)
STATUS = {
    "prompt": ("busy", False),
    "tool": ("busy", False),
    "permission": ("busy", True),
    "stop": ("idle", False),
}


# --- Hook events -------------------------------------------------------------------------


def host_pid() -> int:
    """The Codex process running this hook, skipping a shell that didn't exec us."""
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


def recorded_pid(path: Path) -> object:
    """The Codex process ID in an existing status file, or None."""
    try:
        return json.loads(path.read_text()).get("pid")
    except (OSError, ValueError, AttributeError):
        return None


def write_status(path: Path, payload: dict, pid: int, status: str, permission: bool) -> None:
    cwd = payload.get("cwd")
    data = {
        "version": 1,
        "pid": pid,
        "updated": int(time.time() * 1000),
        "directory": cwd if isinstance(cwd, str) else "",
        "status": status,
        "permission": permission,
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
    elif event == "start":
        # Compaction restarts a session in the middle of a turn; nothing changes for the user.
        if payload.get("source") == "compact":
            return
        prune()
        launch_app()
        # Keep a status this process already wrote; replace one left by an earlier process,
        # such as a Codex that crashed, whose file the app would otherwise ignore.
        pid = host_pid()
        if recorded_pid(path) != pid:
            write_status(path, payload, pid, "ready", False)
    elif event in STATUS:
        write_status(path, payload, host_pid(), *STATUS[event])


# --- Install and uninstall ---------------------------------------------------------------


def is_ours(handler: object) -> bool:
    if not isinstance(handler, dict):
        return False
    command = str(handler.get("command", ""))
    return any(marker in command for marker in MARKERS)


def our_group(event: str) -> dict:
    command = f"{shlex.quote(sys.executable)} -I -S {shlex.quote(str(SCRIPT))} {EVENTS[event]}"
    group: dict = {"hooks": [{"type": "command", "command": command, "timeout": TIMEOUT}]}
    if event in MATCHED:
        group = {"matcher": "*", **group}
    return group


def without_ours(groups: list) -> list:
    result = []
    for group in groups:
        handlers = [h for h in group.get("hooks", []) if not is_ours(h)]
        if handlers:
            result.append({**group, "hooks": handlers})
    return result


def load_hooks() -> dict:
    """Read hooks.json, refusing to rewrite a file with an unexpected shape."""
    config = json.loads(HOOKS_FILE.read_text()) if HOOKS_FILE.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.setdefault("hooks", {}), dict):
        raise ValueError("expected an object with a \"hooks\" object")
    for event, groups in config["hooks"].items():
        if not isinstance(groups, list) or not all(
            isinstance(g, dict) and isinstance(g.get("hooks", []), list) for g in groups
        ):
            raise ValueError(f"unexpected entries for {event}")
    return config


def save_hooks(config: dict) -> None:
    backup = HOOKS_FILE.with_name(HOOKS_FILE.name + ".bak-coding-agent-status-bar")
    # A backup made under the app's previous name predates all of our hooks, so keep it.
    legacy = HOOKS_FILE.with_name(HOOKS_FILE.name + ".bak-opencode-status-bar")
    if legacy.exists() and not backup.exists():
        legacy.rename(backup)
    if HOOKS_FILE.exists() and not backup.exists():
        backup.write_bytes(HOOKS_FILE.read_bytes())
    temporary = HOOKS_FILE.with_name(f"{HOOKS_FILE.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n")
    os.replace(temporary, HOOKS_FILE)


def install() -> int:
    if not HOOKS_FILE.parent.is_dir():
        print("Codex not found (no ~/.codex folder); skipped the Codex hooks.")
        return 0
    try:
        config = load_hooks()
    except ValueError as exc:
        print(f"Could not read {HOOKS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    hooks = config["hooks"]
    changed = False
    for event in EVENTS:
        groups = hooks.get(event, [])
        mine = [g for g in groups if any(is_ours(h) for h in g.get("hooks", []))]
        if mine == [our_group(event)]:
            continue
        # Append, so the positions (and trust) of existing hooks stay the same.
        hooks[event] = without_ours(groups) + [our_group(event)]
        changed = True
    if changed:
        save_hooks(config)
        print(f"Added the Codex hooks to {HOOKS_FILE}.")
        print("Codex skips new hooks until you trust them: in Codex, run /hooks and trust them.")
    else:
        print(f"The Codex hooks in {HOOKS_FILE} are up to date.")
    return 0


def uninstall() -> int:
    if not HOOKS_FILE.exists():
        return 0
    try:
        config = load_hooks()
    except ValueError as exc:
        print(f"Could not read {HOOKS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    hooks = config["hooks"]
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
        save_hooks(config)
        print(f"Removed the Codex hooks from {HOOKS_FILE}.")
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
        # A status bar must never disrupt Codex.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
