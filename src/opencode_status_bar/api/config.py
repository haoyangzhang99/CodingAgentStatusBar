"""
API Configuration - Shared constants for client and server.

Centralizes configuration to avoid duplication and ensure consistency.
"""

# Network configuration
API_HOST = "127.0.0.1"
API_PORT = 19876

# Timeouts (in seconds)
API_TIMEOUT = 30  # Client timeout for requests
SERVER_SHUTDOWN_TIMEOUT = 5  # Server shutdown grace period


# API endpoints base URL
def get_base_url(host: str = API_HOST, port: int = API_PORT) -> str:
    """Get the base URL for API requests."""
    return f"http://{host}:{port}"
