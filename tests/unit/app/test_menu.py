"""Tests for the dropdown's session rows (ui/menu.py)."""

import sys
import time
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import MockMenuItem

# Mock rumps before importing the menu module
if "rumps" not in sys.modules:
    mock_rumps = MagicMock()
    mock_rumps.MenuItem = MockMenuItem
    sys.modules["rumps"] = mock_rumps
else:
    sys.modules["rumps"].MenuItem = MockMenuItem

import coding_agent_status_bar.ui.menu as menu_module  # noqa: E402
from coding_agent_status_bar.ui.menu import (  # noqa: E402
    USAGE_BAR_HEIGHT,
    USAGE_INSET,
    USAGE_ROW_SIZE,
    MenuBuilder,
    truncate_with_tooltip,
)
from coding_agent_status_bar.core.models import (  # noqa: E402
    Agent,
    HookState,
    Instance,
    SessionStatus,
    State,
    Tool,
    Usage,
    UsageLimit,
)

EMOJI = "🤖🔔🔒🔧❓🔄⏳💤└●○🔴🟠🟡🟢📅🌐⚠️"


def make_agent(aid="agent-1", title="Test Agent", status=SessionStatus.BUSY, **kwargs):
    return Agent(id=aid, title=title, dir="project", full_dir="/home/user/project",
                 status=status, **kwargs)


def connected(*instances):
    return State(connected=True, instances=list(instances))


@pytest.fixture
def builder():
    return MenuBuilder(port_names_cache={})


@pytest.fixture
def on_select():
    return MagicMock()


class TestTruncateWithTooltip:
    @pytest.mark.parametrize("text,max_length,prefix,expected,truncated", [
        ("Short", 20, "", "Short", False),
        ("A" * 20, 20, "", "A" * 20, False),
        ("This is a very long text that exceeds the limit", 20, "", "This is a very lo...", True),
        ("Hello", 20, ">>> ", ">>> Hello", False),
    ])
    def test_truncation(self, text, max_length, prefix, expected, truncated):
        item = truncate_with_tooltip(text, max_length=max_length, prefix=prefix)
        assert item.title == expected
        if truncated:
            item._menuitem.setToolTip_.assert_called_once_with(text)
        else:
            item._menuitem.setToolTip_.assert_not_called()

    def test_callback_preserved(self):
        cb = MagicMock()
        assert truncate_with_tooltip("Test", 20, callback=cb).callback is cb


class TestBuildDynamicItems:
    @pytest.mark.parametrize("state", [None, State(connected=False)])
    def test_not_connected(self, builder, state):
        items = builder.build_dynamic_items(state)
        assert [i.title for i in items] == ["OpenCode", "No OpenCode instances"]

    def test_sessions_across_processes_and_click_shows_opencode(self, builder, on_select):
        state = connected(
            Instance(port=-1, agents=[make_agent()]),
            Instance(port=-2, agents=[make_agent("agent-2", "Second", SessionStatus.IDLE)]),
        )
        items = builder.build_dynamic_items(state, on_select=on_select)
        assert [i.title for i in items] == ["OpenCode", "Test Agent", "Second"]
        # The header is a label, matching the Codex and Claude Code sections.
        assert items[0].callback is None
        items[1].callback(None)
        on_select.assert_called_once_with(None)

    def test_subagents_nest_under_parent_and_are_not_clickable(self, builder, on_select):
        parent = make_agent("root", "Root")
        child = make_agent("child", "Child", parent_id="root")
        idle_child = make_agent("child2", "Child 2", SessionStatus.IDLE, parent_id="root")
        items = builder.build_dynamic_items(
            connected(Instance(port=-1, agents=[child, parent, idle_child])),
            on_select=on_select,
        )[1:]
        assert [i.title for i in items] == ["Root", "Child", "Child 2"]
        assert [i.symbol_name for i in items] == ["terminal", "circle.fill", "circle"]
        assert items[1].callback is None
        items[1]._menuitem.setIndentationLevel_.assert_called_with(1)
        assert not any(ch in i.title for i in items for ch in EMOJI)

    def test_idle_process_uses_last_title_or_fallback(self, builder, on_select):
        state = connected(Instance(port=-1, agents=[]))
        items = builder.build_dynamic_items(state, on_select=on_select)
        assert items[1].title == "Port -1 (idle)"
        assert items[1].symbol_name == "moon.zzz"
        assert items[1]._menuitem.setImage_.call_args.args[0].isTemplate()
        assert items[1].callback is on_select

        # After a session was seen, the idle row reuses its title.
        builder.build_dynamic_items(connected(Instance(port=-1, agents=[make_agent()])))
        assert builder.build_dynamic_items(state)[1].title == "Test Agent (idle)"

    def test_name_cache_drops_stopped_processes_and_rotates(self, on_select):
        builder = MenuBuilder(port_names_cache={-9: "Gone"}, port_names_limit=1)
        state = connected(*[
            Instance(port=-i, agents=[make_agent(f"a{i}", f"Agent {i}")]) for i in (1, 2, 3)
        ])
        builder.build_dynamic_items(state, on_select=on_select)
        assert -9 not in builder._port_names
        assert -3 in builder._port_names and len(builder._port_names) <= 2


