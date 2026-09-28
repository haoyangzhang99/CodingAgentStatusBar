"""
Instance fetching for OpenCode monitoring.

Functions to fetch instance data and build state.
"""

import asyncio
import os
from typing import Optional

from ..models import Instance, Agent, SessionStatus, Todos, State, AgentTodos
from ..client import OpenCodeClient

from .ports import find_opencode_ports, get_tty_for_port
from .ask_user import check_pending_ask_user_from_disk
from .helpers import extract_tools_from_messages, count_todos
from .bridge import read_bridge_instances


async def fetch_instance(port: int) -> tuple[Optional[Instance], int, int, list, set]:
    """Fetch all data for an OpenCode instance
    Returns: (Instance, pending_todos, in_progress_todos, idle_candidates, busy_session_ids)
    """
    client = OpenCodeClient(port)

    # Get TTY first (sync call, but fast) - instance exists if we can get TTY
    tty = get_tty_for_port(port)

    # Get busy sessions status and all sessions
    busy_status, all_sessions = await asyncio.gather(
        client.get_status(),
        client.get_all_sessions(),
    )
    busy_status = busy_status or {}
    all_sessions = all_sessions or []

    # Build set of busy session IDs
    busy_session_ids = set(busy_status.keys())

    # Find idle sessions (in all_sessions but not in busy_status)
    idle_sessions = [
        s for s in all_sessions if (sid := s.get("id")) and sid not in busy_session_ids
    ]

    # If no sessions at all, return empty instance
    if not busy_status and not idle_sessions:
        return Instance(port=port, tty=tty, agents=[]), 0, 0, [], set()

    agents = []
    total_pending = 0
    total_in_progress = 0

    # Process busy sessions (full data fetch)
    if busy_status:
        session_ids = list(busy_status.keys())
        session_data_tasks = [client.fetch_session_data(sid) for sid in session_ids]
        session_data_list = await asyncio.gather(*session_data_tasks)

        for session_id, session_data in zip(session_ids, session_data_list):
            info = session_data.get("info", {}) or {}
            messages = session_data.get("messages")
            todos = session_data.get("todos")

            title = info.get("title", "Sans titre")
            full_dir = info.get("directory", "")
            short_dir = os.path.basename(full_dir) if full_dir else "global"
            parent_id = info.get("parentID")

            # Extract tools
            tools = extract_tools_from_messages(messages)

            # Count todos and get labels
            pending, in_progress, current_label, next_label = count_todos(todos)
            total_pending += pending
            total_in_progress += in_progress
            agent_todos = AgentTodos(
                pending=pending,
                in_progress=in_progress,
                current_label=current_label,
                next_label=next_label,
            )

            agent = Agent(
                id=session_id,
                title=title,
                dir=short_dir,
                full_dir=full_dir,
                status=SessionStatus.BUSY,
                tools=tools,
                todos=agent_todos,
                parent_id=parent_id,
            )
            agents.append(agent)

    # Collect idle sessions info for later processing (after we know all busy sessions)
    idle_candidates = []
    for session_info in idle_sessions:
        session_id = session_info.get("id", "")
        parent_id = session_info.get("parentID")

        # Skip sub-agents - they don't use MCP Notify
        if parent_id is not None:
            continue

        idle_candidates.append(session_info)

    return (
        Instance(port=port, tty=tty, agents=agents),
        total_pending,
        total_in_progress,
        idle_candidates,  # Return idle candidates for post-processing
        busy_session_ids,  # Return busy session IDs for cross-checking
    )


async def fetch_all_instances(known_active_sessions: Optional[set] = None) -> State:
    """Fetch state for all OpenCode instances

    Args:
        known_active_sessions: Optional set of session IDs we've seen as BUSY before.
                              Used to filter out zombie sessions with pending ask_user.
                              If None, all sessions with pending ask_user are shown.
    """
    # Find all ports
    ports = await find_opencode_ports()
    bridge_instances = read_bridge_instances()

    if not ports and not bridge_instances:
        return State(connected=False)

    # Fetch all instances in parallel
    instance_tasks = [fetch_instance(port) for port in ports]
    results = await asyncio.gather(*instance_tasks)

    # First pass: collect ALL busy session IDs across all ports
    # This is used to distinguish zombie sessions from active ones
    all_busy_session_ids: set[str] = set()
    for instance, _, _, _, busy_ids in results:
        if instance is not None:
            all_busy_session_ids.update(busy_ids)

    # Second pass: process results and handle idle sessions with ask_user
    seen_session_ids = {agent.id for instance in bridge_instances for agent in instance.agents}
    instances = list(bridge_instances)
    total_pending = 0
    total_in_progress = 0

    for instance, pending, in_progress, idle_candidates, _ in results:
        if instance is None:
            continue

        # Start with busy agents
        all_agents = list(instance.agents)

        # Process idle candidates: check for pending ask_user
        for session_info in idle_candidates:
            session_id = session_info.get("id", "")

            # Skip if already seen (deduplication)
            if session_id in seen_session_ids:
                continue

            # Skip zombie sessions: if we have a cache and this session was never seen as BUSY
            if (
                known_active_sessions is not None
                and session_id not in known_active_sessions
            ):
                # Session was never seen as BUSY - it's from a dead instance
                continue

            # Check for pending ask_user (with configured timeout)
            ask_user_result = check_pending_ask_user_from_disk(session_id)

            if ask_user_result.has_pending:
                title = session_info.get("title", "Sans titre")
                full_dir = session_info.get("directory", "")
                short_dir = os.path.basename(full_dir) if full_dir else "global"

                agent = Agent(
                    id=session_id,
                    title=title,
                    dir=short_dir,
                    full_dir=full_dir,
                    status=SessionStatus.IDLE,
                    tools=[],
                    todos=AgentTodos(),
                    parent_id=None,
                    has_pending_ask_user=True,
                    ask_user_title=ask_user_result.title,
                    ask_user_question=ask_user_result.question,
                    ask_user_options=ask_user_result.options,
                    ask_user_repo=ask_user_result.repo,
                    ask_user_agent=ask_user_result.agent,
                    ask_user_branch=ask_user_result.branch,
                    ask_user_urgency=ask_user_result.urgency,
                )
                all_agents.append(agent)

        # Filter out duplicate agents (keep first occurrence)
        unique_agents = []
        for agent in all_agents:
            if agent.id not in seen_session_ids:
                seen_session_ids.add(agent.id)
                unique_agents.append(agent)

        # Update instance with final agent list
        instance = Instance(
            port=instance.port,
            tty=instance.tty,
            agents=unique_agents,
        )

        instances.append(instance)
        total_pending += pending
        total_in_progress += in_progress

    if not instances:
        return State(connected=False)

    return State(
        instances=instances,
        todos=Todos(pending=total_pending, in_progress=total_in_progress),
        connected=True,
    )
