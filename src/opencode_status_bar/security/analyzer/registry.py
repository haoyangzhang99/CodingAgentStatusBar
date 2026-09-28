"""Pattern registry for loading and managing security patterns.

Replaces hardcoded DANGEROUS_PATTERNS and SAFE_PATTERNS lists.
"""

from pathlib import Path
from typing import Optional
import yaml

from .pattern import SecurityPattern, PatternCategory


class PatternRegistry:
    """Manages security patterns loaded from YAML configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize registry with optional custom config path."""
        if config_path is None:
            config_path = self._get_default_config_path()

        self.config_path = config_path
        self.dangerous = PatternCategory("dangerous", [])
        self.safe = PatternCategory("safe", [])

        if config_path.exists():
            self.load()

    @staticmethod
    def _get_default_config_path() -> Path:
        """Get default patterns.yaml path."""
        return Path(__file__).parent.parent / "config" / "patterns.yaml"

    def load(self) -> None:
        """Load patterns from YAML configuration."""
        with open(self.config_path, "r") as f:
            data = yaml.safe_load(f)

        self.dangerous.patterns = [
            SecurityPattern(
                regex=p["regex"],
                score=p["score"],
                reason=p["reason"],
                mitre_techniques=p.get("mitre_techniques", []),
                context_adjustments=[
                    (adj["pattern"], adj["adjustment"])
                    for adj in p.get("context_adjustments", [])
                ],
            )
            for p in data.get("dangerous_patterns", [])
        ]

        self.safe.patterns = [
            SecurityPattern(
                regex=p["regex"],
                score=p["score"],
                reason=p["reason"],
                mitre_techniques=p.get("mitre_techniques", []),
                context_adjustments=[
                    (adj["pattern"], adj["adjustment"])
                    for adj in p.get("context_adjustments", [])
                ],
            )
            for p in data.get("safe_patterns", [])
        ]

    def analyze_command(self, command: str) -> dict:
        """Analyze a command and return risk assessment."""
        dangerous_matches = self.dangerous.match_all(command)
        safe_matches = self.safe.match_all(command)

        if not dangerous_matches:
            return {"risk_level": "safe", "score": 0, "matches": []}

        max_score = max(score for _, score in dangerous_matches)

        if safe_matches:
            max_score = max(0, max_score - 20)

        risk_level = (
            "critical" if max_score >= 80 else "high" if max_score >= 50 else "medium"
        )

        return {
            "risk_level": risk_level,
            "score": max_score,
            "matches": [
                {"reason": p.reason, "score": s, "mitre": p.mitre_techniques}
                for p, s in dangerous_matches
            ],
        }


_default_registry: Optional[PatternRegistry] = None


def get_pattern_registry() -> PatternRegistry:
    """Get singleton pattern registry."""
    global _default_registry
    if _default_registry is None:
        _default_registry = PatternRegistry()
    return _default_registry
