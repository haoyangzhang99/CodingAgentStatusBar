"""
Security Analyzer Command - Command analysis functions

Provides:
- analyze_command: Analyze a bash command for security risks
- get_level_emoji: Get emoji indicator for risk level
- format_alert_short: Format alert for menu display
"""

import re

from .types import RiskLevel, SecurityAlert
from .patterns import DANGEROUS_PATTERNS, SAFE_PATTERNS


def analyze_command(command: str, tool: str = "bash") -> SecurityAlert:
    """Analyze a command and return a security alert with risk score."""
    if not command or not command.strip():
        return SecurityAlert(
            command=command,
            tool=tool,
            score=0,
            level=RiskLevel.LOW,
            reason="Empty command",
            mitre_techniques=[],
        )

    max_score = 0
    primary_reason = "Normal operation"
    mitre_techniques_set: set[str] = set()

    for entry in DANGEROUS_PATTERNS:
        # Handle both old format (4 elements) and new format (5 elements with MITRE)
        if len(entry) == 5:
            pattern, base_score, reason, context_adjustments, mitre = entry
        else:
            pattern, base_score, reason, context_adjustments = entry
            mitre = []

        if re.search(pattern, command, re.IGNORECASE):
            adjusted_score = base_score
            for ctx_pattern, modifier in context_adjustments:
                if re.search(ctx_pattern, command, re.IGNORECASE):
                    adjusted_score += modifier
            if adjusted_score > max_score:
                max_score = adjusted_score
                primary_reason = reason
            if mitre:
                mitre_techniques_set.update(mitre)

    for pattern, modifier, _ in SAFE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            max_score += modifier

    max_score = max(0, min(100, max_score))

    if max_score >= 80:
        level = RiskLevel.CRITICAL
    elif max_score >= 50:
        level = RiskLevel.HIGH
    elif max_score >= 20:
        level = RiskLevel.MEDIUM
    else:
        level = RiskLevel.LOW

    return SecurityAlert(
        command=command,
        tool=tool,
        score=max_score,
        level=level,
        reason=primary_reason,
        mitre_techniques=list(mitre_techniques_set),
    )


def get_level_emoji(level: RiskLevel) -> str:
    """Return emoji indicator for risk level"""
    return {
        RiskLevel.LOW: "",
        RiskLevel.MEDIUM: "🟡",
        RiskLevel.HIGH: "🟠",
        RiskLevel.CRITICAL: "🔴",
    }.get(level, "")


def format_alert_short(alert: SecurityAlert, max_length: int = 40) -> str:
    """Format alert for menu display (short form)"""
    emoji = get_level_emoji(alert.level)
    cmd = (
        alert.command[:max_length] + "..."
        if len(alert.command) > max_length
        else alert.command
    )
    if emoji:
        return f"{emoji} {cmd}"
    return cmd
