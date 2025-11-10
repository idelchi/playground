"""
Comprehensive test suite for the Crypto Perpetuals Trading Journal
Tests all calculations, database operations, CSV handling, and UI functionality
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import os
import tempfile
import shutil
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import sys
import app

# We'll access these via app.function_name after the fixture reloads the module
# This is a workaround to avoid importing before the fixture sets the DB path


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def temp_db():
    """Create a temporary database for each test"""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_trades.db')

    # Set environment variable and reload app
    os.environ['TRADING_JOURNAL_DB'] = db_path

    # Reload the app module to pick up the new DB path
    import importlib
    importlib.reload(app)

    # Create tables in the new database
    app.Base.metadata.create_all(app.engine)

    yield db_path

    # Cleanup
    if 'TRADING_JOURNAL_DB' in os.environ:
        del os.environ['TRADING_JOURNAL_DB']
    try:
        shutil.rmtree(temp_dir)
    except:
        pass


@pytest.fixture
def sample_long_trade_data():
    """Sample data for a Long trade"""
    return {
        'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
        'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 14, 45)),
        'pair': 'BTC/USDT',
        'direction': 'Long',
        'leverage_x': 5.0,
        'position_notional': 1000.0,
        'entry_price': 50000.0,
        'stop_price': 49500.0,
        'tp1': 51000.0,
        'tp2': 52000.0,
        'exit_price': 51500.0,
        'fees_usd': 2.0,
        'funding_usd': 0.5,
        'exchange': 'Binance',
        'setup_strategy': 'Breakout',
        'market_context': 'Strong uptrend',
        'entry_rationale': 'Break above resistance',
        'trigger_confirmation': 'Volume spike',
        'execution_notes': 'Clean entry',
        'emotional_state': 'Calm and focused',
        'strategy_tags': 'momentum,breakout',
        'market_tags': 'bullish,high_volume',
        'mistake_tag': '',
        'screenshot_entry_url': 'https://example.com/entry.png',
        'screenshot_exit_url': 'https://example.com/exit.png',
        'system_compliance': 5,
        'confidence': 4
    }


@pytest.fixture
def sample_short_trade_data():
    """Sample data for a Short trade"""
    return {
        'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 16, 9, 0)),
        'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 16, 11, 30)),
        'pair': 'ETH/USDT',
        'direction': 'Short',
        'leverage_x': 3.0,
        'position_notional': 500.0,
        'entry_price': 3000.0,
        'stop_price': 3100.0,
        'tp1': 2900.0,
        'tp2': 2800.0,
        'exit_price': 2950.0,
        'fees_usd': 1.5,
        'funding_usd': -0.3,  # Negative funding (we receive)
        'exchange': 'Bybit',
        'setup_strategy': 'Range Reversion',
        'market_context': 'Overbought conditions',
        'entry_rationale': 'RSI divergence',
        'trigger_confirmation': 'Rejection at resistance',
        'execution_notes': 'Entered on pullback',
        'emotional_state': 'Confident',
        'strategy_tags': 'mean_reversion',
        'market_tags': 'overbought',
        'mistake_tag': '',
        'screenshot_entry_url': '',
        'screenshot_exit_url': '',
        'system_compliance': 4,
        'confidence': 5
    }


# ============================================================================
# CALCULATION TESTS
# ============================================================================

class TestCalculations:
    """Test all calculation functions for derived fields"""

    def test_long_trade_winning_calculations(self, sample_long_trade_data):
        """Test calculations for a winning long trade"""
        result = app.compute_derived_fields(sample_long_trade_data)

        # Quantity: position_notional / entry_price
        expected_quantity = 1000.0 / 50000.0
        assert result['quantity'] == pytest.approx(expected_quantity, rel=1e-9)
        assert result['quantity'] == pytest.approx(0.02, rel=1e-9)

        # Gross PnL for Long: (exit_price - entry_price) * quantity
        expected_gross_pnl = (51500.0 - 50000.0) * 0.02
        assert result['gross_pnl_usd'] == pytest.approx(expected_gross_pnl, rel=1e-9)
        assert result['gross_pnl_usd'] == pytest.approx(30.0, rel=1e-9)

        # Risk for Long: (entry_price - stop_price) * quantity
        expected_risk = (50000.0 - 49500.0) * 0.02
        assert result['risk_usd'] == pytest.approx(expected_risk, rel=1e-9)
        assert result['risk_usd'] == pytest.approx(10.0, rel=1e-9)

        # Net PnL: gross_pnl - fees - funding
        expected_net_pnl = 30.0 - 2.0 - 0.5
        assert result['net_pnl_usd'] == pytest.approx(expected_net_pnl, rel=1e-9)
        assert result['net_pnl_usd'] == pytest.approx(27.5, rel=1e-9)

        # PnL %: net_pnl / position_notional
        expected_pnl_pct = 27.5 / 1000.0
        assert result['pnl_pct'] == pytest.approx(expected_pnl_pct, rel=1e-9)
        assert result['pnl_pct'] == pytest.approx(0.0275, rel=1e-9)

        # R multiple: net_pnl / risk
        expected_r = 27.5 / 10.0
        assert result['r_multiple'] == pytest.approx(expected_r, rel=1e-9)
        assert result['r_multiple'] == pytest.approx(2.75, rel=1e-9)

        # Win/Loss
        assert result['win_loss'] == 'Win'

        # Holding period
        delta = sample_long_trade_data['exit_ts'] - sample_long_trade_data['entry_ts']
        expected_hours = delta.total_seconds() / 3600
        assert result['holding_period_hours'] == pytest.approx(expected_hours, rel=1e-9)
        assert result['holding_period_hours'] == pytest.approx(4.25, rel=1e-9)

    def test_short_trade_winning_calculations(self, sample_short_trade_data):
        """Test calculations for a winning short trade"""
        result = app.compute_derived_fields(sample_short_trade_data)

        # Quantity
        expected_quantity = 500.0 / 3000.0
        assert result['quantity'] == pytest.approx(expected_quantity, rel=1e-9)

        # Gross PnL for Short: (entry_price - exit_price) * quantity
        expected_gross_pnl = (3000.0 - 2950.0) * expected_quantity
        assert result['gross_pnl_usd'] == pytest.approx(expected_gross_pnl, rel=1e-9)
        assert result['gross_pnl_usd'] == pytest.approx(8.333333, rel=1e-5)

        # Risk for Short: (stop_price - entry_price) * quantity
        expected_risk = (3100.0 - 3000.0) * expected_quantity
        assert result['risk_usd'] == pytest.approx(expected_risk, rel=1e-9)
        assert result['risk_usd'] == pytest.approx(16.666667, rel=1e-5)

        # Net PnL: gross_pnl - fees - funding (funding is negative, so we add)
        expected_net_pnl = 8.333333 - 1.5 - (-0.3)
        assert result['net_pnl_usd'] == pytest.approx(expected_net_pnl, rel=1e-5)
        assert result['net_pnl_usd'] == pytest.approx(7.133333, rel=1e-5)

        # R multiple
        expected_r = expected_net_pnl / expected_risk
        assert result['r_multiple'] == pytest.approx(expected_r, rel=1e-5)

        # Win/Loss
        assert result['win_loss'] == 'Win'

    def test_long_trade_losing_calculations(self):
        """Test calculations for a losing long trade"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 49800.0,  # Hit near stop
            'fees_usd': 2.0,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Should be negative PnL
        quantity = 1000.0 / 50000.0
        gross_pnl = (49800.0 - 50000.0) * quantity
        net_pnl = gross_pnl - 2.0

        assert result['gross_pnl_usd'] == pytest.approx(gross_pnl, rel=1e-9)
        assert result['net_pnl_usd'] == pytest.approx(net_pnl, rel=1e-9)
        assert result['net_pnl_usd'] < 0
        assert result['win_loss'] == 'Loss'
        assert result['r_multiple'] < 0

    def test_short_trade_losing_calculations(self):
        """Test calculations for a losing short trade"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'ETH/USDT',
            'direction': 'Short',
            'leverage_x': 3.0,
            'position_notional': 500.0,
            'entry_price': 3000.0,
            'stop_price': 3100.0,
            'exit_price': 3080.0,  # Hit near stop
            'fees_usd': 1.5,
            'funding_usd': 0.0,
            'exchange': 'Bybit',
            'setup_strategy': 'Range Reversion',
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Should be negative PnL
        quantity = 500.0 / 3000.0
        gross_pnl = (3000.0 - 3080.0) * quantity  # Negative
        net_pnl = gross_pnl - 1.5

        assert result['gross_pnl_usd'] == pytest.approx(gross_pnl, rel=1e-9)
        assert result['net_pnl_usd'] == pytest.approx(net_pnl, rel=1e-9)
        assert result['net_pnl_usd'] < 0
        assert result['win_loss'] == 'Loss'
        assert result['r_multiple'] < 0

    def test_breakeven_trade(self):
        """Test calculations for a breakeven trade"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 50100.0,  # Small profit that covers fees
            'fees_usd': 2.0,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Net PnL should be exactly 0 or very close
        quantity = 1000.0 / 50000.0
        gross_pnl = (50100.0 - 50000.0) * quantity
        net_pnl = gross_pnl - 2.0

        assert result['net_pnl_usd'] == pytest.approx(net_pnl, rel=1e-9)

        if abs(net_pnl) < 1e-9:
            assert result['win_loss'] == 'Breakeven'
        elif net_pnl > 0:
            assert result['win_loss'] == 'Win'
        else:
            assert result['win_loss'] == 'Loss'

    def test_open_trade_no_exit(self):
        """Test calculations for an open trade without exit price"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': None,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': None,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Quantity should be calculated
        assert result['quantity'] == pytest.approx(0.02, rel=1e-9)

        # Risk should be calculated
        assert result['risk_usd'] == pytest.approx(10.0, rel=1e-9)

        # PnL-related fields should be None
        assert result['gross_pnl_usd'] is None
        assert result['net_pnl_usd'] is None
        assert result['pnl_pct'] is None
        assert result['r_multiple'] is None
        assert result['win_loss'] is None
        assert result['holding_period_hours'] is None

    def test_edge_case_zero_risk(self):
        """Test handling when stop equals entry (zero risk)"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 50000.0,  # Same as entry
            'exit_price': 50500.0,
            'fees_usd': 2.0,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Risk should be 0
        assert result['risk_usd'] == 0.0

        # R multiple should be None (can't divide by zero)
        assert result['r_multiple'] is None

    def test_edge_case_very_small_position(self):
        """Test with very small position size"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 1.0,
            'position_notional': 10.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 51000.0,
            'fees_usd': 0.02,
            'funding_usd': 0.01,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        quantity = 10.0 / 50000.0
        gross_pnl = (51000.0 - 50000.0) * quantity
        net_pnl = gross_pnl - 0.02 - 0.01

        assert result['quantity'] == pytest.approx(quantity, rel=1e-9)
        assert result['gross_pnl_usd'] == pytest.approx(gross_pnl, rel=1e-9)
        assert result['net_pnl_usd'] == pytest.approx(net_pnl, rel=1e-9)

    def test_edge_case_high_leverage(self):
        """Test with high leverage (should not affect calculations)"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 100.0,  # High leverage
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 51000.0,
            'fees_usd': 2.0,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Leverage shouldn't affect PnL calculations
        quantity = 1000.0 / 50000.0
        gross_pnl = (51000.0 - 50000.0) * quantity

        assert result['gross_pnl_usd'] == pytest.approx(gross_pnl, rel=1e-9)


