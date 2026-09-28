"""Tests for the dropdown's session rows (ui/menu.py)."""

import sys
from unittest.mock import MagicMock

import pytest

from tests.conftest import MockMenuItem

# Mock rumps before importing the menu module
if "rumps" not in sys.modules:
    mock_rumps = MagicMock()
    mock_rumps.MenuItem = MockMenuItem
    sys.modules["rumps"] = mock_rumps
else:
    sys.modules["rumps"].MenuItem = MockMenuItem

from opencode_status_bar.ui.menu import MenuBuilder, truncate_with_tooltip  # noqa: E402
from opencode_status_bar.core.models import (  # noqa: E402
    Agent,
    Instance,
    SessionStatus,
    State,
    Tool,
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
        assert [i.title for i in items] == ["No OpenCode instances"]

    def test_sessions_across_processes_and_click_shows_opencode(self, builder, on_select):
        state = connected(
            Instance(port=-1, agents=[make_agent()]),
            Instance(port=-2, agents=[make_agent("agent-2", "Second", SessionStatus.IDLE)]),
        )
        items = builder.build_dynamic_items(state, on_select=on_select)
        assert [i.title for i in items] == ["Test Agent", "Second"]
        items[0].callback(None)
        on_select.assert_called_once_with(None)

    def test_subagents_nest_under_parent_and_are_not_clickable(self, builder, on_select):
        parent = make_agent("root", "Root")
        child = make_agent("child", "Child", parent_id="root")
        idle_child = make_agent("child2", "Child 2", SessionStatus.IDLE, parent_id="root")
        items = builder.build_dynamic_items(
            connected(Instance(port=-1, agents=[child, parent, idle_child])),
            on_select=on_select,
        )
        assert [i.title for i in items] == ["Root", "Child", "Child 2"]
        assert [i.symbol_name for i in items] == ["terminal", "circle.fill", "circle"]
        assert items[1].callback is None
        items[1]._menuitem.setIndentationLevel_.assert_called_with(1)
        assert not any(ch in i.title for i in items for ch in EMOJI)

    def test_idle_process_uses_last_title_or_fallback(self, builder, on_select):
        state = connected(Instance(port=-1, agents=[]))
        items = builder.build_dynamic_items(state, on_select=on_select)
        assert items[0].title == "Port -1 (idle)"
        assert items[0].symbol_name == "moon.zzz"
        assert items[0]._menuitem.setImage_.call_args.args[0].isTemplate()
        assert items[0].callback is on_select

        # After a session was seen, the idle row reuses its title.
        builder.build_dynamic_items(connected(Instance(port=-1, agents=[make_agent()])))
        assert builder.build_dynamic_items(state)[0].title == "Test Agent (idle)"

    def test_name_cache_drops_stopped_processes_and_rotates(self, on_select):
        builder = MenuBuilder(port_names_cache={-9: "Gone"}, port_names_limit=1)
        state = connected(*[
            Instance(port=-i, agents=[make_agent(f"a{i}", f"Agent {i}")]) for i in (1, 2, 3)
        ])
        builder.build_dynamic_items(state, on_select=on_select)
        assert -9 not in builder._port_names
        assert -3 in builder._port_names and len(builder._port_names) <= 2


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
