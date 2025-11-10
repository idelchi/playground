"""
Specific tests for timezone handling in the application.
Verifies that Europe/Berlin timezone is handled correctly throughout the system.
"""

import pytest
from datetime import datetime
import pytz

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    BERLIN_TZ,
    to_utc,
    localize_datetime,
    compute_derived_fields,
)


class TestTimezoneHandling:
    """Comprehensive timezone handling tests."""

    def test_berlin_timezone_configured(self):
        """Verify Berlin timezone is correctly configured."""
        assert BERLIN_TZ.zone == 'Europe/Berlin'

    def test_summer_time_cest(self):
        """Test conversion during Central European Summer Time (CEST = UTC+2)."""
        # July 15, 2025 14:30 in Berlin (summer time, CEST)
        berlin_summer = BERLIN_TZ.localize(datetime(2025, 7, 15, 14, 30, 0))

        # Convert to UTC
        utc_time = to_utc(berlin_summer)

        # Should be 2 hours earlier (12:30 UTC)
        assert utc_time.hour == 12
        assert utc_time.minute == 30
        assert utc_time.tzinfo is None  # Should be naive UTC
        print(f"✅ Summer (CEST): Berlin 14:30 → UTC {utc_time.hour}:30 (correct: -2 hours)")

    def test_winter_time_cet(self):
        """Test conversion during Central European Time (CET = UTC+1)."""
        # January 15, 2025 14:30 in Berlin (winter time, CET)
        berlin_winter = BERLIN_TZ.localize(datetime(2025, 1, 15, 14, 30, 0))

        # Convert to UTC
        utc_time = to_utc(berlin_winter)

        # Should be 1 hour earlier (13:30 UTC)
        assert utc_time.hour == 13
        assert utc_time.minute == 30
        assert utc_time.tzinfo is None  # Should be naive UTC
        print(f"✅ Winter (CET): Berlin 14:30 → UTC {utc_time.hour}:30 (correct: -1 hour)")

    def test_localize_utc_to_berlin_summer(self):
        """Test converting UTC to Berlin during summer."""
        # 12:30 UTC should be 14:30 CEST in Berlin
        utc_time = datetime(2025, 7, 15, 12, 30, 0)
        berlin_time = localize_datetime(utc_time)

        assert berlin_time.hour == 14
        assert berlin_time.minute == 30
        print(f"✅ UTC 12:30 → Berlin {berlin_time.hour}:30 in summer (correct: +2 hours)")

    def test_localize_utc_to_berlin_winter(self):
        """Test converting UTC to Berlin during winter."""
        # 13:30 UTC should be 14:30 CET in Berlin
        utc_time = datetime(2025, 1, 15, 13, 30, 0)
        berlin_time = localize_datetime(utc_time)

        assert berlin_time.hour == 14
        assert berlin_time.minute == 30
        print(f"✅ UTC 13:30 → Berlin {berlin_time.hour}:30 in winter (correct: +1 hour)")

    def test_dst_transition_forward(self):
        """Test daylight saving time transition (spring forward)."""
        # In 2025, DST starts on March 30 at 2:00 AM (clocks move to 3:00 AM)
        # Before transition: CET (UTC+1)
        before_dst = BERLIN_TZ.localize(datetime(2025, 3, 29, 14, 0, 0))

        # After transition: CEST (UTC+2)
        after_dst = BERLIN_TZ.localize(datetime(2025, 3, 31, 14, 0, 0))

        utc_before = to_utc(before_dst)
        utc_after = to_utc(after_dst)

        # Before DST: 14:00 CET = 13:00 UTC
        assert utc_before.hour == 13

        # After DST: 14:00 CEST = 12:00 UTC
        assert utc_after.hour == 12

        print(f"✅ DST transition handled: Before={utc_before.hour}:00 UTC, After={utc_after.hour}:00 UTC")

    def test_dst_transition_backward(self):
        """Test daylight saving time transition (fall back)."""
        # In 2025, DST ends on October 26 at 3:00 AM (clocks move back to 2:00 AM)
        # Before transition: CEST (UTC+2)
        before_dst = BERLIN_TZ.localize(datetime(2025, 10, 25, 14, 0, 0))

        # After transition: CET (UTC+1)
        after_dst = BERLIN_TZ.localize(datetime(2025, 10, 27, 14, 0, 0))

        utc_before = to_utc(before_dst)
        utc_after = to_utc(after_dst)

        # Before DST end: 14:00 CEST = 12:00 UTC
        assert utc_before.hour == 12

        # After DST end: 14:00 CET = 13:00 UTC
        assert utc_after.hour == 13

        print(f"✅ DST fall back handled: Before={utc_before.hour}:00 UTC, After={utc_after.hour}:00 UTC")

    def test_midnight_crossing(self):
        """Test timezone conversion that crosses midnight."""
        # 23:30 in Berlin should handle midnight crossing correctly
        berlin_time = BERLIN_TZ.localize(datetime(2025, 7, 15, 23, 30, 0))
        utc_time = to_utc(berlin_time)

        # 23:30 CEST = 21:30 UTC (same day)
        assert utc_time.day == 15
        assert utc_time.hour == 21
        print(f"✅ Midnight crossing: Berlin 23:30 → UTC {utc_time.hour}:30 (same day)")

        # Early morning UTC crossing
        berlin_early = BERLIN_TZ.localize(datetime(2025, 7, 16, 1, 30, 0))
        utc_early = to_utc(berlin_early)

        # 01:30 CEST on 16th = 23:30 UTC on 15th
        assert utc_early.day == 15
        assert utc_early.hour == 23
        print(f"✅ Midnight crossing back: Berlin 01:30 (16th) → UTC {utc_early.hour}:30 (15th)")

    def test_holding_period_with_timezone(self):
        """Test that holding period calculation accounts for timezone."""
        # Trade entered at 14:00 Berlin, exited at 18:00 Berlin (4 hours)
        entry = BERLIN_TZ.localize(datetime(2025, 11, 9, 14, 0, 0))
        exit = BERLIN_TZ.localize(datetime(2025, 11, 9, 18, 0, 0))

        trade_data = {
            'entry_ts': entry,
            'exit_ts': exit,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'leverage_x': 5.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }

        result = compute_derived_fields(trade_data)

        # Should be exactly 4 hours
        assert abs(result['holding_period_hours'] - 4.0) < 0.01
        print(f"✅ Holding period: {result['holding_period_hours']:.2f} hours (expected: 4.00)")

    def test_overnight_holding_period(self):
        """Test holding period calculation for overnight trades."""
        # Enter Friday 22:00, exit Saturday 10:00 (12 hours across midnight)
        entry = BERLIN_TZ.localize(datetime(2025, 11, 7, 22, 0, 0))  # Friday
        exit = BERLIN_TZ.localize(datetime(2025, 11, 8, 10, 0, 0))   # Saturday

        trade_data = {
            'entry_ts': entry,
            'exit_ts': exit,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'leverage_x': 5.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }

        result = compute_derived_fields(trade_data)

        # Should be exactly 12 hours
        assert abs(result['holding_period_hours'] - 12.0) < 0.01
        print(f"✅ Overnight period: {result['holding_period_hours']:.2f} hours (expected: 12.00)")

    def test_multi_day_holding_period(self):
        """Test holding period for multi-day trades."""
        # Enter Monday 10:00, exit Thursday 14:00 (3 days + 4 hours = 76 hours)
        entry = BERLIN_TZ.localize(datetime(2025, 11, 10, 10, 0, 0))  # Monday
        exit = BERLIN_TZ.localize(datetime(2025, 11, 13, 14, 0, 0))   # Thursday

        trade_data = {
            'entry_ts': entry,
            'exit_ts': exit,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'leverage_x': 5.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }

        result = compute_derived_fields(trade_data)

        # Should be 76 hours (3 days * 24 + 4 hours)
        assert abs(result['holding_period_hours'] - 76.0) < 0.01
        print(f"✅ Multi-day period: {result['holding_period_hours']:.2f} hours (expected: 76.00)")

    def test_timezone_preserves_date_components(self):
        """Test that timezone conversion preserves date components correctly."""
        # Create a specific time in Berlin
        berlin_time = BERLIN_TZ.localize(datetime(2025, 11, 9, 15, 30, 45))

        # Convert to UTC and back
        utc_time = to_utc(berlin_time)
        back_to_berlin = localize_datetime(utc_time)

        # Verify all components match
        assert back_to_berlin.year == berlin_time.year
        assert back_to_berlin.month == berlin_time.month
        assert back_to_berlin.day == berlin_time.day
        assert back_to_berlin.hour == berlin_time.hour
        assert back_to_berlin.minute == berlin_time.minute
        assert back_to_berlin.second == berlin_time.second

        print(f"✅ Round-trip preserved: {berlin_time} → UTC → {back_to_berlin}")

    def test_none_timestamp_handling(self):
        """Test that None timestamps are handled gracefully."""
        assert to_utc(None) is None
        assert localize_datetime(None) is None
        print("✅ None timestamps handled gracefully")

    def test_string_timestamp_conversion(self):
        """Test that string timestamps are converted correctly."""
        # Test with ISO format string (treated as UTC, converted to Berlin)
        time_string = "2025-11-09 14:30:00"
        berlin_time = localize_datetime(time_string)

        assert berlin_time is not None
        # String is treated as UTC and converted to Berlin (+1 hour in winter)
        assert berlin_time.hour == 15
        print(f"✅ String timestamp converted: '{time_string}' (UTC) → {berlin_time} (Berlin)")


def print_timezone_summary():
    """Print a summary of timezone configuration."""
    print("\n" + "=" * 70)
    print("TIMEZONE CONFIGURATION SUMMARY")
    print("=" * 70)
    print(f"Configured Timezone: {BERLIN_TZ.zone}")
    print(f"Timezone Object: {BERLIN_TZ}")

    # Show example conversions
    example_berlin = BERLIN_TZ.localize(datetime(2025, 11, 9, 15, 30, 0))
    example_utc = to_utc(example_berlin)

    print(f"\nExample Conversion:")
    print(f"  Berlin (CET):  {example_berlin}")
    print(f"  UTC:           {example_utc}")
    print(f"  Offset:        -{(example_berlin.hour - example_utc.hour)} hour(s)")
    print("=" * 70)


if __name__ == '__main__':
    print_timezone_summary()
    pytest.main([__file__, '-v', '--tb=short'])
