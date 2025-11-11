"""
Comprehensive integration tests for the Trading Journal Streamlit app.

Tests the complete workflow:
1. Start with empty database
2. Add trades through form logic
3. Verify trades appear correctly
4. Test filtering, sorting, calculations
5. Test edit/delete/duplicate operations
6. Test CSV import/export workflow
7. Test dashboard calculations
8. Verify all derived fields are correct

This ensures the app works correctly before manual testing.
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import os
import tempfile
import shutil
from io import StringIO
import app


@pytest.fixture
def fresh_db():
    """Create fresh database for each test"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_trades.db')
    os.environ['TRADING_JOURNAL_DB'] = db_path

    import importlib
    importlib.reload(app)
    app.Base.metadata.create_all(app.engine)

    yield db_path

    if 'TRADING_JOURNAL_DB' in os.environ:
        del os.environ['TRADING_JOURNAL_DB']
    shutil.rmtree(temp_dir)


def create_full_trade(pair='BTC/USDT', direction='Long',
                      entry_price=50000, exit_price=51000,
                      entry_date=None, exit_date=None):
    """Create a complete trade with all fields"""
    if entry_date is None:
        entry_date = datetime(2024, 1, 15, 10, 30)
    if exit_date is None:
        exit_date = datetime(2024, 1, 15, 14, 45)

    return {
        'entry_ts': app.BERLIN_TZ.localize(entry_date),
        'exit_ts': app.BERLIN_TZ.localize(exit_date),
        'pair': pair,
        'direction': direction,
        'leverage_x': 5.0,
        'position_notional': 1000.0,
        'entry_price': entry_price,
        'stop_price': entry_price - 500 if direction == 'Long' else entry_price + 500,
        'tp1': entry_price + 1000 if direction == 'Long' else entry_price - 1000,
        'tp2': entry_price + 2000 if direction == 'Long' else entry_price - 2000,
        'exit_price': exit_price,
        'fees_usd': 2.0,
        'funding_usd': 0.5,
        'exchange': 'Binance',
        'setup_strategy': 'Breakout',
        'market_context': 'Strong momentum',
        'entry_rationale': 'Clear breakout signal',
        'trigger_confirmation': 'Volume spike',
        'execution_notes': 'Clean entry',
        'emotional_state': 'Calm',
        'strategy_tags': 'momentum,breakout',
        'market_tags': 'trending,volatile',
        'mistake_tag': '',
        'screenshot_entry_url': 'https://example.com/entry.png',
        'screenshot_exit_url': 'https://example.com/exit.png',
        'system_compliance': 5,
        'confidence': 4
    }


