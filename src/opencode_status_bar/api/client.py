"""
Analytics API Client - HTTP client for dashboard to access analytics data.

The dashboard uses this client instead of accessing DuckDB directly.
This solves DuckDB's multi-process concurrency limitations.
"""

import urllib.request
import urllib.error
import json
import time
from typing import Optional

from ..utils.logger import error
from .config import API_HOST, API_PORT, API_TIMEOUT

# Cache duration for health check (seconds)
HEALTH_CHECK_CACHE_DURATION = 5


class AnalyticsAPIClient:
    """HTTP client for the Analytics API.

    Used by the dashboard to fetch data from the menubar's API server.
    Falls back gracefully if the API is not available.
    """

    def __init__(
        self, host: str = API_HOST, port: int = API_PORT, timeout: int = API_TIMEOUT
    ):
        """Initialize the API client.

        Args:
            host: API server host
            port: API server port
            timeout: Request timeout in seconds
        """
        self._base_url = f"http://{host}:{port}"
        self._timeout = timeout
        self._available: Optional[bool] = None
        self._last_health_check: float = 0  # Timestamp of last health check

    def _request(self, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
        """Make an HTTP GET request to the API.

        Args:
            endpoint: API endpoint (e.g., "/api/stats")
            params: Optional query parameters

        Returns:
            Response data dict, or None if request failed
        """
        url = f"{self._base_url}{endpoint}"

        if params:
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"

        start_time = time.time()

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=self._timeout) as response:  # nosec B310
                data = json.loads(response.read().decode("utf-8"))
                elapsed = (time.time() - start_time) * 1000

                if data.get("success"):
                    self._available = True
                    result = data.get("data")
                    self._log_response(endpoint, elapsed, result)
                    return result
                else:
                    error(f"[API Client] Request failed: {data.get('error')}")
                    return None

        except urllib.error.URLError:
            elapsed = (time.time() - start_time) * 1000
            if self._available is not False:
                self._available = False
            return None
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            error(f"[API Client] Error ({elapsed:.0f}ms): {e}")
            return None

    def _log_response(
        self, endpoint: str, elapsed: float, result: Optional[dict]
    ) -> None:
        pass

    @property
    def is_available(self) -> bool:
        """Check if the API is available.

        Uses cached result for HEALTH_CHECK_CACHE_DURATION seconds to reduce
        overhead from repeated checks (dashboard checks availability 3+ times per refresh).
        """
        now = time.time()
        # Use cached result if recent enough
        if (
            self._available is not None
            and (now - self._last_health_check) < HEALTH_CHECK_CACHE_DURATION
        ):
            return self._available
        # Otherwise perform fresh health check
        return self.health_check()

    def health_check(self) -> bool:
        """Check if the API server is responding."""
        result = self._request("/api/health")
        self._last_health_check = time.time()
        return result is not None

    def get_stats(self) -> Optional[dict]:
        """Get database statistics."""
        return self._request("/api/stats")

    def get_global_stats(self, days: int = 30) -> Optional[dict]:
        """Get global statistics from TracingDataService.

        Args:
            days: Number of days to include

        Returns:
            Global stats dict or None
        """
        return self._request("/api/global-stats", {"days": days})

    def get_session_summary(self, session_id: str) -> Optional[dict]:
        """Get session summary.

        Args:
            session_id: Session ID

        Returns:
            Session summary dict or None
        """
        return self._request(f"/api/session/{session_id}/summary")

    def get_session_tokens(self, session_id: str) -> Optional[dict]:
        """Get session token details."""
        return self._request(f"/api/session/{session_id}/tokens")

    def get_session_tools(self, session_id: str) -> Optional[dict]:
        """Get session tool details."""
        return self._request(f"/api/session/{session_id}/tools")

    def get_session_files(self, session_id: str) -> Optional[dict]:
        """Get session file operations."""
        return self._request(f"/api/session/{session_id}/files")

    def get_session_agents(self, session_id: str) -> Optional[dict]:
        """Get session agents."""
        return self._request(f"/api/session/{session_id}/agents")

    def get_session_timeline(self, session_id: str) -> Optional[dict]:
        """Get session timeline events."""
        return self._request(f"/api/session/{session_id}/timeline")

    def get_session_prompts(self, session_id: str) -> Optional[dict]:
        """Get session prompts (first user prompt + last response)."""
        return self._request(f"/api/session/{session_id}/prompts")

    def get_session_messages(self, session_id: str) -> Optional[dict]:
        """Get all messages with content for a session.

        Returns:
            Dict with message data including role, content, timestamp, etc.
        """
        return self._request(f"/api/session/{session_id}/messages")

    def get_session_exchanges(self, session_id: str) -> Optional[dict]:
        """Get conversation exchanges (user→assistant pairs) for a session."""
        return self._request(f"/api/session/{session_id}/exchanges")

    def get_delegation_timeline(self, session_id: str) -> Optional[dict]:
        """Get complete timeline of a delegated agent session (reasoning, text, tools)."""
        return self._request(f"/api/session/{session_id}/delegation-timeline")

    def get_session_timeline_full(
        self, session_id: str, include_children: bool = True, depth: int = 3
    ) -> Optional[dict]:
        """Get complete timeline for a session with all events.

        Returns timeline with user_prompt, reasoning, tool_call,
        step_finish, assistant_response events.

        Args:
            session_id: Session ID
            include_children: Include child session timelines (delegations)
            depth: Max recursion depth for children

        Returns:
            Full timeline data dict or None
        """
        params = {
            "include_children": str(include_children).lower(),
            "depth": depth,
            "stream": "false",
        }
        return self._request(f"/api/session/{session_id}/timeline/full", params)

    def get_tracing_tree(
        self, days: int = 30, limit: int = 80, offset: int = 0
    ) -> Optional[dict]:
        return self._request_with_meta(
            "/api/tracing/tree", {"days": days, "limit": limit, "offset": offset}
        )

    def _request_with_meta(
        self, endpoint: str, params: Optional[dict] = None
    ) -> Optional[dict]:
        url = f"{self._base_url}{endpoint}"

        if params:
            query_string = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}?{query_string}"

        start_time = time.time()

        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req, timeout=self._timeout) as response:  # nosec B310
                data = json.loads(response.read().decode("utf-8"))
                elapsed = (time.time() - start_time) * 1000

                if data.get("success"):
                    self._available = True
                    result = {
                        "data": data.get("data"),
                        "meta": data.get("meta", {}),
                    }
                    self._log_response(endpoint, elapsed, result)
                    return result
                else:
                    error(f"[API Client] Request failed: {data.get('error')}")
                    return None

        except urllib.error.URLError:
            return None

    def get_sync_status(self) -> Optional[dict]:
        """Get sync status including backfill state (legacy format).

        DEPRECATED: Use get_detailed_sync_status() for comprehensive info.

        Returns:
            Dict with backfill_active (bool), initial_backfill_done (bool),
            timestamp, and additional fields (phase, progress) for migration.
        """
        return self._request("/api/sync_status")

    def get_detailed_sync_status(self) -> Optional[dict]:
        """Get detailed sync status from hybrid indexer.

        Returns comprehensive status including:
            - phase: Current sync phase (bulk_sessions, bulk_messages, realtime, etc.)
            - progress: Percentage complete (0-100)
            - files_total: Total files to process
            - files_done: Files processed so far
            - queue_size: Files waiting in queue
            - eta_seconds: Estimated time to completion
            - is_ready: True when data is available for queries

        Preferred over get_sync_status() for detailed progress info.
        """
        return self._request("/api/sync/status")

    def get_security_data(
        self, row_limit: int = 100, top_limit: int = 10
    ) -> Optional[dict]:
        """Get security audit data for dashboard.

        Args:
            row_limit: Max rows for commands table
            top_limit: Max items for top lists

        Returns:
            Dict with stats, commands, files, critical_items, or None
        """
        return self._request(
            "/api/security", {"row_limit": row_limit, "top_limit": top_limit}
        )


# Global client instance
_api_client: Optional[AnalyticsAPIClient] = None


def get_api_client() -> AnalyticsAPIClient:
    """Get or create the global API client instance."""
    global _api_client
    if _api_client is None:
        _api_client = AnalyticsAPIClient()
    return _api_client
