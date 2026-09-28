"""
Model factories for creating test data.

Provides factory functions for Agent, Session, State, Instance, Todos.
"""

from typing import Optional, Any
from datetime import datetime


def create_agent(
    id: str = "agent-test-1",
    title: str = "Test Agent",
    dir: str = "project",
    full_dir: str = "/home/user/project",
    status: str = "busy",
):
    """Create a sample Agent for testing.

    Args:
        id: Agent identifier
        title: Agent display title
        dir: Short directory name
        full_dir: Full directory path
        status: Agent status (busy, idle)

    Returns:
        Agent instance
    """
    from opencode_status_bar.core.models import Agent, SessionStatus

    status_map = {
        "busy": SessionStatus.BUSY,
        "idle": SessionStatus.IDLE,
    }

    return Agent(
        id=id,
        title=title,
        dir=dir,
        full_dir=full_dir,
        status=status_map.get(status, SessionStatus.BUSY),
    )


def create_instance(
    port: int = 8080,
    tty: str = "/dev/ttys001",
    agents: Optional[list] = None,
):
    """Create a sample Instance for testing.

    Args:
        port: Instance port
        tty: Terminal device path
        agents: List of Agent objects (creates default if None)

    Returns:
        Instance instance
    """
    from opencode_status_bar.core.models import Instance

    if agents is None:
        agents = [create_agent()]

    return Instance(
        port=port,
        tty=tty,
        agents=agents,
    )


def create_todos(
    pending: int = 3,
    in_progress: int = 1,
):
    """Create sample Todos for testing.

    Args:
        pending: Number of pending todos
        in_progress: Number of in-progress todos

    Returns:
        Todos instance
    """
    from opencode_status_bar.core.models import Todos

    return Todos(pending=pending, in_progress=in_progress)


def create_state(
    instances: Optional[list] = None,
    todos: Optional[Any] = None,
    connected: bool = True,
):
    """Create a sample State for testing.

    Args:
        instances: List of Instance objects (creates default if None)
        todos: Todos object (creates default if None)
        connected: Connection status

    Returns:
        State instance
    """
    from opencode_status_bar.core.models import State, Todos

    if instances is None:
        instances = [create_instance()]
    if todos is None:
        todos = create_todos()

    return State(
        instances=instances,
        todos=todos,
        connected=connected,
    )


def create_session(
    session_id: str = "sess-001",
    title: str = "Test Session",
    directory: str = "/home/user/project",
    tokens_in: int = 1000,
    tokens_out: int = 500,
    status: str = "completed",
    duration_ms: int = 10000,
) -> dict:
    """Create a session data dict for testing.

    Args:
        session_id: Session identifier
        title: Session title
        directory: Working directory
        tokens_in: Input tokens
        tokens_out: Output tokens
        status: Session status
        duration_ms: Duration in milliseconds

    Returns:
        Session data dict
    """
    return {
        "id": session_id,
        "title": title,
        "directory": directory,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "status": status,
        "duration_ms": duration_ms,
        "created_at": datetime.now().isoformat(),
    }
