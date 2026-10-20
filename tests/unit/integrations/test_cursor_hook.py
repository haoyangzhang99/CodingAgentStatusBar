"""Tests for the Cursor hook script, run as Cursor runs it: `python -I -S script <event>`."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "integrations" / "coding-agent-status-bar-cursor.py"
# What Cursor sends (3.25), with the private fields a status file must never hold.
PAYLOAD = {
    "conversation_id": "be9a6575-d391", "session_id": "be9a6575-d391", "generation_id": "g1",
    "hook_event_name": "postToolUse", "cursor_version": "3.25.9", "model": "secret-model",
    "workspace_roots": ["/work/project"], "user_email": "secret@example.com",
    "transcript_path": "/secret/transcript.jsonl", "tool_name": "Shell",
    "tool_input": {"command": "secret command"}, "tool_output": "secret output",
    "prompt": "secret prompt",
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
    (tmp_path / ".cursor").mkdir()
    return tmp_path


def folder(home):
    return home / ".config/coding-agent-status-bar/cursor"


def status(home, name="be9a6575-d391"):
    path = folder(home) / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


class TestEvents:
    def test_chat_lifecycle_writes_only_status(self, home):
        for event, expected in [
            ("start", "ready"), ("prompt", "busy"), ("tool", "busy"), ("stop", "idle"),
        ]:
            result = run(home, event, payload=PAYLOAD)
            assert result.returncode == 0 and result.stderr == ""
            assert status(home)["status"] == expected
        data = status(home)
        assert data == {
            "version": 1, "pid": os.getpid(), "updated": data["updated"],
            "directory": "/work/project", "status": "idle", "permission": False,
        }
        text = (folder(home) / "be9a6575-d391.json").read_text()
        assert "secret" not in text and "Shell" not in text
        assert stat.S_IMODE(folder(home).stat().st_mode) == 0o700
        assert stat.S_IMODE((folder(home) / "be9a6575-d391.json").stat().st_mode) == 0o600

        run(home, "end", payload=PAYLOAD)
        assert list(folder(home).iterdir()) == []

    @pytest.mark.parametrize("event,answer", [
        ("prompt", {"continue": True}), ("tool", {}), ("stop", {}), ("start", {}), ("end", {}),
    ])
    def test_answers_never_change_what_cursor_does(self, home, event, answer):
        assert json.loads(run(home, event, payload=PAYLOAD).stdout) == answer

    def test_a_prompt_is_never_blocked_even_on_bad_input(self, home):
        result = run(home, "prompt", payload=None)
        assert result.returncode == 0 and json.loads(result.stdout) == {"continue": True}

    def test_subagent_tools_are_left_to_their_chat(self, home):
        run(home, "prompt", payload=PAYLOAD)
        child = {**PAYLOAD, "conversation_id": "child", "session_id": "child",
                 "parent_tool_call_id": "tool-1"}
        run(home, "tool", payload=child)
        assert status(home, "child") is None
        assert status(home)["status"] == "busy"

    def test_conversation_id_is_used_without_session_id(self, home):
        payload = {k: v for k, v in PAYLOAD.items() if k != "session_id"}
        run(home, "prompt", payload=payload)
        assert status(home)["status"] == "busy"

    def test_working_directory_when_there_is_no_workspace(self, home):
        payload = {**PAYLOAD, "workspace_roots": [], "cwd": "/other"}
        run(home, "tool", payload=payload)
        assert status(home)["directory"] == "/other"

    def test_cloud_agents_are_not_shown(self, home):
        run(home, "start", payload={**PAYLOAD, "is_background_agent": True})
        assert status(home) is None

    def test_session_start_keeps_this_process_status(self, home):
        run(home, "prompt", payload=PAYLOAD)
        run(home, "start", payload=PAYLOAD)
        assert status(home)["status"] == "busy"

    def test_session_start_replaces_an_earlier_process_status(self, home):
        folder(home).mkdir()
        (folder(home) / "be9a6575-d391.json").write_text(json.dumps({"pid": 1, "status": "busy"}))
        run(home, "start", payload=PAYLOAD)
        assert status(home)["status"] == "ready" and status(home)["pid"] == os.getpid()

    def test_cursor_process_found_behind_a_shell(self, home):
        run(home, "prompt", payload=PAYLOAD, shell=True)
        assert status(home)["pid"] == os.getpid()

    @pytest.mark.parametrize("stdin", ["{", "[]", json.dumps({"cwd": "/x"}),
                                       json.dumps({"session_id": 5}), json.dumps({"session_id": "/../"})])
    def test_bad_input_is_ignored(self, home, stdin):
        result = subprocess.run(
            [sys.executable, "-I", "-S", str(SCRIPT), "tool"], input=stdin,
            capture_output=True, text=True, env={**os.environ, "HOME": str(home)}, timeout=30,
        )
        assert result.returncode == 0 and json.loads(result.stdout) == {}
        assert not folder(home).exists()


def test_launch_opens_app_in_background_unless_turned_off(home, monkeypatch):
    spec = importlib.util.spec_from_file_location("cursor_hook", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "CONFIG_DIR", home / ".config/coding-agent-status-bar")
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
        "version": 1,
        "hooks": {
            "afterFileEdit": [{"command": "./hooks/format.sh"}],
            "stop": [{"command": "./audit.sh", "loop_limit": 10}],
        },
    }

    def write(self, home, data):
        (home / ".cursor/hooks.json").write_text(json.dumps(data))

    def read(self, home):
        return json.loads((home / ".cursor/hooks.json").read_text())

    def test_adds_hooks_keeping_others_and_is_idempotent(self, home):
        self.write(home, self.EXISTING)
        (home / ".cursor/hooks.json").chmod(0o600)
        result = run(home, "install")
        assert result.returncode == 0 and "Added" in result.stdout
        config = self.read(home)
        hooks = config["hooks"]
        assert config["version"] == 1
        assert set(hooks) == {
            "afterFileEdit", "sessionStart", "beforeSubmitPrompt", "postToolUse",
            "postToolUseFailure", "stop", "sessionEnd",
        }
        assert hooks["afterFileEdit"] == self.EXISTING["hooks"]["afterFileEdit"]
        assert hooks["stop"][0] == self.EXISTING["hooks"]["stop"][0]
        ours = hooks["stop"][1]
        assert ours == {"command": ours["command"], "timeout": 3}
        assert ours["command"].endswith(f"-I -S {SCRIPT} stop")
        assert hooks["beforeSubmitPrompt"][0]["command"].endswith(" prompt")
        assert hooks["postToolUseFailure"][0]["command"].endswith(" tool")
        assert stat.S_IMODE((home / ".cursor/hooks.json").stat().st_mode) == 0o600
        backup = home / ".cursor/hooks.json.bak-coding-agent-status-bar"
        assert json.loads(backup.read_text()) == self.EXISTING

        before = (home / ".cursor/hooks.json").read_bytes()
        result = run(home, "install")
        assert "up to date" in result.stdout
        assert (home / ".cursor/hooks.json").read_bytes() == before

    def test_replaces_and_removes_hooks_from_an_old_location(self, home):
        old = {"command": "python /old/coding-agent-status-bar-cursor.py stop", "timeout": 3}
        self.write(home, {"version": 1, "hooks": {"stop": [old]}})
        run(home, "install")
        commands = [h["command"] for h in self.read(home)["hooks"]["stop"]]
        assert len(commands) == 1 and str(SCRIPT) in commands[0]

        self.write(home, {"version": 1, "hooks": {"stop": [old]}})
        run(home, "uninstall")
        assert self.read(home) == {"version": 1, "hooks": {}}

    def test_uninstall_restores_hooks(self, home):
        self.write(home, self.EXISTING)
        run(home, "install")
        result = run(home, "uninstall")
        assert result.returncode == 0
        assert self.read(home) == self.EXISTING

    def test_creates_hooks_file_when_missing(self, home):
        run(home, "install")
        config = self.read(home)
        assert config["version"] == 1 and len(config["hooks"]) == 6
        assert not (home / ".cursor/hooks.json.bak-coding-agent-status-bar").exists()

    @pytest.mark.parametrize("content", ["{", "[]", '{"hooks": []}', '{"hooks": {"stop": {}}}',
                                         '{"hooks": {"stop": ["x"]}}'])
    def test_unexpected_file_is_left_unchanged(self, home, content):
        (home / ".cursor/hooks.json").write_text(content)
        for command in ("install", "uninstall"):
            result = run(home, command)
            assert result.returncode == 1 and "left it unchanged" in result.stderr
            assert (home / ".cursor/hooks.json").read_text() == content

    def test_skips_without_cursor(self, tmp_path):
        result = run(tmp_path, "install")
        assert result.returncode == 0 and "Cursor not found" in result.stdout
        assert not (tmp_path / ".cursor").exists()
