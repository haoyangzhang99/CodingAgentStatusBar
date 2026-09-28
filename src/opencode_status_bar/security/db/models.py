"""
Security Database Models - Dataclasses for audited operations
"""

from dataclasses import dataclass


@dataclass
class AuditedCommand:
    """A command that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    tool: str
    command: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str
    mitre_techniques: str = ""  # JSON array of MITRE technique IDs
    edr_sequence_bonus: int = 0
    edr_correlation_bonus: int = 0


@dataclass
class AuditedFileRead:
    """A file read operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str
    mitre_techniques: str = ""  # JSON array of MITRE technique IDs
    edr_sequence_bonus: int = 0
    edr_correlation_bonus: int = 0
    scope_verdict: str = ""  # in_scope, out_of_scope_allowed, etc.
    scope_resolved_path: str = ""  # Resolved absolute path


@dataclass
class AuditedFileWrite:
    """A file write/edit operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    file_path: str
    operation: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str
    mitre_techniques: str = ""  # JSON array of MITRE technique IDs
    edr_sequence_bonus: int = 0
    edr_correlation_bonus: int = 0
    scope_verdict: str = ""  # in_scope, out_of_scope_allowed, etc.
    scope_resolved_path: str = ""  # Resolved absolute path


@dataclass
class AuditedWebFetch:
    """A webfetch operation that has been analyzed and stored"""

    id: int
    file_id: str
    session_id: str
    url: str
    risk_score: int
    risk_level: str
    risk_reason: str
    timestamp: int
    scanned_at: str
    mitre_techniques: str = ""  # JSON array of MITRE technique IDs
    edr_sequence_bonus: int = 0
    edr_correlation_bonus: int = 0
