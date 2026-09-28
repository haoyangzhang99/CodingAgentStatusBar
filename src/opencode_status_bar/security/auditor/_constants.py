"""
Constants for the security auditor module.
"""

from pathlib import Path

# Paths
OPENCODE_STORAGE = Path.home() / ".local/share/opencode/storage/part"

# Scan settings
SCAN_INTERVAL = 30  # seconds between incremental scans
