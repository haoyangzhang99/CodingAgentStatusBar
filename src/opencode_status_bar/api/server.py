"""
Analytics API Server - Flask server for dashboard data access.

Runs in the menubar process (the only DuckDB writer) and serves
data to the dashboard via HTTP on localhost.

This architecture solves DuckDB's multi-process concurrency limitations.
"""

import threading
from typing import Any, Optional

from flask import Flask
from werkzeug.serving import make_server

from ..analytics import TracingDataService
from ..utils.logger import info
from .config import API_HOST, API_PORT
from .routes import (
    health_bp,
    stats_bp,
    sessions_bp,
    tracing_bp,
    delegations_bp,
    security_bp,
)
from .routes._context import RouteContext


class AnalyticsAPIServer:
    """Flask server for analytics API.

    Runs in a background thread within the menubar process.
    Provides HTTP endpoints for the dashboard to fetch data.

    Uses a lock to serialize DuckDB access since DuckDB doesn't
    handle concurrent access well from multiple threads.
    """

    def __init__(self, host: str = API_HOST, port: int = API_PORT):
        """Initialize the API server.

        Args:
            host: Host to bind to (default: localhost only)
            port: Port to listen on
        """
        self._host = host
        self._port = port
        self._app = Flask(__name__)
        self._server: Any = None  # wsgiref.simple_server.WSGIServer
        self._thread: Optional[threading.Thread] = None
        self._service: Optional[TracingDataService] = None
        self._db_lock = threading.Lock()

        # Configure route context with dependencies
        self._configure_routes()

        # Register blueprints
        self._register_blueprints()

    def _get_service(self) -> TracingDataService:
        """Lazy load the tracing service (uses singleton DB)."""
        if self._service is None:
            self._service = TracingDataService()
        return self._service

    def _configure_routes(self) -> None:
        """Configure the route context with shared dependencies."""
        context = RouteContext.get_instance()
        context.configure(
            db_lock=self._db_lock,
            get_service=self._get_service,
        )

    def _register_blueprints(self) -> None:
        """Register all API route blueprints."""
        self._app.register_blueprint(health_bp)
        self._app.register_blueprint(stats_bp)
        self._app.register_blueprint(sessions_bp)
        self._app.register_blueprint(tracing_bp)
        self._app.register_blueprint(delegations_bp)
        self._app.register_blueprint(security_bp)

    def start(self) -> None:
        """Start the API server in a background thread."""
        if self._thread is not None and self._thread.is_alive():
            return

        def run_server():
            # Disable Flask logging (too verbose)
            import logging

            log = logging.getLogger("werkzeug")
            log.setLevel(logging.ERROR)

            # Use threaded=False to avoid DuckDB concurrency issues
            # Requests will be serialized but that's safer
            self._server = make_server(
                self._host, self._port, self._app, threaded=False
            )
            info(f"[API] Server started on http://{self._host}:{self._port}")
            self._server.serve_forever()

        self._thread = threading.Thread(target=run_server, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the API server."""
        if self._server:
            self._server.shutdown()
            info("[API] Server stopped")
        self._server = None
        self._thread = None

    @property
    def url(self) -> str:
        """Get the base URL of the API server."""
        return f"http://{self._host}:{self._port}"

    @property
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self._thread is not None and self._thread.is_alive()


# Global server instance
_api_server: Optional[AnalyticsAPIServer] = None


def get_api_server() -> AnalyticsAPIServer:
    """Get or create the global API server instance."""
    global _api_server
    if _api_server is None:
        _api_server = AnalyticsAPIServer()
    return _api_server


def start_api_server() -> None:
    """Start the global API server."""
    server = get_api_server()
    server.start()


def stop_api_server() -> None:
    """Stop the global API server."""
    global _api_server
    if _api_server:
        _api_server.stop()
        _api_server = None