# ============================================================================
# DATABASE TESTS
# ============================================================================

class TestDatabase:
    """Test database operations"""

    def test_add_trade(self, temp_db, sample_long_trade_data):
        """Test adding a trade to the database"""
        success = app.add_trade(sample_long_trade_data)
        assert success is True

        # Verify trade was added
        df = app.get_all_trades()
        assert len(df) == 1

        # Check key fields
        trade = df.iloc[0]
        assert trade['pair'] == 'BTC/USDT'
        assert trade['direction'] == 'Long'
        assert trade['position_notional'] == 1000.0
        assert trade['entry_price'] == 50000.0

        # Check derived fields were calculated
        assert trade['quantity'] == pytest.approx(0.02, rel=1e-9)
        assert trade['net_pnl_usd'] == pytest.approx(27.5, rel=1e-5)
        assert trade['win_loss'] == 'Win'

    def test_add_multiple_trades(self, temp_db, sample_long_trade_data, sample_short_trade_data):
        """Test adding multiple trades"""
        app.add_trade(sample_long_trade_data)
        app.add_trade(sample_short_trade_data)

        df = app.get_all_trades()
        assert len(df) == 2

        # Check both trades are different
        assert df['pair'].tolist() == ['BTC/USDT', 'ETH/USDT']
        assert set(df['direction'].tolist()) == {'Long', 'Short'}

    def test_update_trade(self, temp_db, sample_long_trade_data):
        """Test updating a trade"""
        # Add trade
        app.add_trade(sample_long_trade_data)
        df = app.get_all_trades()
        trade_id = df.iloc[0]['id']

        # Update exit price
        updated_data = sample_long_trade_data.copy()
        updated_data['exit_price'] = 52000.0  # Better exit

        success = app.update_trade(trade_id, updated_data)
        assert success is True

        # Verify update
        df = app.get_all_trades()
        trade = df.iloc[0]
        assert trade['exit_price'] == 52000.0

        # Verify derived fields were recalculated
        quantity = 1000.0 / 50000.0
        expected_gross_pnl = (52000.0 - 50000.0) * quantity
        expected_net_pnl = expected_gross_pnl - 2.0 - 0.5

        assert trade['gross_pnl_usd'] == pytest.approx(expected_gross_pnl, rel=1e-9)
        assert trade['net_pnl_usd'] == pytest.approx(expected_net_pnl, rel=1e-9)

    def test_delete_trade(self, temp_db, sample_long_trade_data, sample_short_trade_data):
        """Test deleting a trade"""
        app.add_trade(sample_long_trade_data)
        app.add_trade(sample_short_trade_data)

        df = app.get_all_trades()
        assert len(df) == 2

        trade_id = df.iloc[0]['id']
        success = app.delete_trades([trade_id])
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 1
        assert df.iloc[0]['pair'] == 'ETH/USDT'

    def test_delete_multiple_trades(self, temp_db, sample_long_trade_data, sample_short_trade_data):
        """Test deleting multiple trades at once"""
        app.add_trade(sample_long_trade_data)
        app.add_trade(sample_short_trade_data)

        df = app.get_all_trades()
        trade_ids = df['id'].tolist()

        success = app.delete_trades(trade_ids)
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 0

    def test_duplicate_trade(self, temp_db, sample_long_trade_data):
        """Test duplicating a trade"""
        app.add_trade(sample_long_trade_data)
        df = app.get_all_trades()
        trade_id = df.iloc[0]['id']

        success = app.duplicate_trade(trade_id)
        assert success is True

        df = app.get_all_trades()
        assert len(df) == 2

        # Check both trades have same data (except id and timestamps)
        trade1 = df.iloc[0]
        trade2 = df.iloc[1]

        assert trade1['id'] != trade2['id']
        assert trade1['pair'] == trade2['pair']
        assert trade1['direction'] == trade2['direction']
        assert trade1['entry_price'] == trade2['entry_price']
        assert trade1['net_pnl_usd'] == pytest.approx(trade2['net_pnl_usd'], rel=1e-9)

    def test_get_all_trades_empty(self, temp_db):
        """Test getting trades from empty database"""
        df = app.get_all_trades()
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0

    def test_timezone_conversion(self, temp_db, sample_long_trade_data):
        """Test that timestamps are properly converted"""
        berlin_time = app.BERLIN_TZ.localize(datetime(2024, 6, 15, 14, 30))

        trade_data = sample_long_trade_data.copy()
        trade_data['entry_ts'] = berlin_time

        app.add_trade(trade_data)
        df = app.get_all_trades()

        retrieved_time = df.iloc[0]['entry_ts']

        # Should be timezone-aware
        assert retrieved_time.tzinfo is not None

        # Should be in Berlin timezone for display
        assert retrieved_time.tzinfo.zone == 'Europe/Berlin'

        # Should match original time
        assert retrieved_time.year == 2024
        assert retrieved_time.month == 6
        assert retrieved_time.day == 15
        assert retrieved_time.hour == 14
        assert retrieved_time.minute == 30


