"""Security pattern domain model.

Replaces hardcoded tuples with validated dataclasses.
"""

import re
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class SecurityPattern:
    """Represents a security risk detection pattern.

    Replaces tuple format: (regex, score, reason, adjustments, mitre_techniques)
    """

    regex: str
    score: int
    reason: str
    mitre_techniques: list[str] = field(default_factory=list)
    context_adjustments: list[tuple[str, int]] = field(default_factory=list)

    VALID_TECHNIQUES: ClassVar[set[str]] = {
        "T1059",
        "T1048",
        "T1070",
        "T1222",
        "T1105",
        "T1053",
        "T1087",
        "T1082",
        "T1485",
        "T1548",
        "T1021",
        "T1497",
        "T1564",
        "T1562",
        "T1036",
    }

    def __post_init__(self):
        """Validate pattern after initialization."""
        try:
            re.compile(self.regex)
        except re.error as e:
            raise ValueError(f"Invalid regex pattern '{self.regex}': {e}")

        if not 0 <= self.score <= 100:
            raise ValueError(f"Score must be 0-100, got {self.score}")

        for technique in self.mitre_techniques:
            if technique not in self.VALID_TECHNIQUES:
                raise ValueError(f"Unknown MITRE technique: {technique}")

    def matches(self, command: str) -> bool:
        """Check if pattern matches the command."""
        return bool(re.search(self.regex, command))

    def calculate_score(self, command: str) -> int:
        """Calculate adjusted score based on context."""
        if not self.matches(command):
            return 0

        adjusted_score = self.score
        for adjustment_pattern, adjustment in self.context_adjustments:
            if re.search(adjustment_pattern, command):
                adjusted_score += adjustment

        return max(0, min(100, adjusted_score))


@dataclass
class PatternCategory:
    """Group of related patterns."""

    name: str
    patterns: list[SecurityPattern]

    def match_all(self, command: str) -> list[tuple[SecurityPattern, int]]:
        """Find all matching patterns with scores."""
        matches = []
        for pattern in self.patterns:
            score = pattern.calculate_score(command)
            if score > 0:
                matches.append((pattern, score))
        return matches
