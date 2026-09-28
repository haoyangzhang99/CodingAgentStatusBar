"""
Enriched data queries.

Queries for todos, projects, code stats, and cost metrics.
"""

from typing import Optional

from ..models import Project, ProjectStats, Todo, TodoStats
from .base import BaseQueries


class EnrichedQueries(BaseQueries):
    """Queries for enriched data (todos, projects, costs)."""

    def get_todos(
        self, session_id: Optional[str] = None, status: Optional[str] = None
    ) -> list[Todo]:
        """Get todos, optionally filtered by session or status."""
        try:
            query = "SELECT id, session_id, content, status, priority, position, created_at, updated_at FROM todos"
            params = []
            conditions = []

            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)
            if status:
                conditions.append("status = ?")
                params.append(status)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY session_id, position"

            results = self._conn.execute(query, params).fetchall()

            return [
                Todo(
                    id=row[0],
                    session_id=row[1],
                    content=row[2],
                    status=row[3],
                    priority=row[4],
                    position=row[5],
                    created_at=row[6],
                    updated_at=row[7],
                )
                for row in results
            ]
        except Exception:  # Intentional catch-all: query failures return empty list
            return []

    def get_todo_stats(self, days: int) -> Optional[TodoStats]:
        """Get todo statistics for the last N days."""
        start_date, end_date = self._get_date_range(days)

        try:
            result = self._conn.execute(
                """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) as cancelled
                FROM todos
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            if not result or result[0] == 0:
                return None

            total = result[0]
            completed = result[1] or 0
            completion_rate = (completed / total * 100) if total > 0 else 0

            return TodoStats(
                total=total,
                completed=completed,
                in_progress=result[2] or 0,
                pending=result[3] or 0,
                cancelled=result[4] or 0,
                completion_rate=completion_rate,
            )
        except Exception:  # Intentional catch-all: query failures return None
            return None

    def get_projects(self) -> list[Project]:
        """Get all projects."""
        try:
            results = self._conn.execute(
                """
                SELECT id, worktree, vcs, created_at, updated_at
                FROM projects
                ORDER BY updated_at DESC
                """
            ).fetchall()

            return [
                Project(
                    id=row[0],
                    worktree=row[1],
                    vcs=row[2],
                    created_at=row[3],
                    updated_at=row[4],
                )
                for row in results
            ]
        except Exception:  # Intentional catch-all: query failures return empty list
            return []

    def get_project_stats(self, days: int) -> list[ProjectStats]:
        """Get statistics per project for the last N days."""
        start_date, end_date = self._get_date_range(days)

        try:
            results = self._conn.execute(
                """
                SELECT 
                    p.id,
                    p.worktree,
                    COUNT(DISTINCT s.id) as sessions,
                    COALESCE(SUM(m.tokens_input + m.tokens_output), 0) as tokens,
                    (SELECT COUNT(*) FROM todos t 
                     WHERE t.session_id IN (SELECT id FROM sessions WHERE project_id = p.id)) as todos_total,
                    (SELECT COUNT(*) FROM todos t 
                     WHERE t.session_id IN (SELECT id FROM sessions WHERE project_id = p.id)
                       AND t.status = 'completed') as todos_completed
                FROM projects p
                LEFT JOIN sessions s ON s.project_id = p.id 
                    AND s.created_at >= ? AND s.created_at <= ?
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY p.id, p.worktree
                ORDER BY tokens DESC
                """,
                [start_date, end_date],
            ).fetchall()

            return [
                ProjectStats(
                    project_id=row[0],
                    worktree=row[1],
                    sessions=row[2],
                    tokens=row[3],
                    todos_total=row[4] or 0,
                    todos_completed=row[5] or 0,
                )
                for row in results
            ]
        except Exception:  # Intentional catch-all: query failures return empty list
            return []

    def get_code_stats(self, days: int) -> dict:
        """Get code change statistics (additions, deletions) for the last N days."""
        start_date, end_date = self._get_date_range(days)

        try:
            result = self._conn.execute(
                """
                SELECT 
                    COALESCE(SUM(additions), 0) as total_additions,
                    COALESCE(SUM(deletions), 0) as total_deletions,
                    COALESCE(SUM(files_changed), 0) as total_files,
                    COUNT(CASE WHEN additions > 0 OR deletions > 0 THEN 1 END) as sessions_with_changes
                FROM sessions
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            return {
                "additions": result[0] if result else 0,
                "deletions": result[1] if result else 0,
                "files_changed": result[2] if result else 0,
                "sessions_with_changes": result[3] if result else 0,
            }
        except Exception:  # Intentional catch-all: query failures return default dict
            return {
                "additions": 0,
                "deletions": 0,
                "files_changed": 0,
                "sessions_with_changes": 0,
            }

    def get_cost_stats(self, days: int) -> dict:
        """Get cost statistics for the last N days."""
        start_date, end_date = self._get_date_range(days)

        try:
            result = self._conn.execute(
                """
                SELECT 
                    COALESCE(SUM(cost), 0) as total_cost,
                    COALESCE(AVG(cost), 0) as avg_cost_per_message,
                    COUNT(CASE WHEN cost > 0 THEN 1 END) as messages_with_cost
                FROM messages
                WHERE created_at >= ? AND created_at <= ?
                """,
                [start_date, end_date],
            ).fetchone()

            return {
                "total_cost": float(result[0]) if result else 0.0,
                "avg_cost_per_message": float(result[1]) if result else 0.0,
                "messages_with_cost": result[2] if result else 0,
            }
        except Exception:  # Intentional catch-all: query failures return default dict
            return {
                "total_cost": 0.0,
                "avg_cost_per_message": 0.0,
                "messages_with_cost": 0,
            }
