"""Helper methods for tracing data service.

Contains private utility methods used across query modules.
"""

import json
import os
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from urllib.parse import urlparse


if TYPE_CHECKING:
    from .config import TracingConfig
    import duckdb


def extract_tool_display_info(
    tool_name: str | None,
    arguments: str | None,
    content: str | None = None,
) -> str:
    """Extract human-readable display info from tool arguments.

    This is the canonical implementation used across the codebase.
    Supports file operations, commands, searches, web fetches, and delegations.

    Args:
        tool_name: Name of the tool (bash, read, write, edit, etc.)
        arguments: JSON string of tool arguments
        content: Optional tool result content (unused but kept for API compat)

    Returns:
        Short display string for the tool operation, or empty string if unavailable
    """
    if not tool_name:
        return ""

    # Try to parse arguments as JSON
    args: dict = {}
    if arguments:
        try:
            args = json.loads(arguments)
        except (json.JSONDecodeError, TypeError):
            pass

    # File-based tools (read, edit, write, glob)
    if tool_name in ("read", "edit", "write"):
        file_path = args.get("filePath", args.get("file_path", ""))
        if file_path:
            return os.path.basename(file_path)
        return ""

    if tool_name == "glob":
        pattern = args.get("pattern", "")
        path = args.get("path", "")
        if pattern:
            return pattern[:40]
        if path:
            return path[:40]
        return ""

    # Command-based tools
    if tool_name == "bash":
        command = args.get("command", "")
        if command:
            # Take first line, truncate to reasonable length
            short_cmd = command.split("\n")[0][:60]
            if len(command) > 60 or "\n" in command:
                short_cmd += "..."
            return short_cmd
        return ""

    # Search tools
    if tool_name == "grep":
        pattern = args.get("pattern", "")
        if pattern:
            return f"/{pattern}/"[:40]
        return ""

    # Web fetch tools
    if tool_name in ("webfetch", "web_fetch"):
        url = args.get("url", "")
        if url:
            try:
                parsed = urlparse(url)
                return parsed.netloc[:30]
            except Exception:
                return url[:30]
        return ""

    # Context7 docs tools
    if tool_name == "context7_query-docs":
        library_id = args.get("libraryId", "")
        return library_id[:80] if library_id else ""

    # Task/delegation tools
    if tool_name == "task":
        subagent = args.get("subagent_type", "")
        description = args.get("description", "")
        if subagent and description:
            return f"{subagent}: {description}"[:100]
        elif description:
            return description[:100]
        elif subagent:
            return subagent
        return ""

    # Generic fallback: show first arg value if available
    if args:
        first_value = str(list(args.values())[0])[:30]
        return first_value

    return ""


