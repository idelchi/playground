"""
Test for the NaT (Not a Time) bug fix.
Tests that open positions with None/NaT exit timestamps are handled correctly.
"""

import pytest
import pandas as pd
from datetime import datetime
import pytz

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    localize_datetime,
    to_utc,
    compute_derived_fields,
    get_all_trades,
    add_trade,
    BERLIN_TZ,
)


class TestNaTHandling:
    """Tests for handling pandas NaT (Not a Time) values."""

    def test_localize_datetime_with_nat(self):
        """Test that localize_datetime handles pandas NaT correctly."""
        nat_value = pd.NaT
        result = localize_datetime(nat_value)
        assert result is None
        print("✅ localize_datetime handles pd.NaT correctly")

    def test_localize_datetime_with_none(self):
        """Test that localize_datetime handles None correctly."""
        result = localize_datetime(None)
        assert result is None
        print("✅ localize_datetime handles None correctly")

    def test_to_utc_with_nat(self):
        """Test that to_utc handles pandas NaT correctly."""
        nat_value = pd.NaT
        result = to_utc(nat_value)
        assert result is None
        print("✅ to_utc handles pd.NaT correctly")

    def test_to_utc_with_none(self):
        """Test that to_utc handles None correctly."""
        result = to_utc(None)
        assert result is None
        print("✅ to_utc handles None correctly")

    def test_open_position_with_nat(self):
        """Test compute_derived_fields with NaT exit timestamp."""
        trade_data = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': pd.NaT,  # Open position
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }

        result = compute_derived_fields(trade_data)

        # Should handle NaT gracefully
        assert result['quantity'] is not None
        assert result['gross_pnl_usd'] is None
        assert result['net_pnl_usd'] is None
        assert result['win_loss'] is None
        # holding_period_hours may be None or NaN for NaT
        assert result['holding_period_hours'] is None or pd.isna(result['holding_period_hours'])
        print("✅ compute_derived_fields handles NaT exit timestamp correctly")

    def test_dataframe_with_nat_exit_timestamps(self):
        """Test that a DataFrame with NaT values can be processed."""
        # Create a DataFrame with mixed None and valid timestamps
        data = {
            'id': [1, 2, 3],
            'entry_ts': [
                datetime(2025, 11, 9, 14, 0, 0),
                datetime(2025, 11, 9, 15, 0, 0),
                datetime(2025, 11, 9, 16, 0, 0),
            ],
            'exit_ts': [
                datetime(2025, 11, 9, 18, 0, 0),  # Closed trade
                None,  # Open trade
                pd.NaT,  # Open trade with NaT
            ],
        }

        df = pd.DataFrame(data)
        df['entry_ts'] = pd.to_datetime(df['entry_ts'])
        df['exit_ts'] = pd.to_datetime(df['exit_ts'])

        # Apply localize_datetime to all rows
        df['entry_ts_berlin'] = df['entry_ts'].apply(localize_datetime)
        df['exit_ts_berlin'] = df['exit_ts'].apply(localize_datetime)

        # Check results
        assert df['entry_ts_berlin'].iloc[0] is not None
        assert df['entry_ts_berlin'].iloc[1] is not None
        assert df['entry_ts_berlin'].iloc[2] is not None

        assert df['exit_ts_berlin'].iloc[0] is not None  # Closed trade has exit
        # Open trades should have None or NaT (pandas may keep NaT in Series)
        assert df['exit_ts_berlin'].iloc[1] is None or pd.isna(df['exit_ts_berlin'].iloc[1])
        assert df['exit_ts_berlin'].iloc[2] is None or pd.isna(df['exit_ts_berlin'].iloc[2])

        print("✅ DataFrame with NaT values processed correctly")

    def test_add_open_trade_to_database(self):
        """Test adding an open position to the database."""
        trade_data = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': None,  # Open position
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'exchange': 'Binance',
            'setup_strategy': 'Breakout',
            'market_context': '',
            'entry_rationale': '',
            'trigger_confirmation': '',
            'execution_notes': '',
            'emotional_state': '',
            'strategy_tags': '',
            'market_tags': '',
            'mistake_tag': '',
            'screenshot_entry_url': '',
            'screenshot_exit_url': '',
            'system_compliance': 5,
            'confidence': 4,
        }

        # This should not raise an error
        success, message = add_trade(trade_data)
        assert success, f"Failed to add open trade: {message}"
        print(f"✅ Open position added to database: {message}")

    def test_retrieve_trades_with_open_positions(self):
        """Test retrieving trades when some positions are open."""
        # Add a closed trade
        closed_trade = {
            'entry_ts': datetime(2025, 11, 9, 14, 0, 0, tzinfo=BERLIN_TZ),
            'exit_ts': datetime(2025, 11, 9, 18, 0, 0, tzinfo=BERLIN_TZ),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'fees_usd': 2.0,
            'funding_usd': 0.5,
            'exchange': 'Binance',
            'setup_strategy': 'Breakout',
            'market_context': '',
            'entry_rationale': '',
            'trigger_confirmation': '',
            'execution_notes': '',
            'emotional_state': '',
            'strategy_tags': '',
            'market_tags': '',
            'mistake_tag': '',
            'screenshot_entry_url': '',
            'screenshot_exit_url': '',
            'system_compliance': 5,
            'confidence': 4,
        }

        # Add an open trade
        open_trade = closed_trade.copy()
        open_trade['exit_ts'] = None
        open_trade['exit_price'] = None

        add_trade(closed_trade)
        add_trade(open_trade)

        # Retrieve all trades - this should not raise an error
        df = get_all_trades()

        assert len(df) >= 2, "Should have at least 2 trades"
        print(f"✅ Retrieved {len(df)} trades including open positions without errors")

        # Check that open positions have None for exit_ts
        open_positions = df[df['exit_ts'].isna()]
        assert len(open_positions) >= 1, "Should have at least one open position"
        print(f"✅ Found {len(open_positions)} open position(s) with NaT exit_ts")


def print_test_summary():
    """Print a summary of NaT handling tests."""
    print("\n" + "=" * 70)
    print("NaT (NOT A TIME) HANDLING TEST SUMMARY")
    print("=" * 70)
    print("Testing pandas NaT value handling for open positions...")
    print("=" * 70)


if __name__ == '__main__':
    print_test_summary()
    pytest.main([__file__, '-v', '--tb=short', '-s'])
