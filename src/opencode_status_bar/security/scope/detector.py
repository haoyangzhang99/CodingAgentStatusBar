"""
Scope Detector - Detect whether file access is within project scope.

Provides intelligent path classification for security analysis:
- Determines if paths are inside or outside project directory
- Classifies out-of-scope access by risk level
- Returns score modifiers for risk calculation
"""

import os
from pathlib import Path
from typing import Optional

from .patterns import (
    ALLOWED_PATHS,
    SENSITIVE_PATHS,
    SUSPICIOUS_PATHS,
    WRITE_PENALTIES,
)
from .types import ScopeConfig, ScopeResult, ScopeVerdict


class ScopeDetector:
    """
    Detects whether file access is within project scope.

    The detector resolves paths, checks project boundaries, and classifies
    out-of-scope access by security sensitivity.

    Example:
        detector = ScopeDetector(Path("/home/user/project"))
        result = detector.detect("../secrets.txt")
        if result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE:
            print(f"Sensitive access: {result.reason}")
    """

    def __init__(
        self,
        project_root: Path,
        config: Optional[ScopeConfig] = None,
    ) -> None:
        """
        Initialize the scope detector.

        Args:
            project_root: The root directory of the current project
            config: Optional configuration for customizing detection
        """
        self.project_root = project_root.resolve()
        self.home = Path.home()
        self._config = config or ScopeConfig()

        # Pre-resolve home-relative paths in patterns
        self._allowed_patterns = self._build_allowed_patterns()
        self._suspicious_patterns = self._build_suspicious_patterns()
        self._sensitive_patterns = self._build_sensitive_patterns()

    def _build_allowed_patterns(self) -> list[tuple[str, str]]:
        """Build resolved allowed path patterns."""
        patterns: list[tuple[str, str]] = []
        home_str = str(self.home)

        for pattern, reason in ALLOWED_PATHS:
            if pattern.startswith("/") and not pattern.startswith("/."):
                # Absolute pattern (like /tmp/) - keep as is
                patterns.append((pattern, reason))
            elif pattern.startswith("/."):
                # Home-relative pattern (starts with /.)
                # Keep the full pattern: {home} + /.cache/ = {home}/.cache/
                resolved = home_str + pattern
                patterns.append((resolved, reason))
            else:
                # Generic pattern - match anywhere
                patterns.append((pattern, reason))

        # Add custom allowed paths
        for path in self._config.additional_allowed_paths:
            patterns.append((path, "Custom allowed path"))

        return patterns

    def _build_suspicious_patterns(self) -> list[tuple[str, int, str]]:
        """Build resolved suspicious path patterns."""
        patterns: list[tuple[str, int, str]] = []
        home_str = str(self.home)

        for pattern, score, reason in SUSPICIOUS_PATHS:
            if pattern.startswith("/") and not pattern.startswith("/."):
                patterns.append((pattern, score, reason))
            elif pattern.startswith("/."):
                resolved = home_str + pattern
                patterns.append((resolved, score, reason))
            else:
                patterns.append((pattern, score, reason))

        return patterns

    def _build_sensitive_patterns(self) -> list[tuple[str, int, str]]:
        """Build resolved sensitive path patterns."""
        patterns: list[tuple[str, int, str]] = []
        home_str = str(self.home)

        for pattern, score, reason in SENSITIVE_PATHS:
            if pattern.startswith("/") and not pattern.startswith("/."):
                # Absolute pattern like /etc/
                patterns.append((pattern, score, reason))
            elif pattern.startswith("~"):
                # Expand ~ to home directory (~/Library -> {home}/Library)
                resolved = home_str + pattern[1:]
                patterns.append((resolved, score, reason))
            elif pattern.startswith("/."):
                # Home-relative pattern (/.ssh/ -> {home}/.ssh/)
                resolved = home_str + pattern
                patterns.append((resolved, score, reason))
            elif pattern.startswith("."):
                # Relative pattern like ".env" - match anywhere
                patterns.append((pattern, score, reason))
            else:
                # Generic pattern
                patterns.append((pattern, score, reason))

        # Add custom sensitive paths
        for path in self._config.additional_sensitive_paths:
            patterns.append((path, 75, "Custom sensitive path"))

        return patterns

    def _resolve_path(self, file_path: str) -> Path:
        """
        Resolve a path to its absolute, canonical form.

        Handles:
        - ~ expansion
        - Relative paths (resolved against project_root)
        - Symlink resolution
        - .. and . components

        Args:
            file_path: The path to resolve

        Returns:
            Resolved Path object
        """
        path = Path(file_path)

        # Expand ~ to home directory
        if str(file_path).startswith("~"):
            path = path.expanduser()

        # Make relative paths absolute (relative to project root)
        if not path.is_absolute():
            path = self.project_root / path

        # Resolve symlinks and normalize (handles .., .)
        try:
            # resolve() handles symlinks and normalizes the path
            return path.resolve()
        except (OSError, RuntimeError):
            # Handle broken symlinks or permission errors
            # Fall back to normpath without symlink resolution
            return Path(os.path.normpath(str(path)))

    def _is_in_project(self, resolved_path: Path) -> bool:
        """Check if a path is within the project directory."""
        try:
            # Check if the resolved path is relative to project root
            resolved_path.relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _check_allowed(self, path_str: str) -> Optional[str]:
        """
        Check if path matches an allowed pattern.

        Returns:
            Reason string if allowed, None otherwise
        """
        for pattern, reason in self._allowed_patterns:
            if pattern in path_str:
                return reason
        return None

    def _check_sensitive(self, path_str: str) -> Optional[tuple[int, str]]:
        """
        Check if path matches a sensitive pattern.

        Returns:
            Tuple of (score, reason) if sensitive, None otherwise
        """
        best_match: Optional[tuple[int, str]] = None

        for pattern, score, reason in self._sensitive_patterns:
            if pattern in path_str:
                # Keep the highest scoring match
                if best_match is None or score > best_match[0]:
                    best_match = (score, reason)

        return best_match

    def _check_suspicious(self, path_str: str) -> Optional[tuple[int, str]]:
        """
        Check if path matches a suspicious pattern.

        Returns:
            Tuple of (score, reason) if suspicious, None otherwise
        """
        best_match: Optional[tuple[int, str]] = None

        for pattern, score, reason in self._suspicious_patterns:
            if pattern in path_str:
                # Keep the highest scoring match
                if best_match is None or score > best_match[0]:
                    best_match = (score, reason)

        return best_match

    def detect(self, file_path: str, operation: str = "read") -> ScopeResult:
        """
        Detect the scope classification of a file access.

        Args:
            file_path: The path being accessed
            operation: The type of operation ("read" or "write")

        Returns:
            ScopeResult with verdict and metadata

        Example:
            result = detector.detect("~/.ssh/id_rsa", "read")
            # result.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE
            # result.score_modifier == 85
        """
        # Resolve the path
        try:
            resolved = self._resolve_path(file_path)
            resolved_str = str(resolved)
        except Exception:
            # If we can't resolve the path, treat it as neutral
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_NEUTRAL,
                path=file_path,
                resolved_path=file_path,
                project_root=str(self.project_root),
                score_modifier=25,
                reason="Unable to resolve path",
            )

        # 1. Check if in project scope
        if self._is_in_project(resolved):
            return ScopeResult(
                verdict=ScopeVerdict.IN_SCOPE,
                path=file_path,
                resolved_path=resolved_str,
                project_root=str(self.project_root),
                score_modifier=0,
                reason="Path is within project directory",
            )

        # 2. Check sensitive patterns FIRST (security takes priority)
        # This ensures paths like ~/.ssh are flagged even if inside temp directories
        sensitive_match = self._check_sensitive(resolved_str)
        if sensitive_match:
            score, reason = sensitive_match
            # Apply write penalty
            if operation == "write":
                score = min(95, score + WRITE_PENALTIES["sensitive"])
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_SENSITIVE,
                path=file_path,
                resolved_path=resolved_str,
                project_root=str(self.project_root),
                score_modifier=score,
                reason=reason,
            )

        # 3. Check allowed patterns (safe temp/cache dirs - before suspicious)
        allowed_reason = self._check_allowed(resolved_str)
        if allowed_reason:
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_ALLOWED,
                path=file_path,
                resolved_path=resolved_str,
                project_root=str(self.project_root),
                score_modifier=0,
                reason=allowed_reason,
            )

        # 4. Check suspicious patterns
        suspicious_match = self._check_suspicious(resolved_str)
        if suspicious_match:
            score, reason = suspicious_match
            # Apply write penalty
            if operation == "write":
                score = min(95, score + WRITE_PENALTIES["suspicious"])
            return ScopeResult(
                verdict=ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS,
                path=file_path,
                resolved_path=resolved_str,
                project_root=str(self.project_root),
                score_modifier=score,
                reason=reason,
            )

        # 5. Default to neutral
        base_score = 25 if operation == "read" else 35
        return ScopeResult(
            verdict=ScopeVerdict.OUT_OF_SCOPE_NEUTRAL,
            path=file_path,
            resolved_path=resolved_str,
            project_root=str(self.project_root),
            score_modifier=base_score,
            reason="Generic out-of-scope access",
        )

    def is_in_scope(self, file_path: str) -> bool:
        """
        Quick check if a path is within project scope.

        This is a convenience method for simple scope checks.

        Args:
            file_path: The path to check

        Returns:
            True if path is within project directory
        """
        try:
            resolved = self._resolve_path(file_path)
            return self._is_in_project(resolved)
        except Exception:
            return False
