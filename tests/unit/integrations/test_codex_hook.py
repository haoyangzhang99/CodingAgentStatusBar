"""Tests for the Codex hook script, run as Codex runs it: `python -I -S script <event>`."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "integrations" / "coding-agent-status-bar-codex.py"
PAYLOAD = {
    "session_id": "01a1-session", "cwd": "/work/project", "hook_event_name": "UserPromptSubmit",
    "prompt": "secret prompt", "tool_name": "Bash", "tool_input": {"command": "secret command"},
}


def run(home, *args, payload=None, shell=False):
    command = [sys.executable, "-I", "-S", str(SCRIPT), *args]
    if shell:
        # "; true" stops the shell from exec'ing the script, as some shells do.
        command = ["/bin/sh", "-c", " ".join(f"'{part}'" for part in command) + "; true"]
    return subprocess.run(
        command, input="" if payload is None else json.dumps(payload),
        capture_output=True, text=True, env={**os.environ, "HOME": str(home)}, timeout=30,
    )


@pytest.fixture
def home(tmp_path):
    (tmp_path / ".config/coding-agent-status-bar").mkdir(parents=True)
    # Never open the real app from tests.
    (tmp_path / ".config/coding-agent-status-bar/no-autolaunch").touch()
    (tmp_path / ".codex").mkdir()
    return tmp_path


def status(home, name="01a1-session"):
    path = home / ".config/coding-agent-status-bar/codex" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


class TestEvents:
    def test_turn_lifecycle_writes_only_status(self, home):
        expected = [
            ("start", "ready", False), ("prompt", "busy", False), ("tool", "busy", False),
            ("permission", "busy", True), ("tool", "busy", False), ("stop", "idle", False),
        ]
        for event, state, permission in expected:
            result = run(home, event, payload=PAYLOAD)
            assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
            data = status(home)
            assert data["status"] == state and data["permission"] is permission
        assert set(data) == {"version", "pid", "updated", "directory", "status", "permission"}
        assert data["pid"] == os.getpid() and data["directory"] == "/work/project"

        folder = home / ".config/coding-agent-status-bar/codex"
        text = (folder / "01a1-session.json").read_text()
        assert "secret" not in text and "Bash" not in text
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        assert stat.S_IMODE((folder / "01a1-session.json").stat().st_mode) == 0o600

        run(home, "end", payload=PAYLOAD)
        assert list(folder.iterdir()) == []

    def test_interrupt_and_stop_both_end_the_turn(self, home):
        run(home, "permission", payload=PAYLOAD)
        run(home, "stop", payload={**PAYLOAD, "hook_event_name": "Interrupt"})
        assert status(home)["status"] == "idle" and not status(home)["permission"]

    def test_session_start_keeps_this_process_status(self, home):
        run(home, "prompt", payload=PAYLOAD)
        run(home, "start", payload={**PAYLOAD, "source": "startup"})
        assert status(home)["status"] == "busy"

    @pytest.mark.parametrize("content", [
        json.dumps({"pid": 1, "status": "busy", "permission": True}), "{", "[]",
    ])
    def test_session_start_replaces_an_earlier_process_status(self, home, content):
        folder = home / ".config/coding-agent-status-bar/codex"
        folder.mkdir()
        (folder / "01a1-session.json").write_text(content)
        run(home, "start", payload={**PAYLOAD, "source": "resume"})
        data = status(home)
        assert (data["status"], data["permission"], data["pid"]) == ("ready", False, os.getpid())

    def test_compaction_changes_nothing(self, home):
        run(home, "start", payload={**PAYLOAD, "source": "compact"})
        assert status(home) is None

    def test_codex_process_found_behind_a_shell(self, home):
        run(home, "prompt", payload=PAYLOAD, shell=True)
        assert status(home)["pid"] == os.getpid()

    @pytest.mark.parametrize("stdin", ["{", "[]", json.dumps({"cwd": "/x"}),
                                       json.dumps({"session_id": 5}), json.dumps({"session_id": "/../"})])
    def test_bad_input_is_ignored(self, home, stdin):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPT), "prompt"], input=stdin,
            capture_output=True, text=True, env={**os.environ, "HOME": str(home)}, timeout=30,
        )
        assert result.returncode == 0 and result.stdout == ""
        assert not (home / ".config/coding-agent-status-bar/codex").exists()

    def test_unsafe_session_id_stays_in_status_folder(self, home):
        run(home, "prompt", payload={**PAYLOAD, "session_id": "../../escape"})
        assert [p.name for p in (home / ".config/coding-agent-status-bar/codex").iterdir()] == ["escape.json"]


def load_module(monkeypatch, home):
    spec = importlib.util.spec_from_file_location("codex_hook", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CONFIG_DIR", home / ".config/coding-agent-status-bar")
    return module


def test_launch_opens_app_in_background_unless_turned_off(home, monkeypatch):
    module = load_module(monkeypatch, home)
    popen = MagicMock()
    monkeypatch.setattr(module.subprocess, "Popen", popen)
    module.launch_app()
    popen.assert_not_called()

    (home / ".config/coding-agent-status-bar/no-autolaunch").unlink()
    module.launch_app()
    args = popen.call_args.args[0]
    assert args[:2] == ["/bin/sh", "-c"] and "open -g -b" in args[2]
    assert args[4] == "io.github.haoyangzhang99.CodingAgentStatusBar"
    assert popen.call_args.kwargs["start_new_session"] is True


class TestInstall:
    EXISTING = {
        "description": "Mine",
        "hooks": {
            "PreToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "node update.js pre"}]}],
            "Stop": [{"hooks": [{"type": "command", "command": "node update.js stop"}]}],
        },
    }

    def write(self, home, data):
        (home / ".codex/hooks.json").write_text(json.dumps(data))

    def read(self, home):
        return json.loads((home / ".codex/hooks.json").read_text())

    def test_appends_after_existing_hooks_and_is_idempotent(self, home):
        self.write(home, self.EXISTING)
        result = run(home, "install")
        assert result.returncode == 0 and "/hooks" in result.stdout
        hooks = self.read(home)["hooks"]
        assert self.read(home)["description"] == "Mine"
        assert set(hooks) == {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest",
            "PostToolUse", "Stop", "Interrupt", "SessionEnd",
        }
        # Existing hooks keep their positions, so Codex keeps trusting them.
        assert hooks["PreToolUse"][0] == self.EXISTING["hooks"]["PreToolUse"][0]
        assert hooks["Stop"][0] == self.EXISTING["hooks"]["Stop"][0]
        ours = hooks["PreToolUse"][1]
        assert ours["matcher"] == "*"
        assert ours["hooks"][0]["command"].endswith(f"-I -S {SCRIPT} tool")
        assert ours["hooks"][0]["timeout"] == 3
        assert "matcher" not in hooks["Stop"][1]
        assert hooks["Interrupt"][0]["hooks"][0]["command"].endswith(" stop")
        backup = home / ".codex/hooks.json.bak-coding-agent-status-bar"
        assert json.loads(backup.read_text()) == self.EXISTING

        before = (home / ".codex/hooks.json").read_bytes()
        result = run(home, "install")
        assert "up to date" in result.stdout
        assert (home / ".codex/hooks.json").read_bytes() == before

    # A moved folder, or hooks installed before the app was renamed from OpenCode Status Bar.
    @pytest.mark.parametrize("name", ["coding-agent-status-bar-codex.py", "opencode-status-bar-codex.py"])
    def test_replaces_and_removes_hooks_from_an_old_location(self, home, name):
        old = {"type": "command", "command": f"python /old/{name} stop"}
        self.write(home, {"hooks": {"Stop": [{"hooks": [old]}]}})
        run(home, "install")
        commands = [h["command"] for g in self.read(home)["hooks"]["Stop"] for h in g["hooks"]]
        assert len(commands) == 1 and str(SCRIPT) in commands[0]

        self.write(home, {"hooks": {"Stop": [{"hooks": [old]}]}})
        run(home, "uninstall")
        assert self.read(home) == {"hooks": {}}

    def test_keeps_the_backup_made_under_the_previous_name(self, home):
        self.write(home, {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x"}]}]}})
        legacy = home / ".codex/hooks.json.bak-opencode-status-bar"
        legacy.write_text('{"original": true}')
        run(home, "install")
        backup = home / ".codex/hooks.json.bak-coding-agent-status-bar"
        assert not legacy.exists() and json.loads(backup.read_text()) == {"original": True}

    def test_uninstall_restores_other_hooks(self, home):
        self.write(home, self.EXISTING)
        run(home, "install")
        result = run(home, "uninstall")
        assert result.returncode == 0
        assert self.read(home) == self.EXISTING

    def test_creates_hooks_file_when_missing(self, home):
        run(home, "install")
        assert len(self.read(home)["hooks"]) == 8
        assert not (home / ".codex/hooks.json.bak-coding-agent-status-bar").exists()

    @pytest.mark.parametrize("content", ["{", "[]", '{"hooks": []}', '{"hooks": {"Stop": {}}}'])
    def test_unexpected_file_is_left_unchanged(self, home, content):
        (home / ".codex/hooks.json").write_text(content)
        for command in ("install", "uninstall"):
            result = run(home, command)
            assert result.returncode == 1 and "left it unchanged" in result.stderr
            assert (home / ".codex/hooks.json").read_text() == content

    def test_skips_without_codex(self, tmp_path):
        result = run(tmp_path, "install")
        assert result.returncode == 0 and "Codex not found" in result.stdout
        assert not (tmp_path / ".codex").exists()
