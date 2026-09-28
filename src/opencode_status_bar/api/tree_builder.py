"""
Tracing Tree Builder - Hierarchical tree construction for dashboard display.

Extracts tree-building logic from server.py for better testability
and separation of concerns.
"""

import json
import threading
from datetime import datetime, timedelta
from typing import Any

# Minimal timestamp for sorting None values
MIN_TIMESTAMP = "0000-01-01T00:00:00"


class TracingTreeBuilder:
    """Builds hierarchical tracing trees from database records.

    Constructs a tree structure showing:
    - Sessions (user → agent)
      - Agent traces (agent → subagent delegations)
        - Tools (bash, read, edit, etc.)

    This class encapsulates all tree-building logic, making it
    easier to test and maintain independently of HTTP handling.
    """

    def __init__(self, conn: Any, db_lock: threading.Lock):
        """Initialize the tree builder.

        Args:
            conn: DuckDB connection for executing queries
            db_lock: Lock for serializing database access
        """
        self._conn = conn
        self._db_lock = db_lock

    def build_tree(self, days: int, include_tools: bool = True) -> list[dict]:
        """Build the complete tracing tree.

        Args:
            days: Number of days to look back
            include_tools: Whether to include tool operations

        Returns:
            List of session nodes with nested children
        """
        start_date = datetime.now() - timedelta(days=days)

        with self._db_lock:
            # Fetch all required data
            root_rows = self._fetch_root_traces(start_date)
            child_rows = self._fetch_child_traces(start_date)
            tools_by_session = (
                self._fetch_tools(root_rows, child_rows) if include_tools else {}
            )

            # Build lookup structures
            children_by_parent = self._build_children_lookup(
                child_rows, tools_by_session, include_tools
            )

            # Construct final tree
            return self._build_sessions(
                root_rows, children_by_parent, tools_by_session, include_tools
            )

    def _fetch_root_traces(self, start_date: datetime) -> list[tuple]:
        """Fetch root traces (user-initiated sessions).

        Root traces have no parent and their trace_id starts with 'root_'.
        Excludes segment traces (trace_id containing '_seg').

        Args:
            start_date: Minimum date for filtering

        Returns:
            List of root trace rows
        """
        return self._conn.execute(
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.parent_agent,
                t.subagent_type,
                t.started_at,
                t.ended_at,
                t.duration_ms,
                t.tokens_in,
                t.tokens_out,
                t.status,
                t.prompt_input,
                s.title,
                s.directory,
                t.child_session_id
            FROM agent_traces t
            LEFT JOIN sessions s ON t.session_id = s.id
            WHERE t.parent_trace_id IS NULL
              AND t.trace_id LIKE 'root_%'
              AND t.trace_id NOT LIKE '%_seg%'
              AND t.started_at >= ?
            ORDER BY t.started_at DESC
            """,
            [start_date],
        ).fetchall()

    def _fetch_child_traces(self, start_date: datetime) -> list[tuple]:
        """Fetch child traces (delegations from agents to subagents).

        Child traces have a parent_trace_id and their trace_id does NOT
        start with 'root_'.

        Args:
            start_date: Minimum date for filtering

        Returns:
            List of child trace rows
        """
        return self._conn.execute(
            """
            SELECT 
                t.trace_id,
                t.session_id,
                t.parent_trace_id,
                t.parent_agent,
                t.subagent_type,
                t.started_at,
                t.ended_at,
                t.duration_ms,
                t.tokens_in,
                t.tokens_out,
                t.status,
                t.prompt_input,
                t.prompt_output,
                t.child_session_id
            FROM agent_traces t
            WHERE t.parent_trace_id IS NOT NULL
              AND t.trace_id NOT LIKE 'root_%'
              AND t.started_at >= ?
            ORDER BY t.started_at ASC
            """,
            [start_date],
        ).fetchall()

    def _fetch_tools(
        self, root_rows: list[tuple], child_rows: list[tuple]
    ) -> dict[str, list[dict]]:
        """Fetch tool operations for all sessions.

        Collects session IDs from both root and child traces,
        then fetches all tool parts for those sessions.

        Args:
            root_rows: Root trace rows (for extracting child_session_id)
            child_rows: Child trace rows (for extracting child_session_id)

        Returns:
            Dict mapping session_id to list of tool dicts
        """
        # Collect all session IDs from traces
        all_session_ids = set()
        for row in root_rows:
            if row[13]:  # child_session_id
                all_session_ids.add(row[13])
        for row in child_rows:
            if row[13]:  # child_session_id
                all_session_ids.add(row[13])

        if not all_session_ids:
            return {}

        # Fetch tools for these sessions
        # Placeholders are just "?" markers for parameterized query - safe
        placeholders = ",".join(["?" for _ in all_session_ids])
        tool_rows = self._conn.execute(
            f"""
            SELECT 
                id, session_id, tool_name, tool_status,
                arguments, created_at, duration_ms, result_summary
            FROM parts
            WHERE session_id IN ({placeholders})
              AND part_type = 'tool'
              AND tool_name IS NOT NULL
              AND tool_name != 'task'
            ORDER BY created_at ASC
            """,  # nosec B608
            list(all_session_ids),
        ).fetchall()

        # Group tools by session
        tools_by_session: dict[str, list[dict]] = {}
        for row in tool_rows:
            session_id = row[1]
            if session_id not in tools_by_session:
                tools_by_session[session_id] = []

            display_info = self._extract_tool_display_info(row[2], row[4])
            tools_by_session[session_id].append(
                {
                    "id": row[0],
                    "node_type": "tool",
                    "tool_name": row[2],
                    "status": row[3],
                    "display_info": display_info,
                    "created_at": row[5].isoformat() if row[5] else None,
                    "duration_ms": row[6],
                }
            )

        return tools_by_session

    def _extract_tool_display_info(self, tool_name: str, arguments: str | None) -> str:
        """Extract display info from tool arguments.

        Parses the JSON arguments and extracts relevant info based
        on the tool type.

        Args:
            tool_name: Name of the tool (bash, read, write, etc.)
            arguments: JSON string of tool arguments

        Returns:
            Human-readable display string
        """
        if not arguments:
            return ""

        try:
            args_dict = json.loads(arguments)

            if tool_name == "bash":
                cmd = args_dict.get("command", "")
                return cmd[:100] + "..." if len(cmd) > 100 else cmd
            elif tool_name in ("read", "write", "edit"):
                return args_dict.get("filePath", args_dict.get("path", ""))
            elif tool_name == "glob":
                return args_dict.get("pattern", "")
            elif tool_name == "grep":
                return args_dict.get("pattern", "")
            elif tool_name == "task":
                return args_dict.get("subagent_type", "")
        except (json.JSONDecodeError, TypeError):
            pass

        return ""

    def _build_children_lookup(
        self,
        child_rows: list[tuple],
        tools_by_session: dict[str, list[dict]],
        include_tools: bool,
    ) -> dict[str, list[dict]]:
        """Build lookup dict mapping parent_trace_id to children.

        Each child includes its tools (if requested) and metadata.

        Args:
            child_rows: Child trace rows from database
            tools_by_session: Tools grouped by session ID
            include_tools: Whether to include tools in children

        Returns:
            Dict mapping parent_trace_id to list of child nodes
        """
        children_by_parent: dict[str, list[dict]] = {}

        for row in child_rows:
            parent_id = row[2]  # parent_trace_id
            if parent_id not in children_by_parent:
                children_by_parent[parent_id] = []

            child_session_id = row[13]

            # Get and sort tools for this agent's session
            child_tools = []
            if include_tools:
                raw_tools = tools_by_session.get(child_session_id, [])
                child_tools = sorted(raw_tools, key=self._get_sort_key)

            # Determine node_type based on parent
            parent_agent = row[3]
            node_type = "user_turn" if parent_agent == "user" else "delegation"

            children_by_parent[parent_id].append(
                {
                    "trace_id": row[0],
                    "session_id": row[1],
                    "node_type": node_type,
                    "parent_trace_id": row[2],
                    "parent_agent": parent_agent,
                    "subagent_type": row[4],
                    "started_at": row[5].isoformat() if row[5] else None,
                    "ended_at": row[6].isoformat() if row[6] else None,
                    "duration_ms": row[7],
                    "tokens_in": row[8],
                    "tokens_out": row[9],
                    "status": row[10],
                    "prompt_input": row[11],
                    "prompt_output": row[12],
                    "children": child_tools,  # Pre-sorted chronologically
                }
            )

        return children_by_parent

    def _build_children(
        self,
        children_by_parent: dict[str, list[dict]],
        parent_trace_id: str,
        depth: int = 0,
    ) -> list[dict]:
        """Recursively build children for a parent trace.

        Traverses the tree depth-first, adding nested agents after tools
        and sorting all children chronologically.

        Args:
            children_by_parent: Lookup dict of children by parent ID
            parent_trace_id: ID of the parent trace
            depth: Current recursion depth (max 10)

        Returns:
            List of child nodes with their own children populated
        """
        if depth > 10:  # Prevent infinite recursion
            return []

        children = children_by_parent.get(parent_trace_id, [])
        for child in children:
            # Get nested agents and add them after tools
            nested_agents = self._build_children(
                children_by_parent, child["trace_id"], depth + 1
            )
            child["children"].extend(nested_agents)
            # Sort all children (tools + nested agents) chronologically
            child["children"].sort(key=self._get_sort_key)

        # Sort this level chronologically
        children.sort(key=self._get_sort_key)
        return children

    def _build_sessions(
        self,
        root_rows: list[tuple],
        children_by_parent: dict[str, list[dict]],
        tools_by_session: dict[str, list[dict]],
        include_tools: bool,
    ) -> list[dict]:
        """Build the final list of session nodes.

        Creates session nodes from root traces, adds their children
        (agent delegations), and optionally includes root session tools.

        Args:
            root_rows: Root trace rows from database
            children_by_parent: Lookup dict of children
            tools_by_session: Tools grouped by session ID
            include_tools: Whether to include tools

        Returns:
            List of fully-constructed session nodes
        """
        sessions = []

        for row in root_rows:
            trace_id = row[0]
            child_session_id = row[13]
            agent_type = row[3]

            # Get agent delegations (2nd level) - tools are inside each agent
            agent_children = self._build_children(children_by_parent, trace_id)

            # Include root session tools as a primary agent node
            if include_tools:
                primary_agent = self._create_primary_agent(
                    row, tools_by_session.get(child_session_id, [])
                )
                if primary_agent:
                    agent_children.append(primary_agent)
                    # Re-sort to maintain chronological order
                    agent_children.sort(key=self._get_sort_key)

            session = {
                "session_id": row[1],
                "trace_id": trace_id,
                "node_type": "session",
                "parent_agent": row[2] or "user",
                "agent_type": agent_type,
                "started_at": row[4].isoformat() if row[4] else None,
                "ended_at": row[5].isoformat() if row[5] else None,
                "duration_ms": row[6],
                "tokens_in": row[7],
                "tokens_out": row[8],
                "status": row[9],
                "prompt_input": row[10],
                "title": row[11] or "",
                "directory": row[12] or "",
                "children": agent_children,
            }

            # Count total traces in subtree
            session["trace_count"] = self._count_traces(session) - 1  # Exclude root
            sessions.append(session)

        return sessions

    def _create_primary_agent(self, root_row: tuple, tools: list[dict]) -> dict | None:
        """Create a virtual primary agent node for root session tools.

        When a root session has tools directly (not via delegation),
        we create a virtual agent node to hold them.

        Args:
            root_row: The root trace row
            tools: List of tools for this session

        Returns:
            Primary agent node dict, or None if no tools
        """
        if not tools:
            return None

        # Sort tools chronologically
        sorted_tools = sorted(tools, key=self._get_sort_key)
        trace_id = root_row[0]
        agent_type = root_row[3]

        return {
            "trace_id": f"{trace_id}_primary",
            "session_id": root_row[1],
            "node_type": "user_turn",
            "parent_agent": "user",
            "subagent_type": agent_type or "agent",
            "started_at": root_row[4].isoformat() if root_row[4] else None,
            "ended_at": root_row[5].isoformat() if root_row[5] else None,
            "duration_ms": root_row[6],
            "tokens_in": root_row[7],
            "tokens_out": root_row[8],
            "status": root_row[9],
            "prompt_input": root_row[10],
            "children": sorted_tools,
        }

    @staticmethod
    def _get_sort_key(item: dict) -> str:
        """Get a sortable timestamp from an item.

        Uses started_at for traces, created_at for tools.
        Returns MIN_TIMESTAMP for None values to ensure they sort first.

        Args:
            item: Dict with started_at or created_at field

        Returns:
            ISO timestamp string for sorting
        """
        ts = item.get("started_at") or item.get("created_at")
        return ts if ts else MIN_TIMESTAMP

    @staticmethod
    def _count_traces(node: dict) -> int:
        """Recursively count traces in a subtree.

        Args:
            node: Node dict with optional children

        Returns:
            Total count including this node and all descendants
        """
        return 1 + sum(
            TracingTreeBuilder._count_traces(c) for c in node.get("children", [])
        )