class TestBuildHookItems:
    @pytest.mark.parametrize("state", [None, HookState(running=False, sessions=[make_agent()])])
    def test_hidden_while_app_is_not_running(self, builder, state):
        assert builder.build_hook_items(state, "Codex") == []

    @pytest.mark.parametrize("name", ["Codex", "Claude Code"])
    def test_idle_app(self, builder, on_select, name):
        items = builder.build_hook_items(HookState(running=True), name, on_select=on_select)
        assert [i.title for i in items] == [name, f"{name} idle"]
        assert items[0].callback is None
        assert items[1].symbol_name == "moon.zzz" and items[1].callback is on_select

    def test_sessions_use_opencode_row_style(self, builder, on_select):
        approval = make_agent("a", "api", tools=[Tool(name="Approval required", permission_pending=True)])
        done = make_agent("b", "web", SessionStatus.IDLE)
        items = builder.build_hook_items(
            HookState(running=True, sessions=[approval, done]), "Codex", on_select=on_select
        )
        assert [i.title for i in items] == ["Codex", "api", "Approval required", "web"]
        assert [i.symbol_name for i in items[1:]] == ["hand.raised", "hand.raised", "checkmark.circle"]
        items[2]._menuitem.setToolTip_.assert_called_with("Codex is waiting for you to approve a request")
        items[1].callback(None)
        on_select.assert_called_once_with(None)
        assert not any(ch in i.title for i in items for ch in EMOJI)

    def test_claude_question_row(self, builder):
        asks = make_agent("a", "api", has_pending_ask_user=True,
                          ask_user_title="Claude Code needs your answer")
        items = builder.build_hook_items(HookState(running=True, sessions=[asks]), "Claude Code")
        assert [i.title for i in items] == ["Claude Code", "api", "Claude Code needs your answer"]
        assert [i.symbol_name for i in items[1:]] == ["questionmark.circle", "text.bubble"]


def local(hour, minute=0, day=5):
    return time.mktime((2026, 10, day, hour, minute, 0, 0, 0, -1))


def usage_parts(item):
    """The real view a usage row shows, and its parts: name, bar, percent, track, fill."""
    view = item._menuitem.setView_.call_args.args[0]
    name, bar, percent = view.subviews()
    track, fill = bar.subviews()
    return view, name, bar, percent, track, fill


def share(bar, fill):
    return fill.frame().size.width / bar.frame().size.width


