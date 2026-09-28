"""
Security auditor mock factories.

Provides mock objects for SecurityAuditor, SecurityDatabase, RiskAnalyzer.
"""

from unittest.mock import MagicMock

from .database import create_default_auditor_stats, create_mock_db


def create_mock_security_db(
    stats: dict | None = None,
    scanned_ids: set | None = None,
) -> MagicMock:
    """Create a mock SecurityDatabase.

    Alias for create_mock_db for explicit naming.

    Args:
        stats: Custom stats dict
        scanned_ids: Set of already scanned IDs

    Returns:
        MagicMock configured as SecurityDatabase
    """
    return create_mock_db(stats=stats, scanned_ids=scanned_ids)


def create_mock_analyzer(
    file_risk_score: int = 60,
    file_risk_level: str = "high",
    url_risk_score: int = 85,
    url_risk_level: str = "critical",
) -> MagicMock:
    """Create a mock RiskAnalyzer.

    Args:
        file_risk_score: Default risk score for file analysis
        file_risk_level: Default risk level for file analysis
        url_risk_score: Default risk score for URL analysis
        url_risk_level: Default risk level for URL analysis

    Returns:
        MagicMock configured as RiskAnalyzer
    """
    from opencode_status_bar.security.analyzer import RiskResult

    analyzer = MagicMock()
    analyzer.analyze_file_path.return_value = RiskResult(
        score=file_risk_score,
        level=file_risk_level,
        reason="Test file analysis",
    )
    analyzer.analyze_url.return_value = RiskResult(
        score=url_risk_score,
        level=url_risk_level,
        reason="Test URL analysis",
    )
    analyzer.analyze_command.return_value = RiskResult(
        score=50,
        level="medium",
        reason="Test command analysis",
    )
    return analyzer


def create_mock_auditor(
    mock_db: MagicMock | None = None,
    stats: dict | None = None,
) -> MagicMock:
    """Create a mock SecurityAuditor with default configuration.

    Args:
        mock_db: Mock database to use (creates new if None)
        stats: Custom stats dict

    Returns:
        MagicMock configured as SecurityAuditor
    """
    if mock_db is None:
        mock_db = create_mock_db(stats=stats)

    auditor = MagicMock()
    auditor.get_stats.return_value = stats or create_default_auditor_stats()
    auditor.get_critical_commands.return_value = []
    auditor.get_sensitive_reads.return_value = []
    auditor.get_sensitive_writes.return_value = []
    auditor.get_risky_webfetches.return_value = []
    auditor.get_all_commands.return_value = []
    auditor.get_all_reads.return_value = []
    auditor.get_all_writes.return_value = []
    auditor.get_all_webfetches.return_value = []
    auditor.generate_report.return_value = "Security Report"
    auditor._db = mock_db
    return auditor


def create_mock_scanner() -> MagicMock:
    """Create a mock SecurityScannerDuckDB.

    DEPRECATED: SecurityScannerDuckDB is now an alias for SecurityDatabase.
    Use create_mock_db() instead, which includes scanner methods.

    Returns:
        MagicMock configured with scanner methods (via create_mock_db)
    """
    # SecurityScannerDuckDB = SecurityDatabase, so just return a mock db
    return create_mock_db()
