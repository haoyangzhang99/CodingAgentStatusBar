"""
Scope Types - Types for scope-aware security analysis.

Provides:
- ScopeVerdict: Classification of file access based on project scope
- ScopeResult: Result of scope detection with scoring metadata
- ScopeConfig: Optional configuration for scope detection
"""

from dataclasses import dataclass, field
from enum import Enum


class ScopeVerdict(Enum):
    """
    Classification of file access based on project scope.

    Verdicts determine risk scoring and alerting behavior:
    - IN_SCOPE: File is within project directory (no penalty)
    - OUT_OF_SCOPE_ALLOWED: Known safe locations like /tmp/, ~/.cache/ (no penalty)
    - OUT_OF_SCOPE_NEUTRAL: Generic out-of-scope access (base penalty)
    - OUT_OF_SCOPE_SUSPICIOUS: Potentially concerning locations (medium penalty)
    - OUT_OF_SCOPE_SENSITIVE: Security-critical locations (high penalty)
    """

    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE_ALLOWED = "out_of_scope_allowed"
    OUT_OF_SCOPE_NEUTRAL = "out_of_scope_neutral"
    OUT_OF_SCOPE_SUSPICIOUS = "out_of_scope_suspicious"
    OUT_OF_SCOPE_SENSITIVE = "out_of_scope_sensitive"


@dataclass
class ScopeResult:
    """
    Result of scope detection analysis.

    Attributes:
        verdict: The scope classification verdict
        path: The path as provided to the detector
        resolved_path: The fully resolved absolute path
        project_root: The project root used for scope checking
        score_modifier: Risk score adjustment to apply (0-95)
        reason: Human-readable explanation of the verdict
    """

    verdict: ScopeVerdict
    path: str
    resolved_path: str
    project_root: str
    score_modifier: int
    reason: str

    def is_in_scope(self) -> bool:
        """Check if the result indicates in-scope access."""
        return self.verdict == ScopeVerdict.IN_SCOPE

    def is_allowed(self) -> bool:
        """Check if access is allowed without penalty."""
        return self.verdict in (
            ScopeVerdict.IN_SCOPE,
            ScopeVerdict.OUT_OF_SCOPE_ALLOWED,
        )

    def is_sensitive(self) -> bool:
        """Check if access targets a sensitive location."""
        return self.verdict == ScopeVerdict.OUT_OF_SCOPE_SENSITIVE

    def is_suspicious(self) -> bool:
        """Check if access targets a suspicious location."""
        return self.verdict == ScopeVerdict.OUT_OF_SCOPE_SUSPICIOUS


@dataclass
class ScopeConfig:
    """
    Configuration for scope detection.

    Attributes:
        additional_allowed_paths: Extra paths to treat as allowed
        additional_sensitive_paths: Extra paths to treat as sensitive
        write_penalty: Additional score for write operations (default: 10)
    """

    additional_allowed_paths: list[str] = field(default_factory=list)
    additional_sensitive_paths: list[str] = field(default_factory=list)
    write_penalty: int = 10
