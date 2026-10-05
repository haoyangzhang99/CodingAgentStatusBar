import json
import time

import pytest

from coding_agent_status_bar.core import reminders
from coding_agent_status_bar.core.models import HookState, Usage, UsageLimit

NOW = time.time()
LATER = NOW + 3600


def app(*limits, running=True):
    return HookState(running=running, usage=Usage(list(limits), NOW))


@pytest.fixture
def saved(tmp_path, monkeypatch):
    path = tmp_path / "dismissed-reminders.json"
    monkeypatch.setattr(reminders, "dismissed_file", lambda: path)
    return path


@pytest.mark.parametrize("left,low", [(9, True), (10, False), (0, True)])
def test_low_means_less_than_ten_percent_left(left, low):
    apps = {"Codex": app(UsageLimit("5-hour", left, LATER))}
    assert (reminders.reminder_for(apps, []) is not None) is low


def test_lowest_limit_is_shown():
    apps = {
        "Codex": app(UsageLimit("5-hour", 60, LATER), UsageLimit("Weekly", 8, LATER)),
        "Claude Code": app(UsageLimit("5-hour", 3, LATER)),
    }
    assert reminders.reminder_for(apps, []) == "Claude Code: 3% left"


def test_apps_that_are_not_running_are_ignored():
    apps = {"Codex": app(UsageLimit("5-hour", 3, LATER), running=False), "Claude Code": None}
    assert reminders.reminder_for(apps, []) is None


def test_dismissing_lasts_until_the_limit_resets():
    dismissed: list = []
    low = UsageLimit("Weekly", 8, LATER)
    apps = {"Codex": app(low)}
    assert reminders.dismiss(apps, dismissed, NOW)
    assert reminders.reminder_for(apps, dismissed) is None
    assert not reminders.dismiss(apps, dismissed, NOW)
    # Lower still, same window: stays dismissed.
    assert reminders.reminder_for({"Codex": app(UsageLimit("Weekly", 2, LATER + 60))}, dismissed) is None
    # The next window is low again: reminded again.
    next_week = {"Codex": app(UsageLimit("Weekly", 5, LATER + 7 * 86400))}
    assert reminders.reminder_for(next_week, dismissed) == "Codex: 5% left"
    # Another app's limit with the same name is separate.
    assert reminders.reminder_for({"Claude Code": app(low)}, dismissed) == "Claude Code: 8% left"


def test_dismissing_drops_windows_that_have_reset():
    dismissed = [{"app": "Codex", "limit": "5-hour", "resets_at": NOW - 10}]
    reminders.dismiss({"Codex": app(UsageLimit("Weekly", 8, LATER))}, dismissed, NOW)
    assert dismissed == [{"app": "Codex", "limit": "Weekly", "resets_at": LATER}]


def test_saved_dismissals_survive_a_restart(saved):
    entries = [{"app": "Codex", "limit": "Weekly", "resets_at": LATER}]
    reminders.save_dismissed(entries)
    assert reminders.load_dismissed(NOW) == entries
    assert json.loads(saved.read_text()) == entries


@pytest.mark.parametrize("content", [
    "{", "{}", json.dumps([{"app": "Codex", "limit": "Weekly", "resets_at": NOW - 1}]),
    json.dumps([{"app": "Codex", "limit": "Weekly"}, "x", {"app": 1, "limit": "Weekly", "resets_at": LATER}]),
], ids=["truncated", "not a list", "reset", "malformed"])
def test_ended_or_invalid_dismissals_are_not_loaded(saved, content):
    saved.write_text(content)
    assert reminders.load_dismissed(NOW) == []


def test_no_saved_dismissals(saved):
    assert reminders.load_dismissed(NOW) == []