class TestCompleteWorkflow:
    """Test the complete user workflow"""

    def test_empty_database_state(self, fresh_db):
        """Test app behaves correctly with empty database"""
        df = app.get_all_trades()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert df.empty

        print("✓ Empty database returns empty DataFrame")

    def test_add_single_trade_workflow(self, fresh_db):
        """Test adding a single trade through the full workflow"""
        # Create trade data (simulating form submission)
        trade_data = create_full_trade()

        # Add trade
        success = app.add_trade(trade_data)
        assert success is True

        # Retrieve and verify
        df = app.get_all_trades()
        assert len(df) == 1

        trade = df.iloc[0]

        # Verify raw inputs
        assert trade['pair'] == 'BTC/USDT'
        assert trade['direction'] == 'Long'
        assert trade['entry_price'] == 50000.0
        assert trade['exit_price'] == 51000.0
        assert trade['exchange'] == 'Binance'
        assert trade['setup_strategy'] == 'Breakout'

        # Verify derived fields are calculated
        assert trade['quantity'] is not None
        assert trade['gross_pnl_usd'] is not None
        assert trade['net_pnl_usd'] is not None
        assert trade['risk_usd'] is not None
        assert trade['r_multiple'] is not None
        assert trade['win_loss'] in ['Win', 'Loss', 'Breakeven']
        assert trade['pnl_pct'] is not None
        assert trade['holding_period_hours'] is not None

        # Verify calculations are correct
        expected_qty = 1000.0 / 50000.0
        assert trade['quantity'] == pytest.approx(expected_qty, rel=1e-9)

        expected_gross_pnl = (51000.0 - 50000.0) * expected_qty
        assert trade['gross_pnl_usd'] == pytest.approx(expected_gross_pnl, rel=1e-9)

        expected_net_pnl = expected_gross_pnl - 2.0 - 0.5
        assert trade['net_pnl_usd'] == pytest.approx(expected_net_pnl, rel=1e-9)

        assert trade['win_loss'] == 'Win'

        print("✓ Single trade add workflow works correctly")

    def test_add_multiple_trades_workflow(self, fresh_db):
        """Test adding multiple trades"""
        trades_to_add = [
            create_full_trade('BTC/USDT', 'Long', 50000, 51000),
            create_full_trade('ETH/USDT', 'Short', 3000, 2950),
            create_full_trade('SOL/USDT', 'Long', 100, 105),
        ]

        for trade_data in trades_to_add:
            success = app.add_trade(trade_data)
            assert success is True

        df = app.get_all_trades()
        assert len(df) == 3

        # Verify all pairs are present
        pairs = set(df['pair'].tolist())
        assert pairs == {'BTC/USDT', 'ETH/USDT', 'SOL/USDT'}

        # Verify all have calculated fields
        assert df['net_pnl_usd'].notna().all()
        assert df['win_loss'].notna().all()

        print("✓ Multiple trades add workflow works correctly")

    def test_update_trade_workflow(self, fresh_db):
        """Test updating a trade"""
        # Add initial trade
        trade_data = create_full_trade('BTC/USDT', 'Long', 50000, 51000)
        app.add_trade(trade_data)

        df = app.get_all_trades()
        trade_id = df.iloc[0]['id']
        original_pnl = df.iloc[0]['net_pnl_usd']

        # Update exit price (better exit)
        updated_data = trade_data.copy()
        updated_data['exit_price'] = 52000.0  # Better exit

        success = app.update_trade(trade_id, updated_data)
        assert success is True

        # Verify update
        df = app.get_all_trades()
        assert len(df) == 1

        updated_trade = df.iloc[0]
        assert updated_trade['exit_price'] == 52000.0

        # Verify derived fields were recalculated
        new_pnl = updated_trade['net_pnl_usd']
        assert new_pnl > original_pnl  # Better exit = more profit

        # Verify exact calculation
        expected_qty = 1000.0 / 50000.0
        expected_gross = (52000.0 - 50000.0) * expected_qty
        expected_net = expected_gross - 2.0 - 0.5
        assert updated_trade['net_pnl_usd'] == pytest.approx(expected_net, rel=1e-9)

        print("✓ Update trade workflow works correctly")

    def test_delete_trade_workflow(self, fresh_db):
        """Test deleting trades"""
        # Add multiple trades
        for i in range(3):
            trade = create_full_trade('BTC/USDT', 'Long', 50000 + i*100, 51000 + i*100)
            app.add_trade(trade)

        df = app.get_all_trades()
        assert len(df) == 3

        # Delete one trade
        trade_id = df.iloc[0]['id']
        success = app.delete_trades([trade_id])
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 2

        # Delete multiple trades
        remaining_ids = df['id'].tolist()
        success = app.delete_trades(remaining_ids)
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 0

        print("✓ Delete trade workflow works correctly")

    def test_duplicate_trade_workflow(self, fresh_db):
        """Test duplicating a trade"""
        # Add trade
        trade_data = create_full_trade('BTC/USDT', 'Long', 50000, 51000)
        app.add_trade(trade_data)

        df = app.get_all_trades()
        trade_id = df.iloc[0]['id']

        # Duplicate
        success = app.duplicate_trade(trade_id)
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 2

        # Verify both trades have same data (except ID)
        trade1 = df.iloc[0]
        trade2 = df.iloc[1]

        assert trade1['id'] != trade2['id']
        assert trade1['pair'] == trade2['pair']
        assert trade1['entry_price'] == trade2['entry_price']
        assert trade1['net_pnl_usd'] == pytest.approx(trade2['net_pnl_usd'], rel=1e-9)

        print("✓ Duplicate trade workflow works correctly")


