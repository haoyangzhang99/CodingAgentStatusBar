"""
Security Database Module - Data models for security auditing

Note: SecurityDatabase and SecurityScannerDuckDB are deprecated.
The auditor now queries the unified `parts` table directly.
"""

from .models import (
    AuditedCommand,
    AuditedFileRead,
    AuditedFileWrite,
    AuditedWebFetch,
)

__all__ = [
    "AuditedCommand",
    "AuditedFileRead",
    "AuditedFileWrite",
    "AuditedWebFetch",
]