# ============================================================================
# CSV IMPORT/EXPORT TESTS
# ============================================================================

class TestCSVHandling:
    """Test CSV import and export functionality"""

    def test_csv_export(self, temp_db, sample_long_trade_data, sample_short_trade_data):
        """Test exporting trades to CSV"""
        app.add_trade(sample_long_trade_data)
        app.add_trade(sample_short_trade_data)

        df = app.get_all_trades()
        csv_string = df.to_csv(index=False)

        # Verify CSV has data
        assert len(csv_string) > 0
        assert 'BTC/USDT' in csv_string
        assert 'ETH/USDT' in csv_string

        # Verify can be read back
        from io import StringIO
        df_reimported = pd.read_csv(StringIO(csv_string))
        assert len(df_reimported) == 2
        assert 'pair' in df_reimported.columns
        assert 'net_pnl_usd' in df_reimported.columns

    def test_csv_roundtrip(self, temp_db, sample_long_trade_data):
        """Test exporting and re-importing trades"""
        # Add original trade
        app.add_trade(sample_long_trade_data)
        original_df = app.get_all_trades()

        # Export to CSV
        csv_string = original_df.to_csv(index=False)

        # Clear database
        trade_ids = original_df['id'].tolist()
        app.delete_trades(trade_ids)

        # Re-import from CSV
        from io import StringIO
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

        # Verify reimported data
        new_df = app.get_all_trades()
        assert len(new_df) == 1

        # Compare key fields
        assert new_df.iloc[0]['pair'] == original_df.iloc[0]['pair']
        assert new_df.iloc[0]['direction'] == original_df.iloc[0]['direction']
        assert new_df.iloc[0]['entry_price'] == original_df.iloc[0]['entry_price']


