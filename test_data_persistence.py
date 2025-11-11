"""
Comprehensive tests for data persistence
Tests that data is properly saved to disk and loaded across app restarts/reloads

This test suite addresses the issue reported by the Swedish user:
"And the second also does the same thing as before, it doesn't seem to read from the file,
you can log and it's saved in the file"
"""

import pytest
import pandas as pd
import os
import tempfile
import shutil
from datetime import datetime
import pytz
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import sys
import importlib


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def persistent_db():
    """Create a persistent temporary database that survives module reloads"""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'persistent_test.db')

    yield db_path, temp_dir

    # Cleanup
    try:
        shutil.rmtree(temp_dir)
    except:
        pass


@pytest.fixture
def sample_trade():
    """Sample trade data for testing"""
    import app
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


def reload_app_with_db(db_path):
    """
    Reload the app module with a new database path.
    This simulates restarting the application.
    """
    os.environ['TRADING_JOURNAL_DB'] = db_path
    import app
    importlib.reload(app)
    app.Base.metadata.create_all(app.engine)
    return app


# ============================================================================
# DATA PERSISTENCE TESTS
# ============================================================================

class TestDataPersistence:
    """Test that data persists across app restarts/reloads"""

    def test_data_persists_across_module_reload(self, persistent_db, sample_trade):
        """
        Critical test: Verify data is saved and can be loaded after module reload.
        This simulates restarting the Streamlit app.
        """
        db_path, temp_dir = persistent_db

        # First session: Create and save data
        app = reload_app_with_db(db_path)

        # Add a trade
        success = app.add_trade(sample_trade)
        assert success is True, "Failed to add trade in first session"

        # Verify data was added
        df1 = app.get_all_trades()
        assert len(df1) == 1, "Trade not found in first session"
        assert df1.iloc[0]['pair'] == 'BTC/USDT', "Trade data incorrect in first session"

        # Simulate app restart by reloading the module with the same DB
        app = reload_app_with_db(db_path)

        # Second session: Load data
        df2 = app.get_all_trades()

        # Critical assertions
        assert len(df2) == 1, "PERSISTENCE FAILURE: Trade not loaded in second session!"
        assert df2.iloc[0]['pair'] == 'BTC/USDT', "Trade data corrupted after reload"
        assert df2.iloc[0]['entry_price'] == 50000.0, "Entry price not persisted"
        assert df2.iloc[0]['position_notional'] == 1000.0, "Position notional not persisted"

        # Verify derived fields are also persisted
        assert df2.iloc[0]['quantity'] is not None, "Derived quantity not persisted"
        assert df2.iloc[0]['net_pnl_usd'] is not None, "Derived PnL not persisted"
        assert df2.iloc[0]['win_loss'] == 'Win', "Win/loss classification not persisted"

    def test_multiple_trades_persist(self, persistent_db, sample_trade):
        """Test that multiple trades persist correctly"""
        db_path, temp_dir = persistent_db

        # Session 1: Add 5 trades
        app = reload_app_with_db(db_path)

        for i in range(5):
            trade = sample_trade.copy()
            trade['pair'] = f'BTC/USDT-{i}'
            trade['position_notional'] = 1000.0 * (i + 1)
            app.add_trade(trade)

        df1 = app.get_all_trades()
        assert len(df1) == 5, "Not all trades saved"

        # Session 2: Reload and verify
        app = reload_app_with_db(db_path)
        df2 = app.get_all_trades()

        assert len(df2) == 5, f"Expected 5 trades, found {len(df2)}"

        # Verify all pairs are present
        pairs = sorted(df2['pair'].tolist())
        expected_pairs = sorted([f'BTC/USDT-{i}' for i in range(5)])
        assert pairs == expected_pairs, f"Trade pairs mismatch: {pairs} vs {expected_pairs}"

    def test_data_persists_after_updates(self, persistent_db, sample_trade):
        """Test that updated data persists correctly"""
        db_path, temp_dir = persistent_db

        # Session 1: Add and update trade
        app = reload_app_with_db(db_path)
        app.add_trade(sample_trade)

        df = app.get_all_trades()
        trade_id = df.iloc[0]['id']

        # Update the trade
        updated_data = sample_trade.copy()
        updated_data['exit_price'] = 52000.0
        updated_data['position_notional'] = 2000.0
        app.update_trade(trade_id, updated_data)

        # Session 2: Reload and verify update persisted
        app = reload_app_with_db(db_path)
        df2 = app.get_all_trades()

        assert len(df2) == 1, "Trade lost after update"
        assert df2.iloc[0]['exit_price'] == 52000.0, "Updated exit price not persisted"
        assert df2.iloc[0]['position_notional'] == 2000.0, "Updated notional not persisted"

    def test_data_persists_after_deletion(self, persistent_db, sample_trade):
        """Test that deletions persist correctly"""
        db_path, temp_dir = persistent_db

        # Session 1: Add 3 trades and delete 1
        app = reload_app_with_db(db_path)

        for i in range(3):
            trade = sample_trade.copy()
            trade['pair'] = f'TRADE-{i}'
            app.add_trade(trade)

        df = app.get_all_trades()
        assert len(df) == 3

        # Delete the middle trade
        trade_id_to_delete = df.iloc[1]['id']
        app.delete_trades([trade_id_to_delete])

        # Session 2: Reload and verify deletion persisted
        app = reload_app_with_db(db_path)
        df2 = app.get_all_trades()

        assert len(df2) == 2, "Deletion not persisted"
        remaining_pairs = sorted(df2['pair'].tolist())
        assert remaining_pairs == ['TRADE-0', 'TRADE-2'], "Wrong trades deleted"


