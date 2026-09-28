"""
Configuration constants for scripts.

Centralized configuration to avoid duplication across backfill and bulk enrichment scripts.
"""

from pathlib import Path

DEFAULT_DB_PATH = Path.home() / ".config" / "opencode-status-bar" / "analytics.duckdb"
DEFAULT_STORAGE_PATH = Path.home() / ".local" / "share" / "opencode" / "storage"