# ============================================================================
# TIMEZONE TESTS
# ============================================================================

class TestTimezones:
    """Test timezone handling"""

    def test_berlin_timezone_aware(self):
        """Test that app.BERLIN_TZ is properly configured"""
        assert app.BERLIN_TZ.zone == 'Europe/Berlin'

        # Test DST handling
        summer_time = app.BERLIN_TZ.localize(datetime(2024, 7, 1, 12, 0))
        winter_time = app.BERLIN_TZ.localize(datetime(2024, 1, 1, 12, 0))

        # Berlin is UTC+2 in summer, UTC+1 in winter
        assert summer_time.utcoffset().total_seconds() / 3600 == 2
        assert winter_time.utcoffset().total_seconds() / 3600 == 1

    def test_timezone_storage_and_retrieval(self, temp_db):
        """Test that timezones are preserved through storage"""
        # Create a specific Berlin time
        berlin_time = app.BERLIN_TZ.localize(datetime(2024, 3, 15, 14, 30))

        trade_data = {
            'entry_ts': berlin_time,
            'exit_ts': None,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': None,
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
            'system_compliance': 3,
            'confidence': 3
        }

        app.add_trade(trade_data)
        df = app.get_all_trades()

        retrieved_time = df.iloc[0]['entry_ts']

        # Should match original time in Berlin timezone
        assert retrieved_time.year == berlin_time.year
        assert retrieved_time.month == berlin_time.month
        assert retrieved_time.day == berlin_time.day
        assert retrieved_time.hour == berlin_time.hour
        assert retrieved_time.minute == berlin_time.minute


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_missing_required_fields(self):
        """Test handling of missing required fields"""
        incomplete_data = {
            'pair': 'BTC/USDT',
            'direction': 'Long',
            # Missing many required fields
        }

        # Should handle gracefully
        result = app.compute_derived_fields(incomplete_data)

        # Should return None for most derived fields
        assert result['quantity'] is None or 'quantity' not in result or pd.isna(result.get('quantity'))

    def test_null_exit_price_handling(self):
        """Test that null exit prices are handled correctly"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': None,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': None,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # PnL should be None
        assert result['gross_pnl_usd'] is None
        assert result['net_pnl_usd'] is None
        assert result['win_loss'] is None

    def test_negative_fees_and_funding(self):
        """Test handling of negative fees and funding (rebates)"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 5.0,
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 51000.0,
            'fees_usd': -1.0,  # Fee rebate
            'funding_usd': -0.5,  # Funding payment received
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Negative fees/funding should increase net PnL
        quantity = 1000.0 / 50000.0
        gross_pnl = (51000.0 - 50000.0) * quantity
        net_pnl = gross_pnl - (-1.0) - (-0.5)  # Subtracting negatives = adding

        assert result['net_pnl_usd'] == pytest.approx(net_pnl, rel=1e-9)
        assert result['net_pnl_usd'] > result['gross_pnl_usd']

    def test_fractional_leverage(self):
        """Test with fractional leverage values"""
        data = {
            'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 10, 30)),
            'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, 15, 12, 0)),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'leverage_x': 2.5,  # Fractional leverage
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'stop_price': 49500.0,
            'exit_price': 51000.0,
            'fees_usd': 2.0,
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
            'system_compliance': 3,
            'confidence': 3
        }

        result = app.compute_derived_fields(data)

        # Should calculate correctly with fractional leverage
        assert result['quantity'] is not None
        assert result['net_pnl_usd'] is not None


