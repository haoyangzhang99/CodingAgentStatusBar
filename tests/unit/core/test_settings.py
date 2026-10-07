import json
import os
import subprocess
import sys

import pytest

from coding_agent_status_bar.core import settings
from coding_agent_status_bar.core.models import HookState, Instance, State, Usage, UsageLimit


@pytest.fixture
def saved(tmp_path, monkeypatch):
    path = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(settings, "settings_file", lambda: path)
    return path


def test_everything_is_on_until_turned_off(saved):
    assert settings.load_settings() == settings.DEFAULTS
    assert all(settings.DEFAULTS.values())


def test_saved_settings_survive_a_restart(saved):
    settings.save_settings({**settings.DEFAULTS, "refresh": False})
    assert settings.load_settings() == {**settings.DEFAULTS, "refresh": False}
    assert oct(saved.parent.stat().st_mode & 0o777) == "0o700"


@pytest.mark.parametrize("content", [
    "not json",
    "[]",
    json.dumps({"refresh": "no", "codex": 0, "unknown": False}),
])
def test_unreadable_settings_fall_back_to_defaults(saved, content):
    saved.parent.mkdir(parents=True)
    saved.write_text(content)
    assert settings.load_settings() == settings.DEFAULTS


def test_every_requirement_is_a_setting():
    keys = [setting.key for setting in settings.SETTINGS]
    assert len(keys) == len(set(keys))
    assert all(s.requires in keys for s in settings.SETTINGS if s.requires)


def usage_app():
    return HookState(running=True, usage=Usage([UsageLimit("Weekly", 8, 1)], 0))


def test_visible_states_leave_out_what_is_turned_off():
    state = State(connected=True, instances=[Instance(port=1)])
    codex, claude = usage_app(), usage_app()
    assert settings.visible_states(settings.DEFAULTS, state, codex, claude) == (
        state, codex, claude
    )

    off = {**settings.DEFAULTS, "opencode": False, "claude": False, "codex_usage": False}
    visible_state, visible_codex, visible_claude = settings.visible_states(
        off, state, codex, claude
    )
    assert visible_state is None and visible_claude is None
    assert visible_codex is not None and visible_codex.usage is None
    assert visible_codex.running
    # The app's own copy is left alone.
    assert codex.usage is not None


@pytest.mark.skipif(sys.platform != "darwin", reason="AppKit requires macOS")
def test_settings_window_builds_with_appkit():
    """The window builds with real AppKit and a switch click reaches the callback."""
    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "src"))
    script = (
        "import AppKit\n"
        "from coding_agent_status_bar.core.settings import DEFAULTS, SETTINGS\n"
        "from coding_agent_status_bar.ui.settings import SettingsWindow\n"
        "changes = []\n"
        "window = SettingsWindow(lambda key, on: changes.append((key, on)))\n"
        "assert set(window._switches) == {s.key for s in SETTINGS}\n"
        "window.update({**DEFAULTS, 'codex': False})\n"
        "assert not window._switches['codex_usage'].isEnabled()\n"
        "assert window._switches['claude_usage'].isEnabled()\n"
        "switch = window._switches['refresh']\n"
        "switch.setState_(AppKit.NSControlStateValueOff)\n"
        "switch.sendAction_to_(switch.action(), switch.target())\n"
        "assert changes == [('refresh', False)], changes\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": src},
        capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stderr