class HelpersMixin:
    """Mixin providing helper methods for TracingDataService.

    Requires _conn property and _config attribute from the main class.
    """

    _config: "TracingConfig"

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection (implemented by main class)."""
        raise NotImplementedError

    def _get_session_info(self, session_id: str) -> Optional[dict]:
        """Get basic session information."""
        try:
            result = self._conn.execute(
                """
                SELECT id, title, directory, created_at, updated_at, parent_id, additions, deletions
                FROM sessions
                WHERE id = ?
                """,
                [session_id],
            ).fetchone()

            if result:
                return {
                    "id": result[0],
                    "title": result[1],
                    "directory": result[2],
                    "created_at": result[3],
                    "updated_at": result[4],
                    "parent_id": result[5],
                    "additions": result[6],
                    "deletions": result[7],
                    "status": "completed" if result[4] else "running",
                }
            return None
        except Exception:
            return None

    def _get_session_tokens_internal(self, session_id: str) -> dict:
        """Get token metrics for a session."""
        try:
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as message_count,
                    COALESCE(SUM(tokens_input), 0) as input,
                    COALESCE(SUM(tokens_output), 0) as output,
                    COALESCE(SUM(tokens_reasoning), 0) as reasoning,
                    COALESCE(SUM(tokens_cache_read), 0) as cache_read,
                    COALESCE(SUM(tokens_cache_write), 0) as cache_write
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result is None:
                raise ValueError("No result from tokens query")

            input_tokens = result[1] or 0
            output_tokens = result[2] or 0
            cache_read = result[4] or 0
            total_input = input_tokens + cache_read

            # Get tokens by agent
            agent_results = self._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'unknown') as agent,
                    SUM(tokens_input + tokens_output) as tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY tokens DESC
                """,
                [session_id],
            ).fetchall()

            return {
                "message_count": result[0] or 0,
                "input": input_tokens,
                "output": output_tokens,
                "reasoning": result[3] or 0,
                "cache_read": cache_read,
                "cache_write": result[5] or 0,
                "total": input_tokens + output_tokens,
                "cache_hit_ratio": round(
                    (cache_read / total_input * 100) if total_input > 0 else 0, 1
                ),
                "by_agent": [
                    {"agent": row[0], "tokens": row[1] or 0} for row in agent_results
                ],
            }
        except Exception:
            return {
                "message_count": 0,
                "input": 0,
                "output": 0,
                "reasoning": 0,
                "cache_read": 0,
                "cache_write": 0,
                "total": 0,
                "cache_hit_ratio": 0,
                "by_agent": [],
            }

    def _get_session_tools_internal(self, session_id: str) -> dict:
        """Get tool metrics for a session."""
        try:
            # Get overall stats
            result = self._conn.execute(
                """
                SELECT
                    COUNT(*) as total_calls,
                    COUNT(DISTINCT tool_name) as unique_tools,
                    SUM(CASE WHEN tool_status = 'completed' THEN 1 ELSE 0 END) as success,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors,
                    AVG(duration_ms) as avg_duration
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                """,
                [session_id],
            ).fetchone()

            if result is None:
                raise ValueError("No result from tools query")

            total = result[0] or 0
            success = result[2] or 0

            # Get top tools
            top_tools = self._conn.execute(
                """
                SELECT
                    tool_name,
                    COUNT(*) as count,
                    AVG(duration_ms) as avg_duration,
                    SUM(CASE WHEN tool_status = 'error' THEN 1 ELSE 0 END) as errors
                FROM parts
                WHERE session_id = ? AND tool_name IS NOT NULL
                GROUP BY tool_name
                ORDER BY count DESC
                LIMIT 10
                """,
                [session_id],
            ).fetchall()

            return {
                "total_calls": total,
                "unique_tools": result[1] or 0,
                "success_count": success,
                "error_count": result[3] or 0,
                "success_rate": round((success / total * 100) if total > 0 else 0, 1),
                "avg_duration_ms": int(result[4] or 0),
                "top_tools": [
                    {
                        "name": row[0],
                        "count": row[1],
                        "avg_duration_ms": int(row[2] or 0),
                        "error_count": row[3] or 0,
                    }
                    for row in top_tools
                ],
            }
        except Exception:
            return {
                "total_calls": 0,
                "unique_tools": 0,
                "success_count": 0,
                "error_count": 0,
                "success_rate": 0,
                "avg_duration_ms": 0,
                "top_tools": [],
            }

    def _get_session_files_internal(self, session_id: str) -> dict:
        """Get file operation metrics for a session."""
        try:
            result = self._conn.execute(
                """
                SELECT
                    SUM(CASE WHEN operation = 'read' THEN 1 ELSE 0 END) as reads,
                    SUM(CASE WHEN operation = 'write' THEN 1 ELSE 0 END) as writes,
                    SUM(CASE WHEN operation = 'edit' THEN 1 ELSE 0 END) as edits,
                    SUM(CASE WHEN risk_level IN ('high', 'critical') THEN 1 ELSE 0 END) as high_risk,
                    COUNT(DISTINCT file_path) as unique_files
                FROM file_operations
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result is not None:
                r_reads = result[0] or 0
                r_writes = result[1] or 0
                r_edits = result[2] or 0
                r_high_risk = result[3] or 0
                r_unique_files = result[4] or 0
                has_file_ops = r_reads + r_writes + r_edits > 0
            else:
                r_reads = r_writes = r_edits = r_high_risk = r_unique_files = 0
                has_file_ops = False

            if has_file_ops:
                reads = r_reads
                writes = r_writes
                edits = r_edits
                high_risk = r_high_risk
                unique_files = r_unique_files

                files_by_op = self._conn.execute(
                    """
                    SELECT operation, file_path, 
                           COALESCE(MAX(additions), 0) as additions,
                           COALESCE(MAX(deletions), 0) as deletions
                    FROM file_operations
                    WHERE session_id = ?
                    GROUP BY file_path, operation
                    ORDER BY 
                        CASE operation WHEN 'edit' THEN 1 WHEN 'write' THEN 2 ELSE 3 END,
                        (COALESCE(MAX(additions), 0) + COALESCE(MAX(deletions), 0)) DESC
                    """,
                    [session_id],
                ).fetchall()

                files_list: dict[str, list[str]] = {"read": [], "write": [], "edit": []}
                files_with_stats: list[dict] = []
                seen_paths: set[str] = set()
                for row in files_by_op:
                    op, path, additions, deletions = row[0], row[1], row[2], row[3]
                    if op in files_list and path not in files_list[op]:
                        files_list[op].append(path)
                    if path not in seen_paths:
                        seen_paths.add(path)
                        files_with_stats.append(
                            {
                                "path": path,
                                "operation": op,
                                "additions": additions or 0,
                                "deletions": deletions or 0,
                            }
                        )
            else:
                fallback = self._conn.execute(
                    """
                    SELECT tool_name, json_extract_string(arguments, '$.filePath') as file_path
                    FROM parts
                    WHERE session_id = ? 
                      AND tool_name IN ('read', 'write', 'edit')
                      AND arguments IS NOT NULL
                    ORDER BY created_at DESC
                    """,
                    [session_id],
                ).fetchall()

                files_list = {"read": [], "write": [], "edit": []}
                files_with_stats = []
                seen_paths: set[str] = set()
                for row in fallback:
                    op, path = row[0], row[1]
                    if op and path and path not in files_list.get(op, []):
                        if op not in files_list:
                            files_list[op] = []
                        files_list[op].append(path)
                    if path and path not in seen_paths:
                        seen_paths.add(path)
                        files_with_stats.append(
                            {
                                "path": path,
                                "operation": op,
                                "additions": 0,
                                "deletions": 0,
                            }
                        )

                reads = len(files_list.get("read", []))
                writes = len(files_list.get("write", []))
                edits = len(files_list.get("edit", []))
                high_risk = 0
                unique_files = len(
                    set(
                        files_list.get("read", [])
                        + files_list.get("write", [])
                        + files_list.get("edit", [])
                    )
                )

            return {
                "total_reads": reads,
                "total_writes": writes,
                "total_edits": edits,
                "high_risk_count": high_risk,
                "unique_files": unique_files,
                "files_list": files_list,
                "files_with_stats": files_with_stats,
                "by_operation": [
                    {"operation": "read", "count": reads},
                    {"operation": "write", "count": writes},
                    {"operation": "edit", "count": edits},
                ],
            }
        except Exception:
            return {
                "total_reads": 0,
                "total_writes": 0,
                "total_edits": 0,
                "high_risk_count": 0,
                "unique_files": 0,
                "files_list": {"read": [], "write": [], "edit": []},
                "files_with_stats": [],
                "by_operation": [],
            }

    def _get_session_agents_internal(self, session_id: str) -> dict:
        """Get agent metrics for a session."""
        try:
            # Get unique agents from messages
            agent_results = self._conn.execute(
                """
                SELECT
                    COALESCE(agent, 'user') as agent,
                    COUNT(*) as message_count,
                    SUM(tokens_input + tokens_output) as tokens
                FROM messages
                WHERE session_id = ?
                GROUP BY agent
                ORDER BY message_count DESC
                """,
                [session_id],
            ).fetchall()

            # Get delegation depth from traces
            depth_result = self._conn.execute(
                """
                WITH RECURSIVE trace_depth AS (
                    SELECT trace_id, parent_trace_id, 0 as depth
                    FROM agent_traces
                    WHERE session_id = ? AND parent_trace_id IS NULL
                    
                    UNION ALL
                    
                    SELECT t.trace_id, t.parent_trace_id, td.depth + 1
                    FROM agent_traces t
                    JOIN trace_depth td ON t.parent_trace_id = td.trace_id
                    WHERE td.depth < 10
                )
                SELECT MAX(depth) FROM trace_depth
                """,
                [session_id],
            ).fetchone()

            return {
                "unique_count": len(agent_results),
                "max_depth": depth_result[0] or 0 if depth_result else 0,
                "agents": [
                    {
                        "agent": row[0],
                        "message_count": row[1],
                        "tokens": row[2] or 0,
                    }
                    for row in agent_results
                ],
            }
        except Exception:
            return {
                "unique_count": 0,
                "max_depth": 0,
                "agents": [],
            }

    def _calculate_duration(self, session_id: str) -> int:
        """Calculate session duration in milliseconds."""
        try:
            result = self._conn.execute(
                """
                SELECT
                    MIN(created_at) as first_event,
                    MAX(COALESCE(completed_at, created_at)) as last_event
                FROM messages
                WHERE session_id = ?
                """,
                [session_id],
            ).fetchone()

            if result and result[0] and result[1]:
                delta = result[1] - result[0]
                return int(delta.total_seconds() * 1000)
            return 0
        except Exception:
            return 0

    def _calculate_cost(self, tokens: dict) -> float:
        """Calculate estimated cost in USD."""
        input_cost = (tokens.get("input", 0) / 1000) * self._config.cost_per_1k_input
        output_cost = (tokens.get("output", 0) / 1000) * self._config.cost_per_1k_output
        cache_cost = (
            tokens.get("cache_read", 0) / 1000
        ) * self._config.cost_per_1k_cache
        return input_cost + output_cost + cache_cost

    def _tokens_chart_data(self, tokens: dict) -> list[dict]:
        """Format tokens data for pie chart."""
        return [
            {"label": "Input", "value": tokens.get("input", 0), "color": "#3498db"},
            {"label": "Output", "value": tokens.get("output", 0), "color": "#2ecc71"},
            {
                "label": "Cache",
                "value": tokens.get("cache_read", 0),
                "color": "#9b59b6",
            },
        ]

    def _tools_chart_data(self, tools: dict) -> list[dict]:
        """Format tools data for bar chart."""
        return [
            {"label": t["name"], "value": t["count"]}
            for t in tools.get("top_tools", [])[:5]
        ]

    def _files_chart_data(self, files: dict) -> list[dict]:
        """Format files data for pie chart."""
        return [
            {"label": "Read", "value": files.get("total_reads", 0), "color": "#3498db"},
            {
                "label": "Write",
                "value": files.get("total_writes", 0),
                "color": "#e74c3c",
            },
            {"label": "Edit", "value": files.get("total_edits", 0), "color": "#f39c12"},
        ]

    def _empty_response(self, session_id: str) -> dict:
        """Return empty response structure."""
        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
                "error": "Session not found",
            },
            "summary": {},
            "details": {},
            "charts": {},
        }

    def _paginate(
        self,
        data: list,
        page: int = 1,
        per_page: int = 50,
        total: Optional[int] = None,
    ) -> dict:
        """Apply pagination to a list and return standardized response.

        Args:
            data: Full list of items (or pre-sliced if total is provided)
            page: Page number (1-based)
            per_page: Items per page (max 200)
            total: Total count if data is already sliced

        Returns:
            Dict with data and meta pagination info
        """
        per_page = min(per_page, 200)  # Max 200 per page
        page = max(page, 1)  # Min page 1

        if total is None:
            total = len(data)
            start = (page - 1) * per_page
            end = start + per_page
            paginated_data = data[start:end]
        else:
            paginated_data = data

        total_pages = (total + per_page - 1) // per_page if total > 0 else 0

        return {
            "success": True,
            "data": paginated_data,
            "meta": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
            },
        }

    def _extract_tool_display_info(
        self, tool_name: str, content: str, arguments: str
    ) -> str:
        """Extract display-friendly info from tool content/arguments.

        Delegates to the standalone `extract_tool_display_info` function.

        Args:
            tool_name: Name of the tool (read, edit, bash, etc.)
            content: Tool result content (kept for API compatibility)
            arguments: Tool arguments (JSON string)

        Returns:
            Short display string for the tool operation
        """
        return extract_tool_display_info(tool_name, arguments, content)
