"""
Security Analyzer - Risk analysis for commands, files, and URLs

Provides unified security analysis for:
- Bash commands (analyze_command)
- File paths for read/write operations (RiskAnalyzer.analyze_file_path)
- URLs for webfetch operations (RiskAnalyzer.analyze_url)

This module re-exports all public symbols for backward compatibility.
"""

# Types
from .types import RiskLevel, SecurityAlert, RiskResult

# Patterns
from .patterns import (
    DANGEROUS_PATTERNS,
    SAFE_PATTERNS,
    SENSITIVE_FILE_PATTERNS,
    SENSITIVE_URL_PATTERNS,
)

# Command analysis
from .command import analyze_command, get_level_emoji, format_alert_short

# Risk analysis
from .risk import RiskAnalyzer, get_risk_analyzer

__all__ = [
    # Types
    "RiskLevel",
    "SecurityAlert",
    "RiskResult",
    # Patterns
    "DANGEROUS_PATTERNS",
    "SAFE_PATTERNS",
    "SENSITIVE_FILE_PATTERNS",
    "SENSITIVE_URL_PATTERNS",
    # Command analysis
    "analyze_command",
    "get_level_emoji",
    "format_alert_short",
    # Risk analysis
    "RiskAnalyzer",
    "get_risk_analyzer",
]