class TestUsageRows:
    def section(self, builder, *limits, updated=None, sessions=(), name="Codex", on_select=None):
        usage = Usage(list(limits), local(21) if updated is None else updated)
        state = HookState(running=True, sessions=list(sessions), usage=usage)
        return builder.build_hook_items(state, name, on_select=on_select)

    def test_rows_sit_between_header_and_sessions_and_cannot_be_clicked(self, builder, on_select):
        import AppKit

        items = self.section(
            builder, UsageLimit("5-hour", 99, local(23, 18)), UsageLimit("Weekly", 43, local(23, 44, day=10)),
            sessions=[make_agent("a", "api")], on_select=on_select,
        )
        assert [i.title for i in items] == [
            "Codex", "5-hour limit: 99% left", "Weekly limit: 43% left", "api",
        ]
        assert [i.callback for i in items] == [None, None, None, on_select]
        # Unlike session rows: no icon, small gray text and a bar.
        assert not hasattr(items[1], "symbol_name")
        items[1]._menuitem.setImage_.assert_not_called()
        view, name, bar, percent, track, fill = usage_parts(items[2])
        assert (name.stringValue(), percent.stringValue()) == ("Weekly", "43% left")
        assert name.font().pointSize() == AppKit.NSFont.smallSystemFontSize()
        assert name.textColor() == AppKit.NSColor.secondaryLabelColor()
        assert share(bar, fill) == pytest.approx(0.43)
        assert fill.fillColor() == AppKit.NSColor.secondaryLabelColor()
        assert track.fillColor() == AppKit.NSColor.quaternaryLabelColor()
        assert view.toolTip() == "Codex updates it after each reply, in the app and the terminal."
        assert view.accessibilityLabel() == "Codex Weekly limit: 43% left"

    def test_low_limit_bar_is_yellow(self, builder):
        import AppKit

        items = self.section(builder, UsageLimit("5-hour", 60, local(23)), UsageLimit("Weekly", 8, local(23)))
        assert usage_parts(items[1])[5].fillColor() == AppKit.NSColor.secondaryLabelColor()
        assert usage_parts(items[2])[5].fillColor() == AppKit.NSColor.systemYellowColor()

    def test_bar_keeps_its_share_in_a_wider_menu(self, builder):
        items = self.section(builder, UsageLimit("Weekly", 43, local(23)))
        view, name, bar, percent, track, fill = usage_parts(items[1])
        view.setFrameSize_((USAGE_ROW_SIZE[0] + 140, USAGE_ROW_SIZE[1]))
        assert share(bar, fill) == pytest.approx(0.43, abs=0.01)
        assert track.frame().size.width == bar.frame().size.width
        assert percent.frame().origin.x + percent.frame().size.width == view.frame().size.width - USAGE_INSET
        assert name.frame().origin.x == USAGE_INSET

    @pytest.mark.parametrize("left,width", [(0, 0), (1, USAGE_BAR_HEIGHT)])
    def test_empty_and_nearly_empty_bars(self, builder, left, width):
        items = self.section(builder, UsageLimit("5-hour", left, local(23)))
        assert usage_parts(items[1])[5].frame().size.width == width

    def test_no_reset_or_reading_time(self, builder):
        # An old reading, and a window that has since ended.
        items = self.section(
            builder, UsageLimit("5-hour", 70, local(23)), UsageLimit("Weekly", 100, local(9), reset=True),
            updated=local(9),
        )
        assert [i.title for i in items[1:3]] == ["5-hour limit: 70% left", "Weekly limit: 100% left"]
        for item in items[1:3]:
            view, name, _, percent, _, _ = usage_parts(item)
            shown = f"{name.stringValue()} {percent.stringValue()} {view.toolTip()}"
            assert "AM" not in shown and "PM" not in shown

    def test_claude_rows_explain_where_numbers_come_from(self, builder):
        items = self.section(builder, UsageLimit("5-hour", 70), name="Claude Code")
        assert items[1].title == "5-hour limit: 70% left"
        assert "terminal" in usage_parts(items[1])[0].toolTip()

    def test_drawing_problem_leaves_a_plain_row(self, builder):
        # Patch the module this file's MenuBuilder came from; other tests reload it.
        with patch.object(menu_module, "usage_view", side_effect=RuntimeError):
            items = self.section(builder, UsageLimit("5-hour", 70, local(23)))
        assert items[1].title == "5-hour limit: 70% left" and items[1].callback is None
        items[1]._menuitem.setView_.assert_not_called()


class TestBuildAgentItems:
    @pytest.mark.parametrize("kwargs,symbol", [
        ({}, "terminal"),
        ({"status": SessionStatus.IDLE}, "checkmark.circle"),
        ({"tools": [Tool(name="Approval required", permission_pending=True)]}, "hand.raised"),
        ({"has_pending_ask_user": True}, "questionmark.circle"),
        ({"has_pending_ask_user": True,
          "tools": [Tool(name="Approval required", permission_pending=True)]}, "questionmark.circle"),
    ])
    def test_session_symbol_matches_menu_bar(self, builder, kwargs, symbol):
        items = builder.build_agent_items(make_agent(**kwargs), 0)
        assert items[0].symbol_name == symbol
        assert items[0].title == "Test Agent"

    def test_branch_suffix_removed_from_title(self, builder):
        items = builder.build_agent_items(make_agent(title="Project (@feature/x)"), 0)
        assert items[0].title == "Project"

    def test_approval_row(self, builder):
        agent = make_agent(tools=[Tool(name="Approval required", permission_pending=True)])
        items = builder.build_agent_items(agent, 0)
        assert [i.title for i in items] == ["Test Agent", "Approval required"]
        assert items[1].symbol_name == "hand.raised"
        items[1]._menuitem.setIndentationLevel_.assert_called_with(1)

    def test_tools_without_a_pending_approval_are_not_listed(self, builder):
        agent = make_agent(tools=[Tool(name="bash")])
        assert len(builder.build_agent_items(agent, 0)) == 1

    def test_question_row(self, builder):
        agent = make_agent(status=SessionStatus.IDLE, has_pending_ask_user=True,
                           ask_user_title="OpenCode needs your answer")
        items = builder.build_agent_items(agent, 0)
        assert [i.title for i in items] == ["Test Agent", "OpenCode needs your answer"]
        assert items[1].symbol_name == "text.bubble"

    def test_question_without_title_adds_no_row(self, builder):
        agent = make_agent(has_pending_ask_user=True, ask_user_title="")
        assert len(builder.build_agent_items(agent, 0)) == 1

    def test_empty_title(self, builder):
        assert builder.build_agent_items(make_agent(title=""), 0)[0].title == ""
