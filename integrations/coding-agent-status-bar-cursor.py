"""Cursor hooks for Coding Agent Status Bar.

Cursor runs this script on its agent's lifecycle events, with the event's JSON on stdin:

    python coding-agent-status-bar-cursor.py <start|prompt|tool|stop|end>

Each Cursor chat gets one status file in ~/.config/coding-agent-status-bar/cursor/ holding only
its status, project folder, the Cursor process's ID and a timestamp: never prompts, messages,
tool names, tool arguments or output. Hooks print only an empty answer (or "continue" for a
prompt) and never block, so Cursor behaves as before.

`install` and `uninstall` add or remove these hooks in ~/.cursor/hooks.json, leaving other hooks
untouched. Uses the standard library only, so it can run with `python -I -S`.
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
STATUS_DIR = CONFIG_DIR / "cursor"
HOOKS_FILE = Path.home() / ".cursor" / "hooks.json"
SCRIPT = Path(__file__).resolve()
MARKER = "coding-agent-status-bar-cursor.py"
TIMEOUT = 3
PRUNE_AFTER = 24 * 60 * 60
SHELLS = {"sh", "bash", "zsh", "dash", "fish", "ksh", "tcsh", "csh"}

# Cursor event -> argument passed to this script. Cursor sends no event while it waits for an
# approval or an answer, so those can't be shown.
EVENTS = {
    "sessionStart": "start",
    "beforeSubmitPrompt": "prompt",
    "postToolUse": "tool",
    "postToolUseFailure": "tool",
    "stop": "stop",
    "sessionEnd": "end",
}


# --- Hook events -------------------------------------------------------------------------


def host_pid() -> int:
    """The Cursor process running this hook, skipping a shell that didn't exec us."""
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


def project_folder(payload: dict) -> str:
    """The chat's workspace folder; Cursor sends a working directory only for some tools."""
    roots = payload.get("workspace_roots")
    if isinstance(roots, list) and roots and isinstance(roots[0], str):
        return roots[0]
    cwd = payload.get("cwd")
    return cwd if isinstance(cwd, str) else ""


def read_status(path: Path) -> dict:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_status(path: Path, payload: dict, pid: int, status: str) -> None:
    """Write atomically, readable only by you."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as file:
            json.dump({
                "version": 1,
                "pid": pid,
                "updated": int(time.time() * 1000),
                "directory": project_folder(payload),
                "status": status,
                "permission": False,
            }, file)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def prune() -> None:
    """Remove files left by chats that ended without a sessionEnd event."""
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
    # A subagent's tools report under its own ID; its chat already shows as working.
    if "parent_tool_call_id" in payload:
        return
    path = status_path(payload.get("session_id") or payload.get("conversation_id"))
    if path is None:
        return
    if event == "end":
        path.unlink(missing_ok=True)
        return
    pid = host_pid()
    if event == "start":
        # Cloud agents run on another computer; they never show here.
        if payload.get("is_background_agent") is True:
            return
        prune()
        launch_app()
        # Keep a status this process already wrote; replace one left by an earlier process.
        if read_status(path).get("pid") != pid:
            write_status(path, payload, pid, "ready")
    elif event in ("prompt", "tool"):
        write_status(path, payload, pid, "busy")
    elif event == "stop":
        write_status(path, payload, pid, "idle")


# --- Install and uninstall ---------------------------------------------------------------


def is_ours(handler: object) -> bool:
    return isinstance(handler, dict) and MARKER in str(handler.get("command", ""))


def our_hook(event: str) -> dict:
    command = f"{shlex.quote(sys.executable)} -I -S {shlex.quote(str(SCRIPT))} {EVENTS[event]}"
    return {"command": command, "timeout": TIMEOUT}


def load_hooks() -> dict:
    """Read hooks.json, refusing to rewrite a file with an unexpected shape."""
    config = json.loads(HOOKS_FILE.read_text()) if HOOKS_FILE.exists() else {}
    if not isinstance(config, dict) or not isinstance(config.get("hooks", {}), dict):
        raise ValueError("expected an object whose \"hooks\" is an object")
    for event, handlers in config.get("hooks", {}).items():
        if not isinstance(handlers, list) or not all(isinstance(h, dict) for h in handlers):
            raise ValueError(f"unexpected entries for {event}")
    return config


def save_hooks(config: dict) -> None:
    backup = HOOKS_FILE.with_name(HOOKS_FILE.name + ".bak-coding-agent-status-bar")
    if HOOKS_FILE.exists() and not backup.exists():
        backup.write_bytes(HOOKS_FILE.read_bytes())
    temporary = HOOKS_FILE.with_name(f"{HOOKS_FILE.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(config, indent=2) + "\n")
    if HOOKS_FILE.exists():
        os.chmod(temporary, stat.S_IMODE(HOOKS_FILE.stat().st_mode))
    os.replace(temporary, HOOKS_FILE)


def install() -> int:
    if not HOOKS_FILE.parent.is_dir():
        print("Cursor not found (no ~/.cursor folder); skipped the Cursor hooks.")
        return 0
    try:
        config = load_hooks()
    except ValueError as exc:
        print(f"Could not read {HOOKS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    config.setdefault("version", 1)
    hooks = config.setdefault("hooks", {})
    changed = False
    for event in EVENTS:
        handlers = hooks.get(event, [])
        if [h for h in handlers if is_ours(h)] == [our_hook(event)]:
            continue
        hooks[event] = [h for h in handlers if not is_ours(h)] + [our_hook(event)]
        changed = True
    if changed:
        save_hooks(config)
        print(f"Added the Cursor hooks to {HOOKS_FILE}.")
    else:
        print(f"The Cursor hooks in {HOOKS_FILE} are up to date.")
    return 0


def uninstall() -> int:
    if not HOOKS_FILE.exists():
        return 0
    try:
        config = load_hooks()
    except ValueError as exc:
        print(f"Could not read {HOOKS_FILE} ({exc}); left it unchanged.", file=sys.stderr)
        return 1
    hooks = config.get("hooks", {})
    changed = False
    for event in list(hooks):
        handlers = [h for h in hooks[event] if not is_ours(h)]
        if handlers != hooks[event]:
            changed = True
            if handlers:
                hooks[event] = handlers
            else:
                del hooks[event]
    if changed:
        save_hooks(config)
        print(f"Removed the Cursor hooks from {HOOKS_FILE}.")
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
        # A status bar must never disrupt Cursor.
        pass
    # Cursor reads each hook's answer; this one changes nothing.
    print(json.dumps({"continue": True} if command == "prompt" else {}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
