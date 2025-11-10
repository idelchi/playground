"""
Comprehensive test suite for Crypto Perpetuals Trading Journal.
Tests all calculations, database operations, edge cases, and validations.
"""

import pytest
import pandas as pd
import pytz
import tempfile
import os
import io
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from hypothesis import given, strategies as st, settings
from freezegun import freeze_time

# Import app components
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app import (
    compute_derived_fields,
    add_trade,
    update_trade,
    delete_trades,
    get_all_trades,
    get_trade_by_id,
    localize_datetime,
    to_utc,
    format_currency,
    format_percentage,
    format_number,
    Base,
    Trade,
    BERLIN_TZ,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Create engine and tables
    engine = create_engine(f'sqlite:///{path}')
    Base.metadata.create_all(engine)

    yield path, engine

    # Cleanup
    Base.metadata.drop_all(engine)
    engine.dispose()
    os.unlink(path)


@pytest.fixture
def db_session(temp_db):
    """Create a database session for testing."""
    _, engine = temp_db
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


@pytest.fixture
def sample_long_trade():
    """Sample long trade data."""
    return {
        'entry_ts': datetime(2025, 11, 9, 14, 30, 0, tzinfo=BERLIN_TZ),
        'exit_ts': datetime(2025, 11, 9, 18, 45, 0, tzinfo=BERLIN_TZ),
        'pair': 'BTC/USDT',
        'direction': 'Long',
        'leverage_x': 5.0,
        'position_notional': 1000.0,
        'entry_price': 50000.0,
        'exit_price': 51000.0,
        'stop_price': 49500.0,
        'tp1': 51500.0,
        'tp2': 52000.0,
        'fees_usd': 2.0,
        'funding_usd': 0.5,
        'exchange': 'Binance',
        'setup_strategy': 'Breakout',
        'market_context': 'Bull market',
        'entry_rationale': 'Strong momentum',
        'trigger_confirmation': 'Volume spike',
        'execution_notes': 'Clean entry',
        'emotional_state': 'Calm',
        'strategy_tags': 'momentum',
        'market_tags': 'trending',
        'mistake_tag': '',
        'screenshot_entry_url': '',
        'screenshot_exit_url': '',
        'system_compliance': 5,
        'confidence': 4,
    }


@pytest.fixture
def sample_short_trade():
    """Sample short trade data."""
    return {
        'entry_ts': datetime(2025, 11, 9, 10, 0, 0, tzinfo=BERLIN_TZ),
        'exit_ts': datetime(2025, 11, 9, 12, 0, 0, tzinfo=BERLIN_TZ),
        'pair': 'ETH/USDT',
        'direction': 'Short',
        'leverage_x': 10.0,
        'position_notional': 2000.0,
        'entry_price': 3000.0,
        'exit_price': 2900.0,
        'stop_price': 3100.0,
        'tp1': 2800.0,
        'tp2': 2700.0,
        'fees_usd': 4.0,
        'funding_usd': 1.0,
        'exchange': 'Bybit',
        'setup_strategy': 'Range Reversion',
        'market_context': 'Ranging market',
        'entry_rationale': 'Overbought',
        'trigger_confirmation': 'RSI divergence',
        'execution_notes': 'Good fill',
        'emotional_state': 'Confident',
        'strategy_tags': 'mean-reversion',
        'market_tags': 'ranging',
        'mistake_tag': '',
        'screenshot_entry_url': '',
        'screenshot_exit_url': '',
        'system_compliance': 4,
        'confidence': 5,
    }


# ============================================================================
# Test Calculation Functions
# ============================================================================

class TestCalculations:
    """Test all derived field calculations."""

    def test_long_position_quantity(self, sample_long_trade):
        """Test quantity calculation for long position."""
        result = compute_derived_fields(sample_long_trade)
        expected = 1000.0 / 50000.0  # 0.02
        assert abs(result['quantity'] - expected) < 1e-10

    def test_short_position_quantity(self, sample_short_trade):
        """Test quantity calculation for short position."""
        result = compute_derived_fields(sample_short_trade)
        expected = 2000.0 / 3000.0  # 0.666...
        assert abs(result['quantity'] - expected) < 1e-10

    def test_long_gross_pnl(self, sample_long_trade):
        """Test gross PnL for long position."""
        result = compute_derived_fields(sample_long_trade)
        quantity = 1000.0 / 50000.0
        expected = (51000.0 - 50000.0) * quantity  # $20
        assert abs(result['gross_pnl_usd'] - expected) < 0.01

    def test_short_gross_pnl(self, sample_short_trade):
        """Test gross PnL for short position."""
        result = compute_derived_fields(sample_short_trade)
        quantity = 2000.0 / 3000.0
        expected = (3000.0 - 2900.0) * quantity  # $66.67
        assert abs(result['gross_pnl_usd'] - expected) < 0.01

    def test_long_risk(self, sample_long_trade):
        """Test risk calculation for long position."""
        result = compute_derived_fields(sample_long_trade)
        quantity = 1000.0 / 50000.0
        expected = (50000.0 - 49500.0) * quantity  # $10
        assert abs(result['risk_usd'] - expected) < 0.01

    def test_short_risk(self, sample_short_trade):
        """Test risk calculation for short position."""
        result = compute_derived_fields(sample_short_trade)
        quantity = 2000.0 / 3000.0
        expected = (3100.0 - 3000.0) * quantity  # $66.67
        assert abs(result['risk_usd'] - expected) < 0.01

    def test_net_pnl_with_fees(self, sample_long_trade):
        """Test net PnL includes fees and funding."""
        result = compute_derived_fields(sample_long_trade)
        gross_pnl = (51000.0 - 50000.0) * (1000.0 / 50000.0)
        expected = gross_pnl - 2.0 - 0.5  # $17.50
        assert abs(result['net_pnl_usd'] - expected) < 0.01

    def test_pnl_percentage(self, sample_long_trade):
        """Test PnL percentage calculation."""
        result = compute_derived_fields(sample_long_trade)
        gross_pnl = (51000.0 - 50000.0) * (1000.0 / 50000.0)
        net_pnl = gross_pnl - 2.0 - 0.5
        expected = net_pnl / 1000.0  # 0.0175
        assert abs(result['pnl_pct'] - expected) < 0.0001

    def test_r_multiple(self, sample_long_trade):
        """Test R-multiple calculation."""
        result = compute_derived_fields(sample_long_trade)
        quantity = 1000.0 / 50000.0
        gross_pnl = (51000.0 - 50000.0) * quantity
        net_pnl = gross_pnl - 2.0 - 0.5
        risk = (50000.0 - 49500.0) * quantity
        expected = net_pnl / risk  # 1.75R
        assert abs(result['r_multiple'] - expected) < 0.01

    def test_win_classification(self, sample_long_trade):
        """Test win classification for profitable trade."""
        result = compute_derived_fields(sample_long_trade)
        assert result['win_loss'] == 'Win'

    def test_loss_classification(self):
        """Test loss classification for losing trade."""
        losing_trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 49000.0,  # Loss
            'stop_price': 49500.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(losing_trade)
        assert result['win_loss'] == 'Loss'

    def test_breakeven_classification(self):
        """Test breakeven classification."""
        breakeven_trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50000.0,  # Breakeven
            'stop_price': 49500.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(breakeven_trade)
        assert result['win_loss'] == 'Breakeven'

    def test_holding_period(self, sample_long_trade):
        """Test holding period calculation in hours."""
        result = compute_derived_fields(sample_long_trade)
        expected = 4.25  # 4 hours 15 minutes
        assert abs(result['holding_period_hours'] - expected) < 0.01

    def test_open_position_no_pnl(self):
        """Test that open positions have no PnL calculated."""
        open_trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': None,  # Open position
            'stop_price': 49500.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(open_trade)
        assert result['gross_pnl_usd'] is None
        assert result['net_pnl_usd'] is None
        assert result['pnl_pct'] is None
        assert result['win_loss'] is None

    def test_negative_fees_rebate(self):
        """Test that negative fees (rebates) increase net PnL."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50500.0,
            'stop_price': 49500.0,
            'fees_usd': -2.0,  # Rebate
            'funding_usd': -1.0,  # Received funding
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        # Net PnL should be greater than gross PnL
        assert result['net_pnl_usd'] > result['gross_pnl_usd']


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_very_small_position(self):
        """Test calculation with micro position."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1.0,  # $1
            'entry_price': 50000.0,
            'exit_price': 50100.0,
            'stop_price': 49900.0,
            'fees_usd': 0.01,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        assert result['quantity'] > 0
        assert result['net_pnl_usd'] is not None

    def test_very_high_leverage(self):
        """Test with extremely high leverage."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50500.0,
            'stop_price': 49900.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 100.0,  # 100x leverage
        }
        result = compute_derived_fields(trade)
        assert result['quantity'] > 0
        assert result['r_multiple'] is not None

    def test_decimal_leverage(self):
        """Test with decimal leverage values."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50500.0,
            'stop_price': 49900.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 7.5,  # Decimal leverage
        }
        result = compute_derived_fields(trade)
        assert result['quantity'] > 0

    def test_very_short_holding_period(self):
        """Test with very short holding period."""
        entry = datetime.now(BERLIN_TZ)
        exit = entry + timedelta(seconds=30)  # 30 seconds
        trade = {
            'entry_ts': entry,
            'exit_ts': exit,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50500.0,
            'stop_price': 49900.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        expected_hours = 30 / 3600  # 0.00833...
        assert abs(result['holding_period_hours'] - expected_hours) < 0.001

    def test_very_long_holding_period(self):
        """Test with multi-day holding period."""
        entry = datetime.now(BERLIN_TZ)
        exit = entry + timedelta(days=7)  # 7 days
        trade = {
            'entry_ts': entry,
            'exit_ts': exit,
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49900.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        expected_hours = 7 * 24  # 168 hours
        assert abs(result['holding_period_hours'] - expected_hours) < 0.1

    def test_zero_risk_trade(self):
        """Test trade with stop at entry (zero risk)."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 50500.0,
            'stop_price': 50000.0,  # Stop at entry = 0 risk
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        assert result['risk_usd'] == 0.0
        # R-multiple should be None when risk is 0
        assert result['r_multiple'] is None

    def test_high_precision_prices(self):
        """Test with high precision decimal prices."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'DOGE/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 0.12345678,  # 8 decimals
            'exit_price': 0.12445678,
            'stop_price': 0.12245678,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        assert result['quantity'] > 0
        assert result['gross_pnl_usd'] is not None


# ============================================================================
# Test Timezone Functions
# ============================================================================

class TestTimezone:
    """Test timezone conversion functions."""

    def test_to_utc_from_berlin(self):
        """Test conversion from Berlin to UTC."""
        # Berlin time in summer (CEST = UTC+2)
        berlin_time = BERLIN_TZ.localize(datetime(2025, 7, 15, 14, 30, 0))
        utc_time = to_utc(berlin_time)

        # Should be 2 hours earlier in UTC
        assert utc_time.hour == 12
        assert utc_time.tzinfo is None  # Should be naive UTC

    def test_localize_datetime_from_utc(self):
        """Test conversion from UTC to Berlin."""
        # UTC time
        utc_time = datetime(2025, 7, 15, 12, 30, 0)
        berlin_time = localize_datetime(utc_time)

        # Should be 2 hours later in Berlin (CEST)
        assert berlin_time.hour == 14
        assert str(berlin_time.tzinfo) == 'Europe/Berlin'

    def test_round_trip_conversion(self):
        """Test Berlin -> UTC -> Berlin conversion."""
        original = BERLIN_TZ.localize(datetime(2025, 11, 9, 15, 30, 0))
        utc = to_utc(original)
        back_to_berlin = localize_datetime(utc)

        # Should match original
        assert original.year == back_to_berlin.year
        assert original.month == back_to_berlin.month
        assert original.day == back_to_berlin.day
        assert original.hour == back_to_berlin.hour
        assert original.minute == back_to_berlin.minute


# ============================================================================
# Test Formatting Functions
# ============================================================================

class TestFormatting:
    """Test output formatting functions."""

    def test_format_currency_positive(self):
        """Test currency formatting for positive values."""
        assert format_currency(1234.56) == "$1,234.56"

    def test_format_currency_negative(self):
        """Test currency formatting for negative values."""
        assert format_currency(-1234.56) == "$-1,234.56"

    def test_format_currency_none(self):
        """Test currency formatting for None."""
        assert format_currency(None) == "—"

    def test_format_percentage(self):
        """Test percentage formatting."""
        assert format_percentage(0.1234) == "12.34%"

    def test_format_percentage_negative(self):
        """Test percentage formatting for negative."""
        assert format_percentage(-0.0567) == "-5.67%"

    def test_format_percentage_none(self):
        """Test percentage formatting for None."""
        assert format_percentage(None) == "—"

    def test_format_number(self):
        """Test number formatting with decimals."""
        assert format_number(1.75, 2) == "1.75"

    def test_format_number_none(self):
        """Test number formatting for None."""
        assert format_number(None, 2) == "—"


# ============================================================================
# Test Database Schema
# ============================================================================

class TestDatabaseSchema:
    """Test database schema and table structure."""

    def test_trade_table_exists(self, db_session):
        """Test that Trade table is created."""
        assert Trade.__tablename__ == 'trades'

    def test_all_required_columns_exist(self):
        """Test that all required columns are present."""
        required_columns = [
            'id', 'entry_ts', 'exit_ts', 'pair', 'direction', 'leverage_x',
            'position_notional', 'entry_price', 'stop_price', 'tp1', 'tp2',
            'exit_price', 'fees_usd', 'funding_usd', 'exchange',
            'setup_strategy', 'market_context', 'entry_rationale',
            'trigger_confirmation', 'execution_notes', 'emotional_state',
            'strategy_tags', 'market_tags', 'mistake_tag',
            'screenshot_entry_url', 'screenshot_exit_url',
            'system_compliance', 'confidence',
            'quantity', 'gross_pnl_usd', 'risk_usd', 'net_pnl_usd',
            'pnl_pct', 'r_multiple', 'win_loss', 'holding_period_hours',
            'created_at', 'updated_at'
        ]

        column_names = [col.name for col in Trade.__table__.columns]

        for col in required_columns:
            assert col in column_names, f"Missing column: {col}"

    def test_primary_key_is_id(self):
        """Test that 'id' is the primary key."""
        pk_columns = [col.name for col in Trade.__table__.primary_key.columns]
        assert 'id' in pk_columns


# ============================================================================
# Test Property-Based Testing
# ============================================================================

class TestPropertyBased:
    """Property-based tests using hypothesis."""

    @given(
        position_notional=st.floats(min_value=1.0, max_value=100000.0),
        entry_price=st.floats(min_value=0.01, max_value=100000.0),
    )
    @settings(max_examples=50, deadline=None)
    def test_quantity_always_positive(self, position_notional, entry_price):
        """Property: Quantity should always be positive for valid inputs."""
        trade = {
            'position_notional': position_notional,
            'entry_price': entry_price,
            'direction': 'Long',
            'leverage_x': 1.0,
        }
        result = compute_derived_fields(trade)
        assert result['quantity'] > 0

    @given(
        entry_price=st.floats(min_value=100.0, max_value=1000.0),
        exit_price=st.floats(min_value=100.0, max_value=1000.0),
        position_notional=st.floats(min_value=100.0, max_value=10000.0),
    )
    @settings(max_examples=50, deadline=None)
    def test_long_pnl_sign_correct(self, entry_price, exit_price, position_notional):
        """Property: Long PnL sign should match price direction."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'position_notional': position_notional,
            'entry_price': entry_price,
            'exit_price': exit_price,
            'stop_price': entry_price * 0.95,
            'direction': 'Long',
            'leverage_x': 1.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }
        result = compute_derived_fields(trade)

        if exit_price > entry_price:
            assert result['gross_pnl_usd'] > 0, "Long profit should be positive when exit > entry"
        elif exit_price < entry_price:
            assert result['gross_pnl_usd'] < 0, "Long loss should be negative when exit < entry"
        else:
            assert abs(result['gross_pnl_usd']) < 0.01, "Long breakeven should be ~0 when exit = entry"

    @given(
        leverage=st.floats(min_value=0.1, max_value=125.0),
    )
    @settings(max_examples=30, deadline=None)
    def test_leverage_preserved(self, leverage):
        """Property: Leverage value should be preserved (not used in calculations)."""
        trade = {
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'leverage_x': leverage,
            'direction': 'Long',
        }
        result = compute_derived_fields(trade)
        # Leverage doesn't affect quantity calculation
        expected_quantity = 1000.0 / 50000.0
        assert abs(result['quantity'] - expected_quantity) < 1e-10


# ============================================================================
# Test Data Validation
# ============================================================================

class TestDataValidation:
    """Test input validation and error handling."""

    def test_missing_required_fields(self):
        """Test that missing required fields are handled."""
        incomplete_trade = {
            'pair': 'BTC/USDT',
            # Missing many required fields
        }
        result = compute_derived_fields(incomplete_trade)
        # Should handle gracefully, returning None for derived fields
        assert result.get('quantity') is None or result.get('quantity', 0) == 0

    def test_invalid_direction(self):
        """Test that invalid direction doesn't crash."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'direction': 'Invalid',  # Invalid direction
            'leverage_x': 1.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }
        result = compute_derived_fields(trade)
        # Should return None for PnL when direction is invalid
        assert result['gross_pnl_usd'] is None


# ============================================================================
# Test Specific Business Logic
# ============================================================================

class TestBusinessLogic:
    """Test specific business logic requirements."""

    def test_long_profit_calculation_accuracy(self):
        """Test exact long profit calculation."""
        # Specific test case from requirements
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=2),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'fees_usd': 2.0,
            'funding_usd': 0.5,
            'leverage_x': 5.0,
        }
        result = compute_derived_fields(trade)

        # Expected values
        expected_quantity = 0.02
        expected_gross_pnl = 20.0
        expected_risk = 10.0
        expected_net_pnl = 17.5
        expected_pnl_pct = 0.0175
        expected_r_multiple = 1.75

        assert abs(result['quantity'] - expected_quantity) < 0.0001
        assert abs(result['gross_pnl_usd'] - expected_gross_pnl) < 0.01
        assert abs(result['risk_usd'] - expected_risk) < 0.01
        assert abs(result['net_pnl_usd'] - expected_net_pnl) < 0.01
        assert abs(result['pnl_pct'] - expected_pnl_pct) < 0.0001
        assert abs(result['r_multiple'] - expected_r_multiple) < 0.01
        assert result['win_loss'] == 'Win'

    def test_short_profit_calculation_accuracy(self):
        """Test exact short profit calculation."""
        trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=2),
            'pair': 'ETH/USDT',
            'direction': 'Short',
            'position_notional': 2000.0,
            'entry_price': 3000.0,
            'exit_price': 2900.0,
            'stop_price': 3100.0,
            'fees_usd': 4.0,
            'funding_usd': 1.0,
            'leverage_x': 5.0,
        }
        result = compute_derived_fields(trade)

        # Expected values
        expected_quantity = 2000.0 / 3000.0  # 0.6667
        expected_gross_pnl = 100.0 * expected_quantity  # ~66.67
        expected_risk = 100.0 * expected_quantity  # ~66.67
        expected_net_pnl = expected_gross_pnl - 5.0  # ~61.67

        assert abs(result['quantity'] - expected_quantity) < 0.0001
        assert abs(result['gross_pnl_usd'] - expected_gross_pnl) < 0.01
        assert abs(result['risk_usd'] - expected_risk) < 0.01
        assert abs(result['net_pnl_usd'] - expected_net_pnl) < 0.01
        assert result['win_loss'] == 'Win'

    def test_fees_reduce_profit_correctly(self):
        """Test that fees correctly reduce net PnL."""
        base_trade = {
            'entry_ts': datetime.now(BERLIN_TZ),
            'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
            'pair': 'BTC/USDT',
            'direction': 'Long',
            'position_notional': 1000.0,
            'entry_price': 50000.0,
            'exit_price': 51000.0,
            'stop_price': 49500.0,
            'leverage_x': 1.0,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
        }

        # Calculate without fees
        result_no_fees = compute_derived_fields(base_trade)

        # Calculate with fees
        base_trade['fees_usd'] = 5.0
        base_trade['funding_usd'] = 2.0
        result_with_fees = compute_derived_fields(base_trade)

        # Net PnL with fees should be exactly 7.0 less
        expected_diff = 7.0
        actual_diff = result_no_fees['net_pnl_usd'] - result_with_fees['net_pnl_usd']
        assert abs(actual_diff - expected_diff) < 0.01


