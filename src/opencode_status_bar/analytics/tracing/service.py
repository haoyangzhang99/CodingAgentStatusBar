"""TracingDataService - Centralized service for tracing data.

Provides a unified interface for querying and aggregating tracing data
with standardized output format for dashboard consumption.
"""

from typing import Optional, TYPE_CHECKING

from ..db import AnalyticsDB
from ..queries.trace_queries import TraceQueries
from ..queries.session_queries import SessionQueries
from ..queries.tool_queries import ToolQueries
from ..queries.delegation_queries import DelegationQueries

from .config import TracingConfig
from .helpers import HelpersMixin
from .session_queries import SessionQueriesMixin
from .stats_queries import StatsQueriesMixin
from .list_queries import ListQueriesMixin
from .detail_queries import DetailQueriesMixin

if TYPE_CHECKING:
    import duckdb


class TracingDataService(
    HelpersMixin,
    SessionQueriesMixin,
    StatsQueriesMixin,
    ListQueriesMixin,
    DetailQueriesMixin,
):
    """Centralized service for tracing data queries.

    Provides standardized methods for retrieving session data,
    computing KPIs, and generating dashboard-ready output.

    All methods return dictionaries with a consistent structure:
    {
        "meta": {...},      # Query metadata
        "summary": {...},   # Key metrics for quick display
        "details": {...},   # Detailed breakdown
        "charts": {...}     # Pre-formatted chart data
    }

    This class combines functionality from multiple mixins:
    - HelpersMixin: Private utility methods
    - SessionQueriesMixin: Session-specific queries
    - StatsQueriesMixin: Global and daily statistics
    - ListQueriesMixin: Paginated list queries
    - DetailQueriesMixin: Detailed trace and cost queries
    """

    def __init__(
        self,
        db: Optional[AnalyticsDB] = None,
        config: Optional[TracingConfig] = None,
    ):
        """Initialize the tracing data service.

        Args:
            db: Analytics database instance. Creates new if not provided.
            config: Configuration for calculations. Uses defaults if not provided.
        """
        from ..db import get_analytics_db

        self._db = db or get_analytics_db()
        self._config = config or TracingConfig()
        self._trace_q = TraceQueries(self._db)
        self._session_q = SessionQueries(self._db)
        self._tool_q = ToolQueries(self._db)
        self._delegation_q = DelegationQueries(self._db)

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get database connection."""
        return self._db.connect()
