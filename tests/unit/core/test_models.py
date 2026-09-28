"""Tests for the data models filled in from the plugin's snapshots."""

import pytest

from opencode_status_bar.core.models import Agent, Instance, SessionStatus, State, Tool


def agent(aid="a", status=SessionStatus.BUSY, **kwargs):
    return Agent(id=aid, title="T", dir="p", full_dir="/p", status=status, **kwargs)


@pytest.mark.parametrize("member,value", [("IDLE", "idle"), ("BUSY", "busy")])
def test_session_status_values(member, value):
    assert SessionStatus[member].value == value


@pytest.mark.parametrize("pending", [True, False])
def test_tool_permission_comes_only_from_plugin(pending):
    assert Tool(name="Approval required", permission_pending=pending).may_need_permission is pending


def test_tool_defaults_to_no_permission_request():
    assert not Tool(name="bash").may_need_permission


@pytest.mark.parametrize("parent_id,is_sub", [(None, False), ("ses_parent", True)])
def test_agent_defaults_and_subagent(parent_id, is_sub):
    a = agent(parent_id=parent_id)
    assert a.is_subagent is is_sub
    assert a.tools == [] and not a.has_pending_ask_user and a.ask_user_title == ""


def test_agent_lists_are_independent():
    first, second = agent("1"), agent("2")
    first.tools.append(Tool(name="x"))
    assert second.tools == []


def test_instance_counts():
    inst = Instance(port=-1, agents=[
        agent("1"), agent("2"), agent("3", SessionStatus.IDLE),
    ])
    assert (inst.agent_count, inst.busy_count, inst.idle_count) == (3, 2, 1)
    assert Instance(port=-2).agent_count == 0


def test_state_defaults():
    state = State()
    assert state.instances == [] and not state.connected
    assert (state.instance_count, state.agent_count, state.busy_count, state.idle_count) == (0, 0, 0, 0)
    assert not state.has_pending_ask_user
    assert isinstance(state.updated, int)


def test_state_totals_across_instances():
    state = State(connected=True, instances=[
        Instance(port=-1, agents=[agent("1"), agent("2", SessionStatus.IDLE)]),
        Instance(port=-2, agents=[agent("3", has_pending_ask_user=True)]),
    ])
    assert (state.instance_count, state.agent_count, state.busy_count, state.idle_count) == (2, 3, 2, 1)
    assert state.has_pending_ask_user
