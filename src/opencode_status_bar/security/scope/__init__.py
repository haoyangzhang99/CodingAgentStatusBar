"""
Scope-Aware Security Detection.

Analyzes file paths relative to project scope to detect out-of-scope accesses.

Exports:
- ScopeDetector: Main detector class for scope analysis
- ScopeVerdict: Enum of possible scope verdicts
- ScopeResult: Dataclass with detection results
- ScopeConfig: Configuration for scope detection
"""

from .detector import ScopeDetector
from .path_extractor import PathExtractor
from .types import ScopeConfig, ScopeResult, ScopeVerdict

__all__ = [
    "ScopeDetector",
    "ScopeVerdict",
    "ScopeResult",
    "ScopeConfig",
    "PathExtractor",
]
