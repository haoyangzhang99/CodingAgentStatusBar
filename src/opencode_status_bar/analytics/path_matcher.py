"""
Path matching utilities for diff enrichment.

Provides multi-level path matching between diff stats (usually relative paths)
and file operations (often absolute paths).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypedDict


class DiffStats(TypedDict):
    """Statistics for a file diff."""

    additions: int
    deletions: int


@dataclass
class DiffPathMatcher:
    """
    Matches file operations to diff stats with multi-level fallback.

    Handles path format mismatches between:
    - Relative paths (./src/file.py, src/file.py)
    - Absolute paths (/Users/.../src/file.py)
    - Different prefix variations

    Matching levels (in order):
    1. Exact match
    2. Normalized path match (strip ./)
    3. Suffix match (handles absolute vs relative)
    4. Basename match (last resort, uses filename only)
    """

    diff_by_file: dict[str, DiffStats]
    suffix_map: dict[str, DiffStats] = field(default_factory=dict)
    basename_map: dict[str, DiffStats] = field(default_factory=dict)
    _basename_collisions: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Build lookup maps from diff_by_file."""
        self._build_lookup_maps()

    def _build_lookup_maps(self) -> None:
        """Pre-build suffix and basename maps for O(1) lookups."""
        # Track basenames we've seen to detect collisions
        seen_basenames: dict[str, str] = {}  # basename -> first diff_path

        for diff_path, diff_stats in self.diff_by_file.items():
            # Normalized path (strip leading ./)
            norm_path = diff_path.lstrip("./")
            self.suffix_map[norm_path] = diff_stats
            self.suffix_map[diff_path] = diff_stats

            # Basename for absolute path matching
            basename = diff_path.rsplit("/", 1)[-1]

            if basename in seen_basenames:
                # Collision detected - mark as unsafe
                self._basename_collisions.add(basename)
            else:
                seen_basenames[basename] = diff_path
                self.basename_map[basename] = diff_stats

        # Remove colliding basenames from the map to avoid false positives
        for colliding_basename in self._basename_collisions:
            self.basename_map.pop(colliding_basename, None)

    def match(self, file_path: str) -> DiffStats | None:
        """
        Try 4 levels of matching: exact -> normalized -> suffix -> basename.

        Args:
            file_path: The file path to match (can be absolute or relative)

        Returns:
            DiffStats if matched, None otherwise
        """
        # Level 1: Exact match
        stats = self.diff_by_file.get(file_path)
        if stats:
            return stats

        # Level 2: Normalized path match (strip ./)
        norm_file_path = file_path.lstrip("./")
        stats = self.suffix_map.get(norm_file_path)
        if stats:
            return stats

        # Level 3: Suffix match (handles absolute vs relative paths)
        for suffix_key in self.suffix_map:
            if norm_file_path.endswith(suffix_key) or suffix_key.endswith(
                norm_file_path
            ):
                return self.suffix_map[suffix_key]

        # Level 4: Basename match (last resort)
        # Only used if no collision was detected for this basename
        op_basename = file_path.rsplit("/", 1)[-1]
        return self.basename_map.get(op_basename)

    @property
    def has_collisions(self) -> bool:
        """Check if any basename collisions were detected."""
        return len(self._basename_collisions) > 0

    @property
    def collision_basenames(self) -> set[str]:
        """Get basenames that had collisions (skipped for safety)."""
        return self._basename_collisions.copy()


def build_diff_stats_map(raw_diff_data: list[dict]) -> dict[str, DiffStats]:
    """
    Build a diff stats map from raw session_diff JSON data.

    Args:
        raw_diff_data: List of diff items with 'file', 'additions', 'deletions'

    Returns:
        Dict mapping file path to DiffStats
    """
    result: dict[str, DiffStats] = {}
    for item in raw_diff_data:
        if isinstance(item, dict):
            file_path = item.get("file")
            if file_path:
                result[file_path] = DiffStats(
                    additions=item.get("additions", 0),
                    deletions=item.get("deletions", 0),
                )
    return result
