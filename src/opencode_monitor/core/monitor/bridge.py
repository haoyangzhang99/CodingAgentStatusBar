"""Read status-only snapshots from the local OpenCode plugin, without API secrets."""

import json
import os
import time
from pathlib import Path

from ..models import Agent, Instance, SessionStatus, State, Tool


def read_bridge_state() -> State:
    """Build the complete menu bar state from live bridge snapshots only."""
    instances = read_bridge_instances()
    return State(instances=instances, connected=bool(instances))


def read_bridge_instances() -> list[Instance]:
    instances: dict[int, Instance] = {}
    seen: set[str] = set()
    now = time.time() * 1000
    for path in sorted((Path.home() / ".config/opencode-monitor/bridge").glob("*.json")):
        try:
            snapshot = json.loads(path.read_text())
            pid = snapshot["pid"]
            if (
                snapshot["version"] != 1
                or type(pid) is not int
                or pid <= 0
                or not 0 <= now - snapshot["updated"] <= 15_000
            ):
                continue
            os.kill(pid, 0)
            agents = []
            for session in snapshot["sessions"]:
                sid = session["id"]
                directory = session["directory"]
                title = session["title"]
                if not all(isinstance(value, str) for value in (sid, directory, title)):
                    raise ValueError("Invalid session metadata")
                if session["status"] not in ("busy", "retry", "idle"):
                    raise ValueError("Invalid session status")
                if type(session["question"]) is not bool or type(session["permission"]) is not bool:
                    raise ValueError("Invalid attention state")
                if sid in seen:
                    continue
                agents.append(Agent(
                    id=sid,
                    title=title,
                    dir=os.path.basename(directory) or "global",
                    full_dir=directory,
                    status=SessionStatus.IDLE if session["status"] == "idle" else SessionStatus.BUSY,
                    parent_id=session.get("parentID"),
                    tools=[Tool(name="Approval required", permission_pending=True)]
                    if session["permission"] else [],
                    has_pending_ask_user=session["question"],
                    ask_user_title="OpenCode needs your answer" if session["question"] else "",
                ))
            # Negative PIDs identify bridge instances; they are not HTTP ports.
            instance = instances.setdefault(pid, Instance(port=-pid))
            instance.agents.extend(agents)
            seen.update(agent.id for agent in agents)
        except (OSError, ValueError, KeyError, TypeError):
            # Incomplete, stale or stopped writers must never appear as live sessions.
            continue
    return list(instances.values())