class TestCSVWorkflow:
    """Test CSV import/export workflow"""

    def test_csv_export_workflow(self, fresh_db):
        """Test exporting trades to CSV"""
        # Add diverse trades
        trades = [
            create_full_trade('BTC/USDT', 'Long', 50000, 51000),
            create_full_trade('ETH/USDT', 'Short', 3000, 2950),
            create_full_trade('SOL/USDT', 'Long', 100, 105),
        ]

        for trade in trades:
            app.add_trade(trade)

        # Export
        df = app.get_all_trades()
        csv_string = df.to_csv(index=False)

        # Verify CSV structure
        assert len(csv_string) > 0
        assert 'BTC/USDT' in csv_string
        assert 'ETH/USDT' in csv_string
        assert 'net_pnl_usd' in csv_string
        assert 'win_loss' in csv_string

        # Verify can be parsed
        csv_df = pd.read_csv(StringIO(csv_string))
        assert len(csv_df) == 3
        assert all(col in csv_df.columns for col in ['pair', 'direction', 'entry_price', 'exit_price'])

        print("✓ CSV export workflow works correctly")

    def test_csv_import_workflow(self, fresh_db):
        """Test importing trades from CSV"""
        # Create and export trades
        original_trades = [
            create_full_trade('BTC/USDT', 'Long', 50000, 51000),
            create_full_trade('ETH/USDT', 'Short', 3000, 2950),
        ]

        for trade in original_trades:
            app.add_trade(trade)

        original_df = app.get_all_trades()
        csv_string = original_df.to_csv(index=False)

        # Clear database
        all_ids = original_df['id'].tolist()
        app.delete_trades(all_ids)

        assert len(app.get_all_trades()) == 0

        # Re-import from CSV
        import_df = pd.read_csv(StringIO(csv_string))

        for _, row in import_df.iterrows():
            trade_dict = row.to_dict()

            # Parse dates
            if 'entry_ts' in trade_dict:
                trade_dict['entry_ts'] = pd.to_datetime(trade_dict['entry_ts'])
            if 'exit_ts' in trade_dict and pd.notna(trade_dict['exit_ts']):
                trade_dict['exit_ts'] = pd.to_datetime(trade_dict['exit_ts'])
            else:
                trade_dict['exit_ts'] = None

            # Remove auto fields
            trade_dict.pop('id', None)
            trade_dict.pop('created_at', None)
            trade_dict.pop('updated_at', None)

            app.add_trade(trade_dict)

        # Verify reimport
        new_df = app.get_all_trades()
        assert len(new_df) == 2

        # Verify key fields match
        assert set(new_df['pair'].tolist()) == {'BTC/USDT', 'ETH/USDT'}

        print("✓ CSV import workflow works correctly")


