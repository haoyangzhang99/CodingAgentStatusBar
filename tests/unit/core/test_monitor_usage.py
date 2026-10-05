import json
import os
import time
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from coding_agent_status_bar.core.models import UsageLimit
from coding_agent_status_bar.core.monitor import usage

NOW = time.time()
RESETS = NOW + 3600


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(usage.Path, "home", lambda: tmp_path)
    return tmp_path


def record(when, used5=1.0, used7=57.0, resets=RESETS, limit_id="codex", limits="default"):
    """A Codex usage record, as Codex writes it after each reply."""
    if limits == "default":
        limits = {
            "limit_id": limit_id, "limit_name": None, "plan_type": "plus",
            "primary": {"used_percent": used5, "window_minutes": 300, "resets_at": resets},
            "secondary": {"used_percent": used7, "window_minutes": 10080, "resets_at": resets + 86400},
        }
    stamp = datetime.fromtimestamp(when, timezone.utc).isoformat().replace("+00:00", "Z")
    return json.dumps({"timestamp": stamp, "type": "event_msg",
                       "payload": {"type": "token_count", "info": None, "rate_limits": limits}})


def session(home, *lines, name="a", day="2026/10/05", modified=None):
    path = home / ".codex/sessions" / day / f"rollout-{name}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
    if modified is not None:
        os.utime(path, (modified, modified))
    return path


PROMPT = json.dumps({"type": "response_item", "payload": {"type": "message", "content": "secret prompt"}})


class TestCodex:
    def test_latest_reading(self, home):
        session(home, PROMPT, record(NOW - 120, used5=5), record(NOW - 60), PROMPT)
        reading = usage.read_codex_usage(now=NOW)
        assert reading.limits == [
            UsageLimit("5-hour", 99, RESETS), UsageLimit("Weekly", 43, RESETS + 86400),
        ]
        assert reading.updated == pytest.approx(NOW - 60, abs=0.01)

    def test_newest_reading_wins_across_files(self, home):
        # The most recently written file can hold an older reading.
        session(home, record(NOW - 300, used5=80), PROMPT, name="busy", modified=NOW)
        session(home, record(NOW - 30, used5=20), name="other", modified=NOW - 10)
        assert usage.read_codex_usage(now=NOW).limits[0].left == 80

    def test_old_sessions_rewritten_without_readings_are_looked_past(self, home):
        # Opening Codex rewrites older sessions; the newest reading is in a file changed earlier.
        for i in range(5):
            session(home, record(NOW - 86400, used7=32), name=f"old{i}", day="2026/10/04", modified=NOW - i)
        session(home, PROMPT, name="new", modified=NOW)
        session(home, record(NOW - 3600, used7=57), name="latest", day="2026/10/05", modified=NOW - 3600)
        assert usage.read_codex_usage(now=NOW).limits[1].left == 43

    def test_files_changed_before_the_newest_reading_are_not_read(self, home):
        session(home, record(NOW - 60), name="latest", modified=NOW - 60)
        session(home, record(NOW - 7200), name="older", modified=NOW - 3600)
        with patch.object(usage, "latest_codex_record", wraps=usage.latest_codex_record) as read:
            usage.read_codex_usage(now=NOW)
        assert [call.args[0].split("/")[-1] for call in read.call_args_list] == ["rollout-latest.jsonl"]

    @pytest.mark.parametrize("newer", [
        record(NOW - 10, used5=70, limit_id="premium"),  # A single model's limit
        record(NOW - 10, limits=None),                    # No subscription
        '{"payload": {"type": "token_count", "rate_limits": {', # Cut off mid-write
    ], ids=["model limit", "no subscription", "cut off"])
    def test_skips_records_that_are_not_plan_usage(self, home, newer):
        session(home, record(NOW - 60), newer)
        assert usage.read_codex_usage(now=NOW).limits[0].left == 99

    def test_finds_a_reading_behind_large_output(self, home):
        big = json.dumps({"type": "response_item", "payload": {"output": "x" * 400_000}})
        session(home, record(NOW - 60), big)
        assert usage.read_codex_usage(now=NOW).limits[0].left == 99

    def test_ended_window_shows_all_left(self, home):
        session(home, record(NOW - 7200, used5=96, resets=NOW - 10))
        five_hour, weekly = usage.read_codex_usage(now=NOW).limits
        assert (five_hour.left, five_hour.reset, five_hour.low) == (100, True, False)
        assert (weekly.left, weekly.reset) == (43, False)

    def test_rounds_down_so_a_low_limit_is_never_hidden(self, home):
        session(home, record(NOW - 60, used5=90.4))
        limit = usage.read_codex_usage(now=NOW).limits[0]
        assert limit.left == 9 and limit.low

    @pytest.mark.parametrize("lines", [[], [PROMPT], [record(NOW, limits={"primary": None})]])
    def test_no_reading(self, home, lines):
        session(home, *lines)
        assert usage.read_codex_usage(now=NOW) is None

    def test_without_codex(self, home):
        assert usage.read_codex_usage(now=NOW) is None

    def test_only_recent_days_are_searched(self, home):
        for day in ("2026/09/29", "2026/09/30", "2026/10/01"):
            (home / ".codex/sessions" / day).mkdir(parents=True)
        root = home / ".codex/sessions"
        assert usage.newest_folders(root, 3, 2) == [root / "2026/10/01", root / "2026/09/30"]

    def test_unchanged_files_are_not_read_again(self, home):
        session(home, record(NOW - 60))
        with patch.object(usage, "latest_codex_record", wraps=usage.latest_codex_record) as read:
            usage.read_codex_usage(now=NOW)
            usage.read_codex_usage(now=NOW)
        assert read.call_count == 1

    @pytest.mark.parametrize("minutes,name", [
        (300, "5-hour"), (10080, "Weekly"), (1440, "1-day"), (90, "90-minute"),
    ])
    def test_window_names(self, minutes, name):
        assert usage.window_name(minutes) == name


def claude_file(home, data):
    path = home / ".config/coding-agent-status-bar/claude-usage.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def claude_usage(**limits):
    return {"version": 1, "updated": (NOW - 60) * 1000, "limits": limits}


class TestClaude:
    def test_saved_reading(self, home):
        claude_file(home, claude_usage(
            five_hour={"used_percentage": 23.5, "resets_at": RESETS},
            seven_day={"used_percentage": 41, "resets_at": RESETS + 86400},
        ))
        reading = usage.read_claude_usage(now=NOW)
        assert reading.limits == [
            UsageLimit("5-hour", 76, RESETS), UsageLimit("Weekly", 59, RESETS + 86400),
        ]
        assert reading.updated == pytest.approx(NOW - 60)

    def test_ended_window_shows_all_left(self, home):
        claude_file(home, claude_usage(five_hour={"used_percentage": 99, "resets_at": NOW - 1}))
        [limit] = usage.read_claude_usage(now=NOW).limits
        assert (limit.left, limit.reset) == (100, True)

    @pytest.mark.parametrize("data", [
        {**claude_usage(five_hour={"used_percentage": 1, "resets_at": RESETS}), "version": 2},
        {**claude_usage(five_hour={"used_percentage": 1, "resets_at": RESETS}), "updated": "now"},
        {"version": 1, "updated": 1, "limits": []},
        claude_usage(five_hour={"used_percentage": "1", "resets_at": RESETS}),
        claude_usage(),
        [],
    ])
    def test_invalid_file(self, home, data):
        claude_file(home, data)
        assert usage.read_claude_usage(now=NOW) is None

    def test_no_file(self, home):
        assert usage.read_claude_usage(now=NOW) is None