# ============================================================================
# DATABASE FILE TESTS
# ============================================================================

class TestDatabaseFile:
    """Test database file creation and management"""

    def test_database_file_created(self, persistent_db, sample_trade):
        """Test that database file is actually created on disk"""
        db_path, temp_dir = persistent_db

        # Initially, file might not exist
        # After reload_app_with_db, it should be created
        app = reload_app_with_db(db_path)

        assert os.path.exists(db_path), f"Database file not created at {db_path}"
        assert os.path.isfile(db_path), f"Database path is not a file: {db_path}"

        # Add data
        app.add_trade(sample_trade)

        # Verify file has content
        file_size = os.path.getsize(db_path)
        assert file_size > 0, f"Database file is empty: {file_size} bytes"

    def test_database_file_path_consistency(self, persistent_db):
        """Test that the database path remains consistent"""
        db_path, temp_dir = persistent_db

        # Session 1
        app1 = reload_app_with_db(db_path)
        assert app1.DB_PATH == db_path, "DB path mismatch in session 1"

        # Session 2
        app2 = reload_app_with_db(db_path)
        assert app2.DB_PATH == db_path, "DB path mismatch in session 2"

        # Both sessions should use the same file
        assert app1.DB_PATH == app2.DB_PATH, "DB path changed between sessions"

    def test_database_structure_persists(self, persistent_db, sample_trade):
        """Test that database structure (tables, columns) persists"""
        db_path, temp_dir = persistent_db

        # Session 1: Create database
        app = reload_app_with_db(db_path)
        app.add_trade(sample_trade)

        # Session 2: Reload and check structure
        app = reload_app_with_db(db_path)

        # Inspect database structure
        inspector = inspect(app.engine)
        tables = inspector.get_table_names()

        assert 'trades' in tables, "Trades table not found after reload"

        # Check that all expected columns exist
        columns = [col['name'] for col in inspector.get_columns('trades')]
        expected_columns = [
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

        for col in expected_columns:
            assert col in columns, f"Column '{col}' missing after reload"


# ============================================================================
# EDGE CASE PERSISTENCE TESTS
# ============================================================================

class TestPersistenceEdgeCases:
    """Test edge cases in data persistence"""

    def test_empty_database_loads_correctly(self, persistent_db):
        """Test that empty database loads without errors"""
        db_path, temp_dir = persistent_db

        app = reload_app_with_db(db_path)
        df = app.get_all_trades()

        assert isinstance(df, pd.DataFrame), "Should return DataFrame even when empty"
        assert len(df) == 0, "Empty database should return empty DataFrame"

    def test_null_values_persist(self, persistent_db, sample_trade):
        """Test that null/None values persist correctly"""
        db_path, temp_dir = persistent_db

        # Session 1: Add trade with null exit
        app = reload_app_with_db(db_path)

        trade = sample_trade.copy()
        trade['exit_ts'] = None
        trade['exit_price'] = None
        trade['tp1'] = None
        trade['tp2'] = None

        app.add_trade(trade)

        # Session 2: Reload and verify nulls persisted
        app = reload_app_with_db(db_path)
        df = app.get_all_trades()

        assert len(df) == 1
        assert pd.isna(df.iloc[0]['exit_ts']) or df.iloc[0]['exit_ts'] is None
        assert pd.isna(df.iloc[0]['exit_price']) or df.iloc[0]['exit_price'] is None

    def test_timezone_persists_across_reload(self, persistent_db, sample_trade):
        """Test that timezone information persists correctly"""
        db_path, temp_dir = persistent_db

        # Session 1: Add trade with Berlin timezone
        app = reload_app_with_db(db_path)
        berlin_time = app.BERLIN_TZ.localize(datetime(2024, 6, 15, 14, 30))

        trade = sample_trade.copy()
        trade['entry_ts'] = berlin_time
        app.add_trade(trade)

        # Session 2: Reload and verify timezone
        app = reload_app_with_db(db_path)
        df = app.get_all_trades()

        retrieved_time = df.iloc[0]['entry_ts']

        # Should be timezone-aware
        assert retrieved_time.tzinfo is not None, "Timezone info lost after reload"

        # Should be in Berlin timezone
        assert retrieved_time.tzinfo.zone == 'Europe/Berlin', f"Wrong timezone: {retrieved_time.tzinfo}"

        # Should match original time
        assert retrieved_time.hour == 14, f"Hour mismatch: {retrieved_time.hour}"
        assert retrieved_time.minute == 30, f"Minute mismatch: {retrieved_time.minute}"

    def test_special_characters_persist(self, persistent_db, sample_trade):
        """Test that special characters in text fields persist"""
        db_path, temp_dir = persistent_db

        # Session 1: Add trade with special characters
        app = reload_app_with_db(db_path)

        trade = sample_trade.copy()
        trade['market_context'] = "åäö ÅÄÖ € £ ¥ 中文 日本語"
        trade['entry_rationale'] = "Test\nwith\nnewlines"
        trade['execution_notes'] = "Quotes: 'single' \"double\""

        app.add_trade(trade)

        # Session 2: Reload and verify
        app = reload_app_with_db(db_path)
        df = app.get_all_trades()

        assert df.iloc[0]['market_context'] == "åäö ÅÄÖ € £ ¥ 中文 日本語"
        assert df.iloc[0]['entry_rationale'] == "Test\nwith\nnewlines"
        assert df.iloc[0]['execution_notes'] == "Quotes: 'single' \"double\""


# ============================================================================
# CONCURRENT ACCESS TESTS (BASIC)
# ============================================================================

class TestConcurrentAccess:
    """Test basic concurrent access scenarios"""

    def test_multiple_sessions_see_same_data(self, persistent_db, sample_trade):
        """
        Test that multiple app instances (sessions) can read the same data.
        This simulates multiple browser tabs or concurrent users.
        """
        db_path, temp_dir = persistent_db

        # Session 1: Add data
        app1 = reload_app_with_db(db_path)
        app1.add_trade(sample_trade)

        # Session 2: Read data
        app2 = reload_app_with_db(db_path)
        df2 = app2.get_all_trades()

        assert len(df2) == 1, "Session 2 can't see data from session 1"

        # Session 3: Also read data
        app3 = reload_app_with_db(db_path)
        df3 = app3.get_all_trades()

        assert len(df3) == 1, "Session 3 can't see data"

        # All sessions should see the same data
        assert df2.iloc[0]['pair'] == df3.iloc[0]['pair']


# ============================================================================
# INTEGRATION TEST: REALISTIC USAGE PATTERN
# ============================================================================

class TestRealisticUsagePattern:
    """Test realistic patterns of app usage"""

    def test_multi_day_usage_simulation(self, persistent_db, sample_trade):
        """
        Simulate a realistic multi-day usage pattern:
        Day 1: Add trades
        Day 2: Review and add more
        Day 3: Update and delete some
        Day 4: Export and verify all data
        """
        db_path, temp_dir = persistent_db

        # Day 1: User adds 3 trades
        app = reload_app_with_db(db_path)
        for i in range(3):
            trade = sample_trade.copy()
            trade['pair'] = f'DAY1-TRADE-{i}'
            app.add_trade(trade)

        # End of day 1 - user closes app
        df_day1 = app.get_all_trades()
        assert len(df_day1) == 3

        # Day 2: User reopens app and adds 2 more trades
        app = reload_app_with_db(db_path)
        df = app.get_all_trades()
        assert len(df) == 3, "Day 1 trades not persisted!"

        for i in range(2):
            trade = sample_trade.copy()
            trade['pair'] = f'DAY2-TRADE-{i}'
            app.add_trade(trade)

        df_day2 = app.get_all_trades()
        assert len(df_day2) == 5

        # Day 3: User updates one trade and deletes one
        app = reload_app_with_db(db_path)
        df = app.get_all_trades()
        assert len(df) == 5, "Day 2 trades not persisted!"

        # Update first trade
        first_id = df.iloc[0]['id']
        updated_trade = sample_trade.copy()
        updated_trade['exit_price'] = 99999.0
        app.update_trade(first_id, updated_trade)

        # Delete second trade
        second_id = df.iloc[1]['id']
        app.delete_trades([second_id])

        df_day3 = app.get_all_trades()
        assert len(df_day3) == 4
        assert df_day3[df_day3['id'] == first_id].iloc[0]['exit_price'] == 99999.0

        # Day 4: User exports data
        app = reload_app_with_db(db_path)
        df_final = app.get_all_trades()

        assert len(df_final) == 4, "Final data count incorrect"
        assert df_final[df_final['id'] == first_id].iloc[0]['exit_price'] == 99999.0, "Update lost"

        # Verify can export to CSV
        csv_data = df_final.to_csv(index=False)
        assert len(csv_data) > 0
        assert 'DAY1-TRADE' in csv_data
        assert 'DAY2-TRADE' in csv_data


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
