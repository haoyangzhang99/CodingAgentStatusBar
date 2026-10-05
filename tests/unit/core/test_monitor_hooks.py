import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from opencode_status_bar.core.models import SessionStatus
from opencode_status_bar.core.monitor import hooks

APPS = {
    "codex": (hooks.read_codex_state, "com.openai.codex"),
    "claude": (hooks.read_claude_state, "com.anthropic.claudefordesktop"),
}


@pytest.fixture(params=sorted(APPS))
def app(request, tmp_path, monkeypatch):
    """(status folder, reader, desktop app bundle ID) for Codex and for Claude Code."""
    monkeypatch.setattr(hooks.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(hooks, "app_running", lambda bundle_id: False)
    path = tmp_path / ".config/opencode-status-bar" / request.param
    path.mkdir(parents=True)
    return (path, *APPS[request.param])


@pytest.fixture
def folder(app):
    return app[0]


@pytest.fixture
def read(app):
    return app[1]


def write(folder, name="ses", age=0, **changes):
    data = {
        "version": 1, "pid": os.getpid(), "updated": time.time() * 1000 - age * 1000,
        "directory": "/work/project", "status": "busy", "permission": False,
    }
    data.update(changes)
    (folder / f"{name}.json").write_text(json.dumps(data))


def test_working_session(folder, read):
    write(folder)
    state = read()
    assert state.running
    [session] = state.sessions
    assert (session.id, session.title, session.full_dir) == ("ses", "project", "/work/project")
    assert session.status == SessionStatus.BUSY and session.tools == []
    assert not session.has_pending_ask_user


def test_approval_becomes_a_pending_tool(folder, read):
    write(folder, permission=True)
    [session] = read().sessions
    assert session.tools[0].name == "Approval required" and session.tools[0].may_need_permission


def test_question_waits_for_an_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(hooks, "app_running", lambda bundle_id: False)
    folder = tmp_path / ".config/opencode-status-bar/claude"
    folder.mkdir(parents=True)
    write(folder, question=True, age=16 * 60)
    [session] = hooks.read_claude_state().sessions
    assert session.has_pending_ask_user and session.status == SessionStatus.BUSY
    assert session.ask_user_title == "Claude Code needs your answer"


@pytest.mark.parametrize("changes,listed", [
    ({"status": "idle", "age": 30}, True),            # Done for a minute
    ({"status": "idle", "age": 61}, False),
    ({"status": "ready"}, False),                     # Started, nothing to show yet
    ({"age": 16 * 60}, False),                        # Working with no event for too long
    ({"age": 16 * 60, "permission": True}, True),     # Still waiting for the user
])
def test_recent_sessions_listed_while_app_runs(folder, read, changes, listed):
    write(folder, **changes)
    state = read()
    assert state.running
    assert len(state.sessions) == (1 if listed else 0)


def test_newest_session_first(folder, read):
    write(folder, "old", age=20, directory="/a")
    write(folder, "new", age=1, directory="/b")
    assert [s.id for s in read().sessions] == ["new", "old"]


def test_exited_process_is_ignored(folder, read, monkeypatch):
    def dead(*args):
        raise ProcessLookupError
    monkeypatch.setattr(hooks.os, "kill", dead)
    write(folder)
    state = read()
    assert not state.running and state.sessions == []


@pytest.mark.parametrize("change", [
    {"version": 2}, {"pid": -1}, {"pid": "1"}, {"updated": "now"}, {"updated": float("inf")},
    {"status": "other"}, {"permission": "yes"}, {"question": 1}, {"directory": None},
])
def test_invalid_file_is_ignored(folder, read, change):
    write(folder, **change)
    (folder / "broken.json").write_text("{")
    (folder / "list.json").write_text("[]")
    state = read()
    assert not state.running and state.sessions == []


def test_desktop_app_counts_as_running(app, monkeypatch):
    _, read, bundle_id = app
    monkeypatch.setattr(hooks, "app_running", lambda b: b == bundle_id)
    state = read()
    assert state.running and state.sessions == []


def test_apps_read_only_their_own_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(hooks.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(hooks, "app_running", lambda bundle_id: False)
    folder = tmp_path / ".config/opencode-status-bar/codex"
    folder.mkdir(parents=True)
    write(folder)
    assert hooks.read_codex_state().running
    assert not hooks.read_claude_state().running


def test_app_running_checks_bundle_id():
    native = MagicMock()
    find = native.NSRunningApplication.runningApplicationsWithBundleIdentifier_
    with patch.dict(sys.modules, {"AppKit": native}):
        find.return_value = [object()]
        assert hooks.app_running("com.openai.codex")
        find.assert_called_with("com.openai.codex")
        find.return_value = []
        assert not hooks.app_running("com.openai.codex")
        find.side_effect = RuntimeError
        assert not hooks.app_running("com.openai.codex")
