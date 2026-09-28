"""
Security Auditor Package

Provides query-only access to security data from the parts table.
The actual enrichment is handled by SecurityEnrichmentWorker.

Public API:
- SecurityAuditor: Query-only auditor class
- get_auditor(): Get or create global auditor instance
- start_auditor(): Start the auditor (no-op in query-only mode)
- stop_auditor(): Stop the auditor
"""

# Core auditor API
from .core import (
    SecurityAuditor,
    get_auditor,
    start_auditor,
    stop_auditor,
)

# Constants (for patching in tests)
from ._constants import OPENCODE_STORAGE, SCAN_INTERVAL

# Re-export symbols from sibling modules for backwards compatibility
from ..analyzer import analyze_command, get_risk_analyzer
from ..db import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)
from ..sequences import SequenceAnalyzer, SequenceMatch, create_event_from_audit_data
from ..correlator import EventCorrelator, Correlation

# Re-export for backwards compatibility with tests
from . import core as _core

# Expose time for patching in tests
import time  # noqa: F401, E402


__all__ = [
    # Core API
    "SecurityAuditor",
    "time",
    "get_auditor",
    "start_auditor",
    "stop_auditor",
    # Constants
    "OPENCODE_STORAGE",
    "SCAN_INTERVAL",
    # From analyzer
    "analyze_command",
    "get_risk_analyzer",
    # From db (models only, no repository)
    "AuditedCommand",
    "AuditedFileRead",
    "AuditedFileWrite",
    "AuditedWebFetch",
    # From sequences
    "SequenceAnalyzer",
    "SequenceMatch",
    "create_event_from_audit_data",
    # From correlator
    "EventCorrelator",
    "Correlation",
]


# Provide _auditor access at module level for backwards compatibility
def __getattr__(name: str):
    if name == "_auditor":
        return _core._auditor
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __setattr__(name: str, value):
    if name == "_auditor":
        _core._auditor = value
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
