import json
import os
import time
from unittest.mock import AsyncMock

import pytest

from opencode_monitor.core.models import SessionStatus, Tool
from opencode_monitor.core.monitor import bridge, fetcher


@pytest.fixture
def snapshot(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge.Path, "home", lambda: tmp_path)
    path = tmp_path / ".config/opencode-monitor/bridge/status.json"
    path.parent.mkdir(parents=True)
    data = {
        "version": 1,
        "pid": os.getpid(),
        "updated": time.time() * 1000,
        "directory": "/project",
        "sessions": [{
            "id": "ses_test", "title": "Test session", "directory": "/project",
            "status": "busy", "tools": [], "question": False, "permission": False,
        }],
    }
    path.write_text(json.dumps(data))
    return path, data


@pytest.mark.parametrize("status", ["busy", "retry", "idle"])
def test_bridge_status_and_native_attention(snapshot, status):
    path, data = snapshot
    data["sessions"][0].update(status=status, question=True, permission=True)
    path.write_text(json.dumps(data))
    instances = bridge.read_bridge_instances()
    assert len(instances) == 1
    assert instances[0].port == -os.getpid()
    agent = instances[0].agents[0]
    assert agent.status == (SessionStatus.IDLE if status == "idle" else SessionStatus.BUSY)
    assert agent.has_pending_ask_user
    assert agent.tools[0].may_need_permission
    assert not Tool(name="bash", elapsed_ms=60_000, permission_pending=False).may_need_permission


@pytest.mark.parametrize("change", [
    {"updated": 0}, {"updated": float("inf")}, {"pid": -1}, {"pid": "bad"},
    {"version": 2}, {"sessions": None}, {"sessions": [{}]},
])
def test_invalid_or_stale_snapshot_is_ignored(snapshot, change):
    path, data = snapshot
    data.update(change)
    path.write_text(json.dumps(data))
    assert bridge.read_bridge_instances() == []


def test_dead_process_is_ignored(snapshot, monkeypatch):
    def dead(*args):
        raise ProcessLookupError
    monkeypatch.setattr(bridge.os, "kill", dead)
    assert bridge.read_bridge_instances() == []


def test_snapshots_group_by_process_and_deduplicate(snapshot):
    path, data = snapshot
    path.with_name("duplicate.json").write_text(json.dumps(data))
    data["sessions"][0]["id"] = "ses_second"
    path.with_name("second.json").write_text(json.dumps(data))
    instances = bridge.read_bridge_instances()
    assert len(instances) == 1
    assert {a.id for a in instances[0].agents} == {"ses_test", "ses_second"}


@pytest.mark.asyncio
async def test_bridge_detected_without_unauthenticated_server(snapshot, monkeypatch):
    monkeypatch.setattr(fetcher, "find_opencode_ports", AsyncMock(return_value=[]))
    state = await fetcher.fetch_all_instances(known_active_sessions=set())
    assert state.connected
    assert state.busy_count == 1


def test_malformed_file_does_not_hide_valid_snapshot(snapshot):
    path, _ = snapshot
    path.with_name("broken.json").write_text("{")
    assert len(bridge.read_bridge_instances()) == 1


def test_bridge_state_connected_only_with_live_snapshots(snapshot):
    path, _ = snapshot
    state = bridge.read_bridge_state()
    assert state.connected and state.busy_count == 1
    path.unlink()
    empty = bridge.read_bridge_state()
    assert not empty.connected and empty.instances == []
