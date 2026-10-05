"""Tests for the Claude Code hook script, run as Claude Code runs it:
`python -I -S script <event>`."""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "integrations" / "coding-agent-status-bar-claude.py"
PAYLOAD = {
    "session_id": "abc-123", "cwd": "/work/project", "hook_event_name": "UserPromptSubmit",
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
    (tmp_path / ".claude").mkdir()
    return tmp_path


def status(home, name="abc-123"):
    path = home / ".config/coding-agent-status-bar/claude" / f"{name}.json"
    return json.loads(path.read_text()) if path.exists() else None


def flags(home):
    data = status(home)
    return data["status"], data["permission"], data["question"]


def notify(kind):
    return {**PAYLOAD, "hook_event_name": "Notification", "notification_type": kind}


class TestEvents:
    def test_turn_lifecycle_writes_only_status(self, home):
        expected = [
            ("start", PAYLOAD, ("ready", False, False)),
            ("prompt", PAYLOAD, ("busy", False, False)),
            ("pre", PAYLOAD, ("busy", False, False)),
            ("permission", PAYLOAD, ("busy", True, False)),
            # A sub-agent's tool doesn't hide the pending approval.
            ("pre", {**PAYLOAD, "tool_name": "Read"}, ("busy", True, False)),
            ("post", PAYLOAD, ("busy", False, False)),
            ("stop", PAYLOAD, ("idle", False, False)),
        ]
        for event, payload, expected_flags in expected:
            result = run(home, event, payload=payload)
            assert result.returncode == 0 and result.stdout == "" and result.stderr == ""
            assert flags(home) == expected_flags
        data = status(home)
        assert set(data) == {
            "version", "pid", "updated", "directory", "status", "permission", "question",
        }
        assert data["pid"] == os.getpid() and data["directory"] == "/work/project"

        folder = home / ".config/coding-agent-status-bar/claude"
        text = (folder / "abc-123.json").read_text()
        assert "secret" not in text and "Bash" not in text
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        assert stat.S_IMODE((folder / "abc-123.json").stat().st_mode) == 0o600

        run(home, "end", payload=PAYLOAD)
        assert list(folder.iterdir()) == []

    def test_question_tool_waits_for_an_answer(self, home):
        asks = {**PAYLOAD, "tool_name": "AskUserQuestion"}
        run(home, "prompt", payload=PAYLOAD)
        run(home, "pre", payload=asks)
        assert flags(home) == ("busy", False, True)
        run(home, "permission", payload=asks)
        assert flags(home) == ("busy", False, True)
        run(home, "post", payload=asks)
        assert flags(home) == ("busy", False, False)

    @pytest.mark.parametrize("kind,expected", [
        ("permission_prompt", ("busy", True, False)),
        ("elicitation_dialog", ("busy", False, True)),
        ("elicitation_url_dialog", ("busy", False, True)),
        ("auth_success", ("busy", False, False)),
    ])
    def test_notifications_that_need_you(self, home, kind, expected):
        run(home, "prompt", payload=PAYLOAD)
        run(home, "notify", payload=notify(kind))
        assert flags(home) == expected

    def test_idle_notification_clears_an_interrupted_turn(self, home):
        run(home, "permission", payload=PAYLOAD)
        run(home, "notify", payload=notify("idle_prompt"))
        assert flags(home) == ("ready", False, False)

    def test_idle_notification_keeps_a_finished_turn(self, home):
        run(home, "stop", payload=PAYLOAD)
        before = status(home)
        run(home, "notify", payload=notify("idle_prompt"))
        assert status(home) == before

    def test_failed_turn_ends_like_stop(self, home):
        run(home, "prompt", payload=PAYLOAD)
        run(home, "stop", payload={**PAYLOAD, "hook_event_name": "StopFailure", "error": "rate_limit"})
        assert flags(home) == ("idle", False, False)

    def test_session_start_keeps_this_process_status(self, home):
        run(home, "prompt", payload=PAYLOAD)
        run(home, "start", payload={**PAYLOAD, "source": "startup"})
        assert status(home)["status"] == "busy"

    def test_session_start_replaces_an_earlier_process_status(self, home):
        folder = home / ".config/coding-agent-status-bar/claude"
        folder.mkdir()
        (folder / "abc-123.json").write_text(json.dumps({"pid": 1, "status": "busy"}))
        run(home, "start", payload={**PAYLOAD, "source": "resume"})
        assert status(home)["status"] == "ready" and status(home)["pid"] == os.getpid()

    def test_compaction_changes_nothing(self, home):
        run(home, "start", payload={**PAYLOAD, "source": "compact"})
        assert status(home) is None

    def test_claude_process_found_behind_a_shell(self, home):
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
        assert not (home / ".config/coding-agent-status-bar/claude").exists()


def test_launch_opens_app_in_background_unless_turned_off(home, monkeypatch):
    spec = importlib.util.spec_from_file_location("claude_hook", SCRIPT)
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
        "theme": "dark",
        "permissions": {"allow": ["Bash(ls)"]},
        "hooks": {
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "lint.sh"}]}],
        },
    }

    def write(self, home, data):
        (home / ".claude/settings.json").write_text(json.dumps(data))

    def read(self, home):
        return json.loads((home / ".claude/settings.json").read_text())

    def test_adds_hooks_keeping_other_settings_and_is_idempotent(self, home):
        self.write(home, self.EXISTING)
        (home / ".claude/settings.json").chmod(0o600)
        result = run(home, "install")
        assert result.returncode == 0 and "Added" in result.stdout
        settings = self.read(home)
        assert settings["theme"] == "dark" and settings["permissions"] == self.EXISTING["permissions"]
        hooks = settings["hooks"]
        assert set(hooks) == {
            "SessionStart", "UserPromptSubmit", "PreToolUse", "PermissionRequest", "PostToolUse",
            "PostToolUseFailure", "Notification", "Stop", "StopFailure", "SessionEnd",
        }
        assert hooks["PreToolUse"][0] == self.EXISTING["hooks"]["PreToolUse"][0]
        ours = hooks["PreToolUse"][1]
        assert ours["matcher"] == "*"
        assert ours["hooks"][0]["command"].endswith(f"-I -S {SCRIPT} pre")
        assert ours["hooks"][0]["timeout"] == 3
        assert "idle_prompt" in hooks["Notification"][0]["matcher"]
        assert "matcher" not in hooks["Stop"][0]
        assert hooks["StopFailure"][0]["hooks"][0]["command"].endswith(" stop")
        assert stat.S_IMODE((home / ".claude/settings.json").stat().st_mode) == 0o600
        backup = home / ".claude/settings.json.bak-coding-agent-status-bar"
        assert json.loads(backup.read_text()) == self.EXISTING

        before = (home / ".claude/settings.json").read_bytes()
        result = run(home, "install")
        assert "up to date" in result.stdout
        assert (home / ".claude/settings.json").read_bytes() == before

    # A moved folder, or hooks installed before the app was renamed from OpenCode Status Bar.
    @pytest.mark.parametrize("name", ["coding-agent-status-bar-claude.py", "opencode-status-bar-claude.py"])
    def test_replaces_and_removes_hooks_from_an_old_location(self, home, name):
        old = {"type": "command", "command": f"python /old/{name} stop"}
        self.write(home, {"hooks": {"Stop": [{"hooks": [old]}]}})
        run(home, "install")
        commands = [h["command"] for g in self.read(home)["hooks"]["Stop"] for h in g["hooks"]]
        assert len(commands) == 1 and str(SCRIPT) in commands[0]

        self.write(home, {"theme": "dark", "hooks": {"Stop": [{"hooks": [old]}]}})
        run(home, "uninstall")
        assert self.read(home) == {"theme": "dark"}

    def test_keeps_the_backup_made_under_the_previous_name(self, home):
        self.write(home, {"theme": "dark"})
        legacy = home / ".claude/settings.json.bak-opencode-status-bar"
        legacy.write_text('{"original": true}')
        run(home, "install")
        backup = home / ".claude/settings.json.bak-coding-agent-status-bar"
        assert not legacy.exists() and json.loads(backup.read_text()) == {"original": True}

    @pytest.mark.parametrize("existing", [EXISTING, {"theme": "dark"}])
    def test_uninstall_restores_settings(self, home, existing):
        self.write(home, existing)
        run(home, "install")
        result = run(home, "uninstall")
        assert result.returncode == 0
        assert self.read(home) == existing

    def test_creates_settings_file_when_missing(self, home):
        run(home, "install")
        assert len(self.read(home)["hooks"]) == 10
        assert not (home / ".claude/settings.json.bak-coding-agent-status-bar").exists()

    @pytest.mark.parametrize("content", ["{", "[]", '{"hooks": []}', '{"hooks": {"Stop": {}}}'])
    def test_unexpected_file_is_left_unchanged(self, home, content):
        (home / ".claude/settings.json").write_text(content)
        for command in ("install", "uninstall"):
            result = run(home, command)
            assert result.returncode == 1 and "left it unchanged" in result.stderr
            assert (home / ".claude/settings.json").read_text() == content

    def test_skips_without_claude_code(self, tmp_path):
        result = run(tmp_path, "install")
        assert result.returncode == 0 and "Claude Code not found" in result.stdout
        assert not (tmp_path / ".claude").exists()
