"""Shared utilities for loaders."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator


def chunked(lst: list, chunk_size: int) -> Generator[list, None, None]:
    """Yield successive chunks from a list."""
    for i in range(0, len(lst), chunk_size):
        yield lst[i : i + chunk_size]


def collect_recent_part_files(part_dir: Path, max_days: int) -> list[str]:
    """Collect part files from recent directories using mtime filter.

    This is much faster than letting DuckDB scan all files with a glob pattern.

    Args:
        part_dir: Path to the part directory
        max_days: Only include files from directories modified in the last N days

    Returns:
        List of file paths as strings
    """
    cutoff_ts = (datetime.now() - timedelta(days=max_days)).timestamp()
    recent_files: list[str] = []

    for msg_dir in part_dir.iterdir():
        if not msg_dir.is_dir():
            continue
        try:
            if msg_dir.stat().st_mtime < cutoff_ts:
                continue
        except OSError:
            continue

        for f in msg_dir.iterdir():
            if f.suffix == ".json":
                recent_files.append(str(f))

    return recent_files
