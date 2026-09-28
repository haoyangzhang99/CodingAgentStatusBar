"""Tests for DiffPathMatcher path matching utilities."""

import pytest

from opencode_status_bar.analytics.path_matcher import (
    DiffPathMatcher,
    DiffStats,
    build_diff_stats_map,
)


class TestDiffPathMatcher:
    """Tests for the DiffPathMatcher class."""

    def test_exact_match(self):
        """Level 1: Exact path matches."""
        diff_by_file = {"src/file.py": DiffStats(additions=10, deletions=5)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("src/file.py")

        assert result is not None
        assert result["additions"] == 10
        assert result["deletions"] == 5

    def test_normalized_path_match_strip_dot_slash(self):
        """Level 2: Normalized path strips leading ./"""
        diff_by_file = {"./src/file.py": DiffStats(additions=10, deletions=5)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("src/file.py")

        assert result is not None
        assert result["additions"] == 10

    def test_normalized_path_match_from_operation(self):
        """Level 2: Operation path with ./ matches diff without ./"""
        diff_by_file = {"src/file.py": DiffStats(additions=10, deletions=5)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("./src/file.py")

        assert result is not None
        assert result["additions"] == 10

    def test_suffix_match_absolute_to_relative(self):
        """Level 3: Absolute path matches relative diff path."""
        diff_by_file = {"src/utils/helper.py": DiffStats(additions=20, deletions=3)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("/Users/dev/project/src/utils/helper.py")

        assert result is not None
        assert result["additions"] == 20
        assert result["deletions"] == 3

    def test_suffix_match_relative_to_absolute(self):
        """Level 3: Relative path matches absolute diff path."""
        diff_by_file = {
            "/Users/dev/project/src/module.py": DiffStats(additions=15, deletions=0)
        }
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("src/module.py")

        assert result is not None
        assert result["additions"] == 15

    def test_basename_match_last_resort(self):
        """Level 4: Basename match when no other match works."""
        diff_by_file = {"some/path/config.json": DiffStats(additions=5, deletions=2)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("/completely/different/path/config.json")

        assert result is not None
        assert result["additions"] == 5
        assert result["deletions"] == 2

    def test_no_match_returns_none(self):
        """No match returns None."""
        diff_by_file = {"src/file.py": DiffStats(additions=10, deletions=5)}
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("other/different.py")

        assert result is None

    def test_basename_collision_detection(self):
        """Basename collisions are detected and skipped."""
        diff_by_file = {
            "src/utils.py": DiffStats(additions=10, deletions=5),
            "tests/utils.py": DiffStats(additions=20, deletions=3),
        }
        matcher = DiffPathMatcher(diff_by_file)

        assert matcher.has_collisions
        assert "utils.py" in matcher.collision_basenames

        result = matcher.match("/other/path/utils.py")
        assert result is None

    def test_basename_no_collision_single_file(self):
        """Single file per basename has no collision."""
        diff_by_file = {
            "src/config.py": DiffStats(additions=10, deletions=5),
            "tests/test_utils.py": DiffStats(additions=20, deletions=3),
        }
        matcher = DiffPathMatcher(diff_by_file)

        assert not matcher.has_collisions

        result = matcher.match("/any/path/config.py")
        assert result is not None
        assert result["additions"] == 10

    def test_collision_does_not_affect_exact_match(self):
        """Even with collision, exact match still works."""
        diff_by_file = {
            "src/utils.py": DiffStats(additions=10, deletions=5),
            "tests/utils.py": DiffStats(additions=20, deletions=3),
        }
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("src/utils.py")
        assert result is not None
        assert result["additions"] == 10

        result = matcher.match("tests/utils.py")
        assert result is not None
        assert result["additions"] == 20

    def test_collision_does_not_affect_suffix_match(self):
        """Even with collision, suffix match still works."""
        diff_by_file = {
            "src/utils.py": DiffStats(additions=10, deletions=5),
            "tests/utils.py": DiffStats(additions=20, deletions=3),
        }
        matcher = DiffPathMatcher(diff_by_file)

        result = matcher.match("/project/src/utils.py")
        assert result is not None
        assert result["additions"] == 10

    def test_empty_diff_by_file(self):
        """Empty diff_by_file returns None for any path."""
        matcher = DiffPathMatcher({})

        result = matcher.match("any/path.py")

        assert result is None
        assert not matcher.has_collisions


class TestBuildDiffStatsMap:
    """Tests for the build_diff_stats_map utility function."""

    def test_builds_map_from_raw_data(self):
        """Builds correct map from raw JSON data."""
        raw_data = [
            {"file": "src/a.py", "additions": 10, "deletions": 5},
            {"file": "src/b.py", "additions": 3, "deletions": 0},
        ]

        result = build_diff_stats_map(raw_data)

        assert len(result) == 2
        assert result["src/a.py"]["additions"] == 10
        assert result["src/a.py"]["deletions"] == 5
        assert result["src/b.py"]["additions"] == 3

    def test_skips_items_without_file(self):
        """Items without 'file' key are skipped."""
        raw_data = [
            {"file": "src/a.py", "additions": 10, "deletions": 5},
            {"additions": 3, "deletions": 0},
            {"file": None, "additions": 1, "deletions": 1},
        ]

        result = build_diff_stats_map(raw_data)

        assert len(result) == 1
        assert "src/a.py" in result

    def test_skips_non_dict_items(self):
        """Non-dict items in list are skipped."""
        raw_data = [
            {"file": "src/a.py", "additions": 10, "deletions": 5},
            "not a dict",
            123,
            None,
        ]

        result = build_diff_stats_map(raw_data)

        assert len(result) == 1

    def test_defaults_to_zero_for_missing_counts(self):
        """Missing additions/deletions default to 0."""
        raw_data = [
            {"file": "src/a.py"},
            {"file": "src/b.py", "additions": 5},
        ]

        result = build_diff_stats_map(raw_data)

        assert result["src/a.py"]["additions"] == 0
        assert result["src/a.py"]["deletions"] == 0
        assert result["src/b.py"]["additions"] == 5
        assert result["src/b.py"]["deletions"] == 0

    def test_empty_list_returns_empty_dict(self):
        """Empty list returns empty dict."""
        result = build_diff_stats_map([])

        assert result == {}
