"""
Security Analyzer Risk - File and URL risk analysis

Provides:
- RiskAnalyzer: Analyzes file paths and URLs for security risks
- get_risk_analyzer: Get the singleton RiskAnalyzer instance
"""

import re
from typing import Dict, List, Optional, Tuple

from .types import RiskResult
from .patterns import SENSITIVE_FILE_PATTERNS, SENSITIVE_URL_PATTERNS


class RiskAnalyzer:
    """Analyzes file paths and URLs for security risks"""

    @staticmethod
    def _score_to_level(score: int) -> str:
        """Convert a score to a risk level"""
        if score >= 80:
            return "critical"
        elif score >= 50:
            return "high"
        elif score >= 20:
            return "medium"
        return "low"

    @staticmethod
    def _analyze_patterns(
        value: str, patterns: Dict[str, List[Tuple[str, int, str, List[str]]]]
    ) -> Tuple[int, str, List[str]]:
        """Analyze a value against patterns, return max score, reason, and MITRE techniques"""
        value_lower = value.lower()
        max_score = 0
        reason = "Normal"
        mitre_techniques_set: set[str] = set()

        for level in ["critical", "high", "medium"]:
            for entry in patterns.get(level, []):
                pattern, score, desc, mitre = entry
                if re.search(pattern, value_lower):
                    if score > max_score:
                        max_score = score
                        reason = desc
                    mitre_techniques_set.update(mitre)

        return max_score, reason, list(mitre_techniques_set)

    def analyze_file_path(self, file_path: str, write_mode: bool = False) -> RiskResult:
        """Analyze a file path for security risk"""
        score, reason, mitre = self._analyze_patterns(
            file_path, SENSITIVE_FILE_PATTERNS
        )

        if write_mode and score > 0:
            score = min(100, score + 10)
            reason = f"WRITE: {reason}"

        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal file"

        return RiskResult(
            score=score, level=level, reason=reason, mitre_techniques=mitre
        )

    def analyze_url(self, url: str) -> RiskResult:
        """Analyze a URL for security risk"""
        score, reason, mitre = self._analyze_patterns(url, SENSITIVE_URL_PATTERNS)
        level = self._score_to_level(score)

        if score == 0:
            reason = "Normal URL"

        return RiskResult(
            score=score, level=level, reason=reason, mitre_techniques=mitre
        )


# Singleton instance
_analyzer: Optional[RiskAnalyzer] = None


def get_risk_analyzer() -> RiskAnalyzer:
    """Get the singleton RiskAnalyzer instance"""
    global _analyzer
    if _analyzer is None:
        _analyzer = RiskAnalyzer()
    return _analyzer
