"""
Route Context - Shared dependencies for API routes.

This module provides access to shared resources (db_lock, service getter)
that are initialized by the main server.
"""

import threading
from typing import Callable, Optional

from ...analytics import TracingDataService


class RouteContext:
    """Singleton holding shared dependencies for routes."""

    _instance: Optional["RouteContext"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._db_lock: Optional[threading.Lock] = None
        self._get_service: Optional[Callable[[], TracingDataService]] = None

    @classmethod
    def get_instance(cls) -> "RouteContext":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def configure(
        self,
        db_lock: threading.Lock,
        get_service: Callable[[], TracingDataService],
    ) -> None:
        """Configure the context with dependencies from the server."""
        self._db_lock = db_lock
        self._get_service = get_service

    @property
    def db_lock(self) -> threading.Lock:
        """Get the database lock."""
        if self._db_lock is None:
            raise RuntimeError("RouteContext not configured - call configure() first")
        return self._db_lock

    def get_service(self) -> TracingDataService:
        """Get the tracing data service."""
        if self._get_service is None:
            raise RuntimeError("RouteContext not configured - call configure() first")
        return self._get_service()


# Convenience functions for routes
def get_context() -> RouteContext:
    """Get the route context singleton."""
    return RouteContext.get_instance()


def get_db_lock() -> threading.Lock:
    """Get the database lock."""
    return get_context().db_lock


def get_service() -> TracingDataService:
    """Get the tracing data service."""
    return get_context().get_service()