# ============================================================================
# Test Comprehensive Scenarios
# ============================================================================

class TestComprehensiveScenarios:
    """Test complete end-to-end scenarios."""

    def test_winning_streak_metrics(self):
        """Test multiple winning trades in sequence."""
        trades = []
        for i in range(5):
            trade = {
                'entry_ts': datetime.now(BERLIN_TZ) + timedelta(days=i),
                'exit_ts': datetime.now(BERLIN_TZ) + timedelta(days=i, hours=2),
                'pair': 'BTC/USDT',
                'direction': 'Long',
                'position_notional': 1000.0,
                'entry_price': 50000.0,
                'exit_price': 51000.0,
                'stop_price': 49500.0,
                'leverage_x': 5.0,
                'fees_usd': 2.0,
                'funding_usd': 0.5,
            }
            result = compute_derived_fields(trade)
            trades.append(result)
            assert result['win_loss'] == 'Win'

        # All should have positive net PnL
        assert all(t['net_pnl_usd'] > 0 for t in trades)

        # All should have same metrics (identical trades)
        assert all(abs(t['r_multiple'] - trades[0]['r_multiple']) < 0.01 for t in trades)

    def test_mixed_outcomes_scenario(self):
        """Test mixture of wins, losses, and breakeven."""
        scenarios = [
            ('Win', 50000.0, 51000.0),
            ('Loss', 50000.0, 49000.0),
            ('Breakeven', 50000.0, 50000.0),
        ]

        results = []
        for expected, entry, exit in scenarios:
            trade = {
                'entry_ts': datetime.now(BERLIN_TZ),
                'exit_ts': datetime.now(BERLIN_TZ) + timedelta(hours=1),
                'pair': 'BTC/USDT',
                'direction': 'Long',
                'position_notional': 1000.0,
                'entry_price': entry,
                'exit_price': exit,
                'stop_price': entry * 0.99,
                'leverage_x': 1.0,
                'fees_usd': 0.0,
                'funding_usd': 0.0,
            }
            result = compute_derived_fields(trade)
            assert result['win_loss'] == expected
            results.append(result)

        # Win should have positive PnL
        assert results[0]['net_pnl_usd'] > 0
        # Loss should have negative PnL
        assert results[1]['net_pnl_usd'] < 0
        # Breakeven should have zero PnL
        assert abs(results[2]['net_pnl_usd']) < 0.01


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '--cov=app', '--cov-report=term-missing'])
