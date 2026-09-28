"""
Base class for analytics queries.

Provides database connection access to all query classes.
"""

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..db import AnalyticsDB


class BaseQueries:
    """Base class providing database access for query modules."""

    def __init__(self, db: "AnalyticsDB"):
        """Initialize with a database instance.

        Args:
            db: The analytics database instance
        """
        self._db = db

    @property
    def _conn(self):
        """Get database connection."""
        return self._db.connect()

    def _get_date_range(self, days: int) -> tuple[datetime, datetime]:
        """Calculate date range from days ago to now.

        Args:
            days: Number of days to go back

        Returns:
            Tuple of (start_date, end_date)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        return start_date, end_date