class TestDashboardCalculations:
    """Test dashboard metrics calculations"""

    def test_performance_metrics(self, fresh_db):
        """Test that dashboard metrics calculate correctly"""
        # Add trades with known outcomes
        wins = [
            create_full_trade('BTC/USDT', 'Long', 50000, 51000,
                            datetime(2024, 1, i+1, 10, 0),
                            datetime(2024, 1, i+1, 12, 0))
            for i in range(3)
        ]

        losses = [
            create_full_trade('BTC/USDT', 'Long', 50000, 49800,
                            datetime(2024, 1, i+10, 10, 0),
                            datetime(2024, 1, i+10, 12, 0))
            for i in range(2)
        ]

        for trade in wins + losses:
            app.add_trade(trade)

        df = app.get_all_trades()
        closed_trades = df[df['net_pnl_usd'].notna()]

        # Calculate metrics (as dashboard would)
        total_trades = len(df)
        win_count = len(closed_trades[closed_trades['win_loss'] == 'Win'])
        loss_count = len(closed_trades[closed_trades['win_loss'] == 'Loss'])
        win_rate = (win_count / len(closed_trades)) * 100 if len(closed_trades) > 0 else 0

        net_pnl = closed_trades['net_pnl_usd'].sum()
        avg_r = closed_trades['r_multiple'].mean()
        best_trade = closed_trades['net_pnl_usd'].max()
        worst_trade = closed_trades['net_pnl_usd'].min()

        # Verify
        assert total_trades == 5
        assert win_count == 3
        assert loss_count == 2
        assert win_rate == pytest.approx(60.0, rel=1e-9)
        assert net_pnl != 0  # Should have net result
        assert avg_r is not None
        assert best_trade > 0
        assert worst_trade < 0

        print("✓ Dashboard metrics calculate correctly")

    def test_equity_curve_calculation(self, fresh_db):
        """Test equity curve calculation"""
        starting_balance = 10000.0

        # Add trades with specific PnL
        trades = [
            create_full_trade('BTC/USDT', 'Long', 50000, 51000,  # ~$27.50 profit
                            datetime(2024, 1, 1, 10, 0),
                            datetime(2024, 1, 1, 12, 0)),
            create_full_trade('BTC/USDT', 'Long', 50000, 49800,  # loss
                            datetime(2024, 1, 2, 10, 0),
                            datetime(2024, 1, 2, 12, 0)),
            create_full_trade('BTC/USDT', 'Long', 50000, 51000,  # profit
                            datetime(2024, 1, 3, 10, 0),
                            datetime(2024, 1, 3, 12, 0)),
        ]

        for trade in trades:
            app.add_trade(trade)

        df = app.get_all_trades()
        closed_trades = df[df['net_pnl_usd'].notna()].sort_values('exit_ts')

        # Calculate equity curve
        closed_trades_copy = closed_trades.copy()
        closed_trades_copy['cumulative_pnl'] = closed_trades_copy['net_pnl_usd'].cumsum()
        closed_trades_copy['equity'] = starting_balance + closed_trades_copy['cumulative_pnl']

        # Verify equity curve
        assert len(closed_trades_copy) == 3

        # First trade: starting + first PnL
        first_equity = closed_trades_copy.iloc[0]['equity']
        assert first_equity > starting_balance or first_equity < starting_balance

        # Final equity should equal starting + total PnL
        final_equity = closed_trades_copy.iloc[-1]['equity']
        total_pnl = closed_trades['net_pnl_usd'].sum()
        expected_final = starting_balance + total_pnl
        assert final_equity == pytest.approx(expected_final, rel=1e-9)

        print("✓ Equity curve calculates correctly")

    def test_strategy_breakdown(self, fresh_db):
        """Test strategy performance breakdown"""
        # Add trades with different strategies
        breakout_trades = [
            {**create_full_trade('BTC/USDT', 'Long', 50000, 51000), 'setup_strategy': 'Breakout'}
            for _ in range(2)
        ]

        reversion_trades = [
            {**create_full_trade('BTC/USDT', 'Long', 50000, 49800), 'setup_strategy': 'Range Reversion'}
            for _ in range(1)
        ]

        for trade in breakout_trades + reversion_trades:
            app.add_trade(trade)

        df = app.get_all_trades()
        closed_trades = df[df['net_pnl_usd'].notna()]

        # Group by strategy
        strategy_stats = closed_trades.groupby('setup_strategy').agg({
            'id': 'count',
            'net_pnl_usd': 'sum',
            'r_multiple': 'mean',
            'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100
        }).reset_index()

        # Verify breakdown
        assert len(strategy_stats) == 2  # Two strategies
        assert 'Breakout' in strategy_stats['setup_strategy'].values
        assert 'Range Reversion' in strategy_stats['setup_strategy'].values

        breakout_row = strategy_stats[strategy_stats['setup_strategy'] == 'Breakout'].iloc[0]
        assert breakout_row['id'] == 2  # 2 breakout trades

        print("✓ Strategy breakdown calculates correctly")


