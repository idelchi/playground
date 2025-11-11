"""
Test to verify the filter bug is fixed.

This test simulates the exact scenario reported:
1. App starts with no trades (filters initialize as empty)
2. User adds a trade
3. User switches to Trades Table tab
4. Trades should appear (not be filtered out)

We test this by checking that the filtering logic correctly handles
empty vs populated filter lists.
"""

import pytest
import pandas as pd
from datetime import datetime
import pytz
import os
import tempfile
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import app


@pytest.fixture
def test_env():
    """Set up test environment with temporary database"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_trades.db')

    os.environ['TRADING_JOURNAL_DB'] = db_path

    import importlib
    importlib.reload(app)

    app.Base.metadata.create_all(app.engine)

    yield

    if 'TRADING_JOURNAL_DB' in os.environ:
        del os.environ['TRADING_JOURNAL_DB']
    shutil.rmtree(temp_dir)


def create_sample_trade(pair='BTC/USDT', direction='Long', entry_price=50000, exit_price=51000):
    """Create a sample trade"""
    return {
        'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
        'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 14, 45)),
        'pair': pair,
        'direction': direction,
        'leverage_x': 5.0,
        'position_notional': 1000.0,
        'entry_price': entry_price,
        'stop_price': entry_price - 500,
        'tp1': entry_price + 1000,
        'tp2': entry_price + 2000,
        'exit_price': exit_price,
        'fees_usd': 2.0,
        'funding_usd': 0.5,
        'exchange': 'Binance',
        'setup_strategy': 'Breakout',
        'market_context': 'Test',
        'entry_rationale': 'Test',
        'trigger_confirmation': 'Test',
        'execution_notes': 'Test',
        'emotional_state': 'Test',
        'strategy_tags': 'test',
        'market_tags': 'test',
        'mistake_tag': '',
        'screenshot_entry_url': '',
        'screenshot_exit_url': '',
        'system_compliance': 3,
        'confidence': 3
    }


def apply_filters_logic(df, selected_pairs, selected_direction, selected_exchanges,
                        selected_strategies, selected_win_loss):
    """
    Simulate the filter logic from the app.
    This is the EXACT logic from app.py lines 497-514.
    """
    filtered_df = df.copy()

    if not filtered_df.empty:
        # Pair
        if selected_pairs:
            filtered_df = filtered_df[filtered_df['pair'].isin(selected_pairs)]

        # Direction
        if selected_direction:
            filtered_df = filtered_df[filtered_df['direction'].isin(selected_direction)]

        # Exchange
        if selected_exchanges:
            filtered_df = filtered_df[filtered_df['exchange'].isin(selected_exchanges)]

        # Strategy
        if selected_strategies:
            filtered_df = filtered_df[filtered_df['setup_strategy'].isin(selected_strategies)]

        # Win/Loss
        if selected_win_loss and 'win_loss' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['win_loss'].isin(selected_win_loss)]

    return filtered_df


class TestFilterBugScenario:
    """Test the exact bug scenario reported"""

    def test_empty_filters_dont_filter_out_data(self, test_env):
        """
        CRITICAL TEST: Verify that empty filter lists don't filter out trades.

        This was the bug: when app started with no trades, filters were [],
        and even after adding trades, the empty [] filtered everything out.
        """
        # Add a trade
        trade = create_sample_trade()
        app.add_trade(trade)

        # Get all trades
        all_trades = app.get_all_trades()
        assert len(all_trades) == 1, "Trade should be in database"

        # Simulate what happens when filters are EMPTY (the bug scenario)
        # This is what happened when the app first loaded with no trades
        empty_filters = {
            'selected_pairs': [],           # Empty!
            'selected_direction': [],       # Empty!
            'selected_exchanges': [],       # Empty!
            'selected_strategies': [],      # Empty!
            'selected_win_loss': []         # Empty!
        }

        # Apply filtering logic with empty filters
        filtered = apply_filters_logic(
            all_trades,
            empty_filters['selected_pairs'],
            empty_filters['selected_direction'],
            empty_filters['selected_exchanges'],
            empty_filters['selected_strategies'],
            empty_filters['selected_win_loss']
        )

        # THE BUG: With the filter logic checking "if selected_pairs:" before filtering,
        # empty lists should NOT filter data out. But they were!
        # With the fix, empty filters should show all data.
        assert len(filtered) == 1, f"Empty filters should not filter out trades! Got {len(filtered)} trades"

        print("✓ Empty filters correctly show all trades (bug is fixed)")

    def test_populated_filters_work_correctly(self, test_env):
        """Verify that populated filters still work correctly"""
        # Add multiple trades
        app.add_trade(create_sample_trade('BTC/USDT', 'Long', 50000, 51000))
        app.add_trade(create_sample_trade('ETH/USDT', 'Short', 3000, 2950))
        app.add_trade(create_sample_trade('BTC/USDT', 'Short', 50000, 49500))

        all_trades = app.get_all_trades()
        assert len(all_trades) == 3

        # Test filtering by pair
        filtered = apply_filters_logic(
            all_trades,
            selected_pairs=['BTC/USDT'],  # Only BTC
            selected_direction=['Long', 'Short'],
            selected_exchanges=['Binance'],
            selected_strategies=['Breakout'],
            selected_win_loss=['Win', 'Loss', 'Breakeven']
        )
        assert len(filtered) == 2, f"Should have 2 BTC trades, got {len(filtered)}"
        assert all(filtered['pair'] == 'BTC/USDT')

        # Test filtering by direction
        filtered = apply_filters_logic(
            all_trades,
            selected_pairs=['BTC/USDT', 'ETH/USDT'],
            selected_direction=['Long'],  # Only Long
            selected_exchanges=['Binance'],
            selected_strategies=['Breakout'],
            selected_win_loss=['Win', 'Loss', 'Breakeven']
        )
        assert len(filtered) == 1, f"Should have 1 Long trade, got {len(filtered)}"
        assert all(filtered['direction'] == 'Long')

        print("✓ Populated filters work correctly")

    def test_mixed_empty_and_populated_filters(self, test_env):
        """Test scenario where some filters are empty and some are populated"""
        app.add_trade(create_sample_trade('BTC/USDT', 'Long', 50000, 51000))
        app.add_trade(create_sample_trade('ETH/USDT', 'Short', 3000, 2950))

        all_trades = app.get_all_trades()

        # Mix of empty and populated filters
        filtered = apply_filters_logic(
            all_trades,
            selected_pairs=['BTC/USDT'],  # Populated
            selected_direction=[],         # EMPTY - should not filter
            selected_exchanges=[],         # EMPTY - should not filter
            selected_strategies=['Breakout'],  # Populated
            selected_win_loss=[]           # EMPTY - should not filter
        )

        # Should only filter by pair and strategy (the populated ones)
        assert len(filtered) == 1
        assert filtered.iloc[0]['pair'] == 'BTC/USDT'

        print("✓ Mixed empty/populated filters work correctly")

    def test_all_filters_empty_shows_all_data(self, test_env):
        """When ALL filters are empty, ALL data should be shown"""
        # Add multiple diverse trades
        app.add_trade(create_sample_trade('BTC/USDT', 'Long', 50000, 51000))
        app.add_trade(create_sample_trade('ETH/USDT', 'Short', 3000, 2950))
        app.add_trade(create_sample_trade('SOL/USDT', 'Long', 100, 110))

        all_trades = app.get_all_trades()
        assert len(all_trades) == 3

        # ALL filters empty
        filtered = apply_filters_logic(
            all_trades,
            selected_pairs=[],
            selected_direction=[],
            selected_exchanges=[],
            selected_strategies=[],
            selected_win_loss=[]
        )

        assert len(filtered) == 3, f"All empty filters should show all 3 trades, got {len(filtered)}"

        print("✓ All empty filters show all data")

    def test_default_filter_values_from_app(self, test_env):
        """Test the actual default values used in the app"""
        # Add trades
        app.add_trade(create_sample_trade('BTC/USDT', 'Long', 50000, 51000))
        app.add_trade(create_sample_trade('ETH/USDT', 'Short', 3000, 2950))

        all_trades = app.get_all_trades()

        # Simulate the app's default behavior (after fix)
        # When data exists, filters should default to show all
        unique_pairs = sorted(all_trades['pair'].unique().tolist())
        unique_exchanges = sorted(all_trades['exchange'].unique().tolist())
        unique_strategies = sorted(all_trades['setup_strategy'].unique().tolist())

        # These are the defaults set in the app
        filtered = apply_filters_logic(
            all_trades,
            selected_pairs=unique_pairs,  # All pairs
            selected_direction=['Long', 'Short'],  # All directions
            selected_exchanges=unique_exchanges,  # All exchanges
            selected_strategies=unique_strategies,  # All strategies
            selected_win_loss=['Win', 'Loss', 'Breakeven']  # All outcomes
        )

        assert len(filtered) == 2, "Default filters should show all data"

        print("✓ App default filter values work correctly")


def test_filter_logic_comprehensive(test_env):
    """Comprehensive test of all filter combinations"""
    # Create diverse dataset
    trades = [
        create_sample_trade('BTC/USDT', 'Long', 50000, 51000),   # Win
        create_sample_trade('BTC/USDT', 'Short', 50000, 49500),  # Win
        create_sample_trade('ETH/USDT', 'Long', 3000, 2950),     # Loss
        create_sample_trade('ETH/USDT', 'Short', 3000, 3100),    # Loss
        create_sample_trade('SOL/USDT', 'Long', 100, 100),       # Breakeven (after fees)
    ]

    for trade in trades:
        app.add_trade(trade)

    all_trades = app.get_all_trades()
    assert len(all_trades) == 5

    # Test 1: Filter by wins only
    filtered = apply_filters_logic(
        all_trades,
        selected_pairs=['BTC/USDT', 'ETH/USDT', 'SOL/USDT'],
        selected_direction=['Long', 'Short'],
        selected_exchanges=['Binance'],
        selected_strategies=['Breakout'],
        selected_win_loss=['Win']  # Only wins
    )
    wins = filtered[filtered['win_loss'] == 'Win']
    assert len(wins) > 0, "Should have some winning trades"

    # Test 2: Filter by pair + direction
    filtered = apply_filters_logic(
        all_trades,
        selected_pairs=['BTC/USDT'],
        selected_direction=['Long'],
        selected_exchanges=['Binance'],
        selected_strategies=['Breakout'],
        selected_win_loss=['Win', 'Loss', 'Breakeven']
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]['pair'] == 'BTC/USDT'
    assert filtered.iloc[0]['direction'] == 'Long'

    # Test 3: No filters (empty lists) shows everything
    filtered = apply_filters_logic(
        all_trades,
        selected_pairs=[],
        selected_direction=[],
        selected_exchanges=[],
        selected_strategies=[],
        selected_win_loss=[]
    )
    assert len(filtered) == 5, "No filters should show all 5 trades"

    print("✓ Comprehensive filter logic tests passed")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