# ============================================================================
# PERFORMANCE AND STATS TESTS
# ============================================================================

class TestPerformanceMetrics:
    """Test performance metric calculations"""

    def test_win_rate_calculation(self, temp_db):
        """Test win rate calculation"""
        # Add 3 wins and 2 losses
        wins = [
            {'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+1, 10, 0)),
             'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+1, 12, 0)),
             'pair': 'BTC/USDT', 'direction': 'Long', 'leverage_x': 5.0,
             'position_notional': 1000.0, 'entry_price': 50000.0,
             'stop_price': 49500.0, 'exit_price': 51000.0,
             'fees_usd': 2.0, 'funding_usd': 0.0, 'exchange': 'Binance',
             'setup_strategy': 'Breakout', 'market_context': '',
             'entry_rationale': '', 'trigger_confirmation': '',
             'execution_notes': '', 'emotional_state': '',
             'strategy_tags': '', 'market_tags': '', 'mistake_tag': '',
             'screenshot_entry_url': '', 'screenshot_exit_url': '',
             'system_compliance': 3, 'confidence': 3}
            for i in range(3)
        ]

        losses = [
            {'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+10, 10, 0)),
             'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+10, 12, 0)),
             'pair': 'BTC/USDT', 'direction': 'Long', 'leverage_x': 5.0,
             'position_notional': 1000.0, 'entry_price': 50000.0,
             'stop_price': 49500.0, 'exit_price': 49800.0,
             'fees_usd': 2.0, 'funding_usd': 0.0, 'exchange': 'Binance',
             'setup_strategy': 'Breakout', 'market_context': '',
             'entry_rationale': '', 'trigger_confirmation': '',
             'execution_notes': '', 'emotional_state': '',
             'strategy_tags': '', 'market_tags': '', 'mistake_tag': '',
             'screenshot_entry_url': '', 'screenshot_exit_url': '',
             'system_compliance': 3, 'confidence': 3}
            for i in range(2)
        ]

        for trade in wins + losses:
            app.add_trade(trade)

        df = app.get_all_trades()
        closed_trades = df[df['net_pnl_usd'].notna()]

        win_count = len(closed_trades[closed_trades['win_loss'] == 'Win'])
        total_closed = len(closed_trades)
        win_rate = (win_count / total_closed) * 100

        assert total_closed == 5
        assert win_count == 3
        assert win_rate == pytest.approx(60.0, rel=1e-9)

    def test_expectancy_calculation(self, temp_db):
        """Test expectancy (average R) calculation"""
        trades = [
            {'r': 2.0}, {'r': 1.5}, {'r': -1.0}, {'r': 3.0}, {'r': -1.0}
        ]

        for i, trade_r in enumerate(trades):
            # Create trade with specific R multiple
            # Need to work backwards from R to create the trade
            risk = 100.0
            net_pnl = trade_r['r'] * risk
            gross_pnl = net_pnl + 2.0  # Add fees back

            # For long: gross_pnl = (exit - entry) * qty
            entry = 50000.0
            qty = risk / 500.0  # (entry - stop) * qty = risk, so qty = risk / (entry - stop)
            exit_price = entry + (gross_pnl / qty)

            trade_data = {
                'entry_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+1, 10, 0)),
                'exit_ts': app.BERLIN_TZ.localize(datetime(2024, 1, i+1, 12, 0)),
                'pair': 'BTC/USDT', 'direction': 'Long', 'leverage_x': 5.0,
                'position_notional': qty * entry, 'entry_price': entry,
                'stop_price': entry - 500.0, 'exit_price': exit_price,
                'fees_usd': 2.0, 'funding_usd': 0.0, 'exchange': 'Binance',
                'setup_strategy': 'Breakout', 'market_context': '',
                'entry_rationale': '', 'trigger_confirmation': '',
                'execution_notes': '', 'emotional_state': '',
                'strategy_tags': '', 'market_tags': '', 'mistake_tag': '',
                'screenshot_entry_url': '', 'screenshot_exit_url': '',
                'system_compliance': 3, 'confidence': 3
            }
            app.add_trade(trade_data)

        df = app.get_all_trades()
        avg_r = df['r_multiple'].mean()

        expected_avg = sum([t['r'] for t in trades]) / len(trades)
        assert avg_r == pytest.approx(expected_avg, rel=1e-1)  # Some tolerance due to rounding


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
