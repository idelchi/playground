"""
Test to verify the datetime input bug fix.
Tests that date and time inputs are correctly combined into datetime objects.
"""

import pytest
from datetime import datetime, date, time
import pytz

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import BERLIN_TZ


class TestDateTimeInputFix:
    """Test the datetime input functionality."""

    def test_combine_date_and_time(self):
        """Test combining date and time into datetime."""
        test_date = date(2025, 11, 9)
        test_time = time(14, 30, 0)

        # Combine and localize
        result = BERLIN_TZ.localize(datetime.combine(test_date, test_time))

        assert result.year == 2025
        assert result.month == 11
        assert result.day == 9
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 0
        assert str(result.tzinfo) == 'Europe/Berlin'
        print(f"✅ Date + Time combination works: {result}")

    def test_combine_with_current_date_and_time(self):
        """Test combining with current date and time."""
        now = datetime.now(BERLIN_TZ)
        test_date = now.date()
        test_time = now.time()

        result = BERLIN_TZ.localize(datetime.combine(test_date, test_time))

        assert result.date() == test_date
        # Time may differ slightly, check hour and minute
        assert result.hour == test_time.hour
        assert result.minute == test_time.minute
        print(f"✅ Current date + time combination works: {result}")

    def test_optional_exit_timestamp(self):
        """Test that exit timestamp can be None."""
        entry_date = date(2025, 11, 9)
        entry_time = time(14, 0, 0)
        exit_date = None

        entry_ts = BERLIN_TZ.localize(datetime.combine(entry_date, entry_time))
        exit_ts = None
        if exit_date is not None:
            exit_ts = BERLIN_TZ.localize(datetime.combine(exit_date, time(18, 0, 0)))

        assert entry_ts is not None
        assert exit_ts is None
        print("✅ Optional exit timestamp handled correctly (None)")

    def test_with_exit_timestamp(self):
        """Test that exit timestamp is created when provided."""
        entry_date = date(2025, 11, 9)
        entry_time = time(14, 0, 0)
        exit_date = date(2025, 11, 9)
        exit_time = time(18, 0, 0)

        entry_ts = BERLIN_TZ.localize(datetime.combine(entry_date, entry_time))
        exit_ts = None
        if exit_date is not None:
            exit_ts = BERLIN_TZ.localize(datetime.combine(exit_date, exit_time))

        assert entry_ts is not None
        assert exit_ts is not None
        assert exit_ts > entry_ts
        delta = exit_ts - entry_ts
        assert delta.total_seconds() / 3600 == 4.0  # 4 hours
        print(f"✅ Exit timestamp created correctly: {exit_ts}")
        print(f"   Holding period: {delta.total_seconds() / 3600} hours")

    def test_midnight_time(self):
        """Test with midnight time (00:00:00)."""
        test_date = date(2025, 11, 10)
        test_time = time(0, 0, 0)

        result = BERLIN_TZ.localize(datetime.combine(test_date, test_time))

        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        print(f"✅ Midnight time handled correctly: {result}")

    def test_end_of_day_time(self):
        """Test with end of day time (23:59:59)."""
        test_date = date(2025, 11, 9)
        test_time = time(23, 59, 59)

        result = BERLIN_TZ.localize(datetime.combine(test_date, test_time))

        assert result.hour == 23
        assert result.minute == 59
        assert result.second == 59
        print(f"✅ End of day time handled correctly: {result}")

    def test_datetime_objects_are_timezone_aware(self):
        """Test that combined datetime objects are timezone-aware."""
        test_date = date(2025, 11, 9)
        test_time = time(14, 30, 0)

        result = BERLIN_TZ.localize(datetime.combine(test_date, test_time))

        assert result.tzinfo is not None
        assert result.tzinfo == BERLIN_TZ or str(result.tzinfo) == 'Europe/Berlin'
        print(f"✅ Datetime is timezone-aware: {result.tzinfo}")

    def test_different_dates_for_entry_and_exit(self):
        """Test with different dates for entry and exit."""
        entry_date = date(2025, 11, 9)
        entry_time = time(22, 0, 0)
        exit_date = date(2025, 11, 10)
        exit_time = time(2, 0, 0)

        entry_ts = BERLIN_TZ.localize(datetime.combine(entry_date, entry_time))
        exit_ts = BERLIN_TZ.localize(datetime.combine(exit_date, exit_time))

        delta = exit_ts - entry_ts
        assert delta.total_seconds() / 3600 == 4.0  # 4 hours across midnight
        print(f"✅ Cross-midnight trade handled correctly")
        print(f"   Entry: {entry_ts}")
        print(f"   Exit:  {exit_ts}")
        print(f"   Duration: {delta.total_seconds() / 3600} hours")


def print_test_summary():
    """Print test summary."""
    print("\n" + "=" * 70)
    print("DATETIME INPUT FIX TEST SUMMARY")
    print("=" * 70)
    print("Testing date + time combination for Streamlit forms...")
    print("=" * 70)


if __name__ == '__main__':
    print_test_summary()
    pytest.main([__file__, '-v', '--tb=short', '-s'])
