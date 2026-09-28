"""File-related queries for sessions.

Handles file operation metrics, git history, and chart data generation.
"""

import json
from datetime import datetime
from typing import TYPE_CHECKING

from .base import BaseSessionQueries

if TYPE_CHECKING:
    pass


class FileQueries(BaseSessionQueries):
    """Queries for session file operations and git history."""

    def get_session_files(self, session_id: str) -> dict:
        """Get detailed file operations for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with file operations breakdown
        """
        files = self._get_session_files_internal(session_id)
        session = self._get_session_info(session_id)

        return {
            "meta": {
                "session_id": session_id,
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total_reads": files["total_reads"],
                "total_writes": files["total_writes"],
                "total_edits": files["total_edits"],
                "high_risk_count": files["high_risk_count"],
                "additions": session.get("additions") if session else None,
                "deletions": session.get("deletions") if session else None,
            },
            "details": files,
            "charts": {
                "files_by_type": self._files_chart_data(files),
                "files_by_extension": files.get("by_extension", []),
            },
        }

    def get_session_file_parts(self, session_id: str) -> dict:
        """Get file parts (reads/writes) with MIME type information.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with file parts and MIME type statistics
        """
        try:
            results = self._conn.execute(
                """
                SELECT
                    file_path,
                    mime_type,
                    part_type,
                    operation,
                    created_at
                FROM parts
                WHERE session_id = ?
                  AND file_path IS NOT NULL
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            files = []
            for row in results:
                file_entry = {
                    "file_path": row[0],
                    "mime_type": row[1],
                    "part_type": row[2],
                    "operation": row[3],
                    "created_at": row[4].isoformat() if row[4] else None,
                }
                files.append(file_entry)

            # Count by MIME type
            mime_counts = {}
            for f in files:
                mime = f.get("mime_type") or "unknown"
                mime_counts[mime] = mime_counts.get(mime, 0) + 1

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_files": len(files),
                    "by_mime_type": [
                        {"mime_type": k, "count": v}
                        for k, v in sorted(
                            mime_counts.items(), key=lambda x: x[1], reverse=True
                        )
                    ],
                },
                "files": files,
            }

        except Exception as e:
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "summary": {"total_files": 0, "by_mime_type": []},
                "files": [],
            }

    def get_session_git_history(self, session_id: str) -> dict:
        """Get git history (patches) for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with git patches and file statistics
        """
        try:
            # Query the patches table (not parts) - patches are stored separately
            # with git_hash and files[] array columns
            results = self._conn.execute(
                """
                SELECT
                    git_hash,
                    files,
                    created_at
                FROM patches
                WHERE session_id = ?
                ORDER BY created_at ASC
                """,
                [session_id],
            ).fetchall()

            patches = []
            all_files: set[str] = set()

            for row in results:
                # files is a VARCHAR[] array in DuckDB, not JSON
                file_list = list(row[1]) if row[1] else []

                # Collect unique files
                for f in file_list:
                    all_files.add(f)

                patches.append(
                    {
                        "git_hash": row[0],
                        "files": file_list,
                        "created_at": row[2].isoformat() if row[2] else None,
                    }
                )

            return {
                "meta": {
                    "session_id": session_id,
                    "generated_at": datetime.now().isoformat(),
                },
                "summary": {
                    "total_patches": len(patches),
                    "unique_files": len(all_files),
                },
                "patches": patches,
            }

        except Exception as e:
            return {
                "meta": {"session_id": session_id, "error": str(e)},
                "summary": {"total_patches": 0, "unique_files": 0},
                "patches": [],
            }

    # ===== Internal/Private Methods =====

    def _get_session_files_internal(self, session_id: str) -> dict:
        """Get file operation metrics for a session.

        Args:
            session_id: The session ID to query

        Returns:
            Dict with file operation statistics
        """
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
                                "additions": additions,
                                "deletions": deletions,
                            }
                        )
            else:
                reads = writes = edits = high_risk = unique_files = 0
                files_list = {"read": [], "write": [], "edit": []}
                files_with_stats = []

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

    def _files_chart_data(self, files: dict) -> list[dict]:
        """Format files data for pie chart.

        Args:
            files: Dict with file operation statistics

        Returns:
            List of chart data points
        """
        return [
            {"label": "Read", "value": files.get("total_reads", 0), "color": "#3498db"},
            {
                "label": "Write",
                "value": files.get("total_writes", 0),
                "color": "#e74c3c",
            },
            {"label": "Edit", "value": files.get("total_edits", 0), "color": "#f39c12"},
        ]
