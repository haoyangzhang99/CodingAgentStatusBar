"""Tests for datetime utilities."""

from datetime import datetime

from opencode_status_bar.utils.datetime import ms_to_datetime


class TestMsToDatetime:
    """Tests for ms_to_datetime function."""

    def test_valid_timestamp(self):
        """Test conversion of valid millisecond timestamp."""
        # 2024-01-15 12:00:00 UTC = 1705320000000 ms
        ts_ms = 1705320000000
        result = ms_to_datetime(ts_ms)

        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_none_returns_none(self):
        """Test that None input returns None."""
        result = ms_to_datetime(None)
        assert result is None

    def test_zero_returns_none(self):
        """Test that zero returns None (falsy value)."""
        result = ms_to_datetime(0)
        assert result is None

    def test_recent_timestamp(self):
        """Test conversion of a recent timestamp."""
        # Create a known datetime and convert to ms
        known_dt = datetime(2024, 6, 15, 10, 30, 0)
        ts_ms = int(known_dt.timestamp() * 1000)

        result = ms_to_datetime(ts_ms)

        assert isinstance(result, datetime)
        assert result.year == known_dt.year
        assert result.month == known_dt.month
        assert result.day == known_dt.day
        assert result.hour == known_dt.hour
        assert result.minute == known_dt.minute

    def test_millisecond_precision(self):
        """Test that milliseconds are properly handled."""
        # A timestamp with non-zero milliseconds
        ts_ms = 1705320000500  # +500ms
        result = ms_to_datetime(ts_ms)

        assert isinstance(result, datetime)
        assert result.microsecond == 500000

    def test_negative_timestamp(self):
        """Test handling of negative timestamps (dates before epoch)."""
        # Negative timestamp should still work (date before 1970)
        ts_ms = -86400000  # -1 day from epoch
        result = ms_to_datetime(ts_ms)

        assert isinstance(result, datetime)
        assert result.year == 1969
        assert result.month == 12
        assert result.day == 31
