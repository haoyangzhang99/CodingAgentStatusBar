"""
Security Analyzer Types - Common types for security analysis

Provides:
- RiskLevel: Enum for risk severity levels
- SecurityAlert: Result of command security analysis
- RiskResult: Result of file/URL risk analysis
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class RiskLevel(Enum):
    """Risk levels for security analysis"""

    LOW = "low"  # 0-19: Normal operations
    MEDIUM = "medium"  # 20-49: Potential impact
    HIGH = "high"  # 50-79: Sensitive operations
    CRITICAL = "critical"  # 80-100: Major risk


@dataclass
class SecurityAlert:
    """Result of security analysis for a command"""

    command: str
    tool: str
    score: int
    level: RiskLevel
    reason: str
    agent_id: Optional[str] = None
    agent_title: Optional[str] = None
    mitre_techniques: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.mitre_techniques is None:
            self.mitre_techniques = []


@dataclass
class RiskResult:
    """Result of a file/URL risk analysis"""

    score: int
    level: str
    reason: str
    mitre_techniques: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.mitre_techniques is None:
            self.mitre_techniques = []