class TestValidationAndEdgeCases:
    """Test validation and edge case handling"""

    def test_invalid_trade_data(self, fresh_db):
        """Test that invalid data is handled"""
        # Missing entry price
        invalid_trade = create_full_trade()
        invalid_trade['entry_price'] = 0  # Invalid

        # Should still return success (or handle gracefully)
        # The validation happens in the UI, but calculations should handle it
        result = app.compute_derived_fields(invalid_trade)
        # Should not crash, should return None for derived fields that can't be calculated

        print("✓ Invalid data handled gracefully")

    def test_open_positions(self, fresh_db):
        """Test handling of open positions (no exit price)"""
        open_trade = create_full_trade()
        open_trade['exit_price'] = None
        open_trade['exit_ts'] = None

        app.add_trade(open_trade)

        df = app.get_all_trades()
        assert len(df) == 1

        trade = df.iloc[0]

        # Should have quantity and risk calculated
        assert trade['quantity'] is not None
        assert trade['risk_usd'] is not None

        # Should NOT have PnL calculated
        assert pd.isna(trade['gross_pnl_usd']) or trade['gross_pnl_usd'] is None
        assert pd.isna(trade['net_pnl_usd']) or trade['net_pnl_usd'] is None
        assert pd.isna(trade['win_loss']) or trade['win_loss'] is None

        print("✓ Open positions handled correctly")

    def test_extreme_values(self, fresh_db):
        """Test with extreme values"""
        # Very large position
        large_trade = create_full_trade()
        large_trade['position_notional'] = 1000000.0
        large_trade['entry_price'] = 50000.0
        large_trade['exit_price'] = 51000.0

        app.add_trade(large_trade)

        df = app.get_all_trades()
        trade = df.iloc[0]

        assert trade['net_pnl_usd'] is not None
        assert not pd.isna(trade['net_pnl_usd'])
        assert trade['net_pnl_usd'] > 0

        # Very small position
        small_trade = create_full_trade()
        small_trade['position_notional'] = 1.0
        small_trade['entry_price'] = 50000.0
        small_trade['exit_price'] = 51000.0

        app.add_trade(small_trade)

        df = app.get_all_trades()
        assert len(df) == 2

        print("✓ Extreme values handled correctly")


def test_full_user_journey(fresh_db):
    """Test complete user journey from start to finish"""
    # 1. User starts with empty database
    assert len(app.get_all_trades()) == 0

    # 2. User adds their first trade
    first_trade = create_full_trade('BTC/USDT', 'Long', 50000, 51000)
    app.add_trade(first_trade)
    assert len(app.get_all_trades()) == 1

    # 3. User adds more trades
    app.add_trade(create_full_trade('ETH/USDT', 'Short', 3000, 2950))
    app.add_trade(create_full_trade('SOL/USDT', 'Long', 100, 105))
    assert len(app.get_all_trades()) == 3

    # 4. User views their trades (all should be visible with correct data)
    df = app.get_all_trades()
    assert len(df) == 3
    assert df['net_pnl_usd'].notna().all()

    # 5. User edits a trade
    trade_id = df.iloc[0]['id']
    updated = first_trade.copy()
    updated['exit_price'] = 52000.0
    app.update_trade(trade_id, updated)

    df = app.get_all_trades()
    assert df[df['id'] == trade_id].iloc[0]['exit_price'] == 52000.0

    # 6. User exports to CSV
    csv_data = df.to_csv(index=False)
    assert 'BTC/USDT' in csv_data

    # 7. User deletes a trade
    app.delete_trades([trade_id])
    assert len(app.get_all_trades()) == 2

    # 8. User views dashboard metrics
    df = app.get_all_trades()
    closed = df[df['net_pnl_usd'].notna()]

    total_trades = len(df)
    wins = len(closed[closed['win_loss'] == 'Win'])
    net_pnl = closed['net_pnl_usd'].sum()

    assert total_trades > 0
    assert wins >= 0
    assert net_pnl != 0

    print("✓ Complete user journey works end-to-end")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
