"""
Tests for deployment scenarios and environment-specific issues

This test suite addresses potential issues that could cause the Swedish user's problem:
- Working directory changes
- Relative vs absolute paths
- Environment variable handling
- File permissions
"""

import pytest
import pandas as pd
import os
import tempfile
import shutil
from datetime import datetime
import importlib
import sys


# ============================================================================
# FIXTURES
# ============================================================================

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
        'exit_price': 51500.0,
        'fees_usd': 2.0,
        'funding_usd': 0.5,
        'exchange': 'Binance',
        'setup_strategy': 'Breakout',
        'market_context': 'Test',
        'entry_rationale': 'Test',
        'trigger_confirmation': 'Test',
        'execution_notes': 'Test',
        'emotional_state': 'Test',
        'strategy_tags': '',
        'market_tags': '',
        'mistake_tag': '',
        'screenshot_entry_url': '',
        'screenshot_exit_url': '',
        'system_compliance': 3,
        'confidence': 3
    }


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except:
        pass


def reload_app():
    """Reload the app module"""
    import app
    importlib.reload(app)
    app.Base.metadata.create_all(app.engine)
    return app


# ============================================================================
# WORKING DIRECTORY TESTS
# ============================================================================

class TestWorkingDirectory:
    """Test behavior when working directory changes"""

    def test_relative_path_issue(self, temp_workspace, sample_trade):
        """
        Test that the app now uses ABSOLUTE paths by default to prevent
        the issue where changing working directory creates different DB files.

        FIXED: Previously used relative path 'trades.db', now uses absolute path.
        """
        original_cwd = os.getcwd()

        try:
            # Use a controlled test database to avoid contamination from main trades.db
            test_db_path = os.path.join(temp_workspace, 'test_absolute_path.db')
            os.environ['TRADING_JOURNAL_DB'] = test_db_path

            # Load app from directory 1
            dir1 = os.path.join(temp_workspace, 'dir1')
            os.makedirs(dir1, exist_ok=True)
            os.chdir(dir1)

            app = reload_app()

            # DB path should be ABSOLUTE (from env var)
            assert os.path.isabs(app.DB_PATH), f"DB path should be absolute, got: {app.DB_PATH}"
            assert app.DB_PATH == test_db_path, f"DB path mismatch"

            # Add a trade
            app.add_trade(sample_trade)

            # Load trades
            df1 = app.get_all_trades()
            assert len(df1) == 1, "Trade not saved"

            # Change to directory 2 and reload
            dir2 = os.path.join(temp_workspace, 'dir2')
            os.makedirs(dir2, exist_ok=True)
            os.chdir(dir2)

            app = reload_app()

            # FIXED: With absolute path, we should still see the same data!
            # The database file location is determined by env var or app.py location, not working directory
            df2 = app.get_all_trades()

            # Data should still be accessible because we use absolute path now
            assert len(df2) == 1, "Data should persist across working directory changes"
            assert df2.iloc[0]['pair'] == 'BTC/USDT', "Same data should be accessible"

        finally:
            os.chdir(original_cwd)
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']

    def test_absolute_path_solution(self, temp_workspace, sample_trade):
        """
        Test that using an absolute path solves the working directory issue.
        """
        original_cwd = os.getcwd()

        try:
            # Use absolute path for database
            db_abs_path = os.path.join(temp_workspace, 'shared_trades.db')
            os.environ['TRADING_JOURNAL_DB'] = db_abs_path

            # Work from directory 1
            dir1 = os.path.join(temp_workspace, 'dir1')
            os.makedirs(dir1, exist_ok=True)
            os.chdir(dir1)

            app = reload_app()
            assert app.DB_PATH == db_abs_path

            # Add trade
            app.add_trade(sample_trade)
            df1 = app.get_all_trades()
            assert len(df1) == 1

            # Change to directory 2
            dir2 = os.path.join(temp_workspace, 'dir2')
            os.makedirs(dir2, exist_ok=True)
            os.chdir(dir2)

            app = reload_app()

            # With absolute path, we still see the same data!
            df2 = app.get_all_trades()
            assert len(df2) == 1, "Absolute path allows access from different working dirs"

        finally:
            os.chdir(original_cwd)
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']


# ============================================================================
# ENVIRONMENT VARIABLE TESTS
# ============================================================================

class TestEnvironmentVariables:
    """Test environment variable handling"""

    def test_env_var_takes_precedence(self, temp_workspace, sample_trade):
        """Test that TRADING_JOURNAL_DB env var is respected"""
        original_cwd = os.getcwd()

        try:
            custom_db_path = os.path.join(temp_workspace, 'custom_location.db')
            os.environ['TRADING_JOURNAL_DB'] = custom_db_path

            app = reload_app()

            assert app.DB_PATH == custom_db_path, f"Expected {custom_db_path}, got {app.DB_PATH}"

            # Add data
            app.add_trade(sample_trade)

            # Verify file created at custom location
            assert os.path.exists(custom_db_path), f"DB not created at {custom_db_path}"

            # Verify data accessible
            df = app.get_all_trades()
            assert len(df) == 1

        finally:
            os.chdir(original_cwd)
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']

    def test_default_path_when_no_env_var(self, temp_workspace):
        """Test default behavior when no env var is set"""
        original_cwd = os.getcwd()

        try:
            # Clear env var
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']

            os.chdir(temp_workspace)

            app = reload_app()

            # FIXED: Should now default to absolute path based on app.py location
            assert os.path.isabs(app.DB_PATH), f"Default should be absolute path, got: {app.DB_PATH}"
            assert app.DB_PATH.endswith('trades.db'), f"Should end with trades.db, got: {app.DB_PATH}"

        finally:
            os.chdir(original_cwd)
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']


# ============================================================================
# FILE PERMISSION TESTS
# ============================================================================

class TestFilePermissions:
    """Test file permission scenarios"""

    def test_database_is_writable(self, temp_workspace, sample_trade):
        """Test that database file has correct permissions"""
        db_path = os.path.join(temp_workspace, 'test_perms.db')
        os.environ['TRADING_JOURNAL_DB'] = db_path

        try:
            app = reload_app()
            app.add_trade(sample_trade)

            # Check file exists and is writable
            assert os.path.exists(db_path)
            assert os.access(db_path, os.R_OK), "Database file is not readable"
            assert os.access(db_path, os.W_OK), "Database file is not writable"

        finally:
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']

    def test_directory_is_writable(self, temp_workspace, sample_trade):
        """Test that database directory is writable"""
        db_dir = os.path.join(temp_workspace, 'db_directory')
        os.makedirs(db_dir, exist_ok=True)

        db_path = os.path.join(db_dir, 'test.db')
        os.environ['TRADING_JOURNAL_DB'] = db_path

        try:
            # Check directory permissions
            assert os.access(db_dir, os.W_OK), "Database directory is not writable"

            app = reload_app()
            app.add_trade(sample_trade)

            assert os.path.exists(db_path)

        finally:
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']


# ============================================================================
# STREAMLIT CLOUD / DEPLOYMENT TESTS
# ============================================================================

class TestDeploymentScenarios:
    """Test scenarios specific to Streamlit Cloud and other deployments"""

    def test_read_only_filesystem_detection(self, temp_workspace):
        """
        Test behavior when database directory might be read-only.
        In some deployments (like Streamlit Cloud), the app directory might be read-only.
        """
        # This test documents expected behavior but can't fully simulate read-only FS
        # without root permissions

        # Best practice: Database should be in a writable location
        # On Streamlit Cloud, use tempfile or a mounted volume

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, 'cloud_db.db')
            os.environ['TRADING_JOURNAL_DB'] = db_path

            try:
                app = reload_app()

                # Should be able to create database in temp directory
                assert app.engine is not None
                assert app.DB_PATH == db_path

            finally:
                if 'TRADING_JOURNAL_DB' in os.environ:
                    del os.environ['TRADING_JOURNAL_DB']

    def test_persistent_storage_location(self, sample_trade, temp_workspace):
        """
        Test that recommends best practices for persistent storage.

        For local development: uses absolute path (app directory + trades.db)
        For Streamlit Cloud: should use absolute path or mounted storage
        """
        # Document recommended patterns - all use unique paths for testing
        patterns = {
            'local_dev': os.path.join(temp_workspace, 'local_trades.db'),
            'docker': os.path.join(temp_workspace, 'docker_trades.db'),  # Simulate mounted volume
            'cloud': os.path.join(tempfile.gettempdir(), 'cloud_test_trades.db'),
        }

        # Test that app can work with all these patterns
        for scenario, db_path in patterns.items():
            try:
                # Clean up before test
                if os.path.exists(db_path):
                    os.remove(db_path)

                os.environ['TRADING_JOURNAL_DB'] = db_path

                app = reload_app()

                # Should be able to create DB at this location
                app.add_trade(sample_trade)
                df = app.get_all_trades()
                assert len(df) == 1, f"Failed for scenario: {scenario} (got {len(df)} trades)"

                # Cleanup after test
                if os.path.exists(db_path):
                    os.remove(db_path)

            finally:
                if 'TRADING_JOURNAL_DB' in os.environ:
                    del os.environ['TRADING_JOURNAL_DB']


# ============================================================================
# DATABASE PATH VERIFICATION TESTS
# ============================================================================

class TestDatabasePathVerification:
    """Test database path verification and diagnostics"""

    def test_verify_database_location(self, temp_workspace, sample_trade):
        """
        Test that provides diagnostic information about database location.
        This helps debug "data not loading" issues.
        """
        db_path = os.path.join(temp_workspace, 'verified.db')
        os.environ['TRADING_JOURNAL_DB'] = db_path

        try:
            app = reload_app()

            # Add trade
            app.add_trade(sample_trade)

            # Diagnostic checks
            print(f"\nDatabase diagnostics:")
            print(f"  DB_PATH setting: {app.DB_PATH}")
            print(f"  DB file exists: {os.path.exists(db_path)}")
            print(f"  DB file size: {os.path.getsize(db_path) if os.path.exists(db_path) else 0} bytes")
            print(f"  DB file absolute path: {os.path.abspath(db_path)}")
            print(f"  Current working directory: {os.getcwd()}")

            # Verify actual data in database using raw SQL
            from sqlalchemy import text
            with app.engine.connect() as conn:
                result = conn.execute(text("SELECT COUNT(*) FROM trades"))
                count = result.scalar()
                print(f"  Trade count (direct SQL): {count}")

            # Verify data via app function
            df = app.get_all_trades()
            print(f"  Trade count (app function): {len(df)}")

            assert len(df) == 1, "Data verification failed"

        finally:
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']

    def test_database_connection_string(self, temp_workspace, sample_trade):
        """Test that database connection string is correctly formed"""
        db_path = os.path.join(temp_workspace, 'connection_test.db')
        os.environ['TRADING_JOURNAL_DB'] = db_path

        try:
            app = reload_app()

            # Check connection string format
            expected_url = f'sqlite:///{db_path}'
            actual_url = str(app.engine.url)

            print(f"\nConnection string check:")
            print(f"  Expected: {expected_url}")
            print(f"  Actual:   {actual_url}")

            assert expected_url == actual_url, "Connection string mismatch"

            # Verify it works
            app.add_trade(sample_trade)
            df = app.get_all_trades()
            assert len(df) == 1

        finally:
            if 'TRADING_JOURNAL_DB' in os.environ:
                del os.environ['TRADING_JOURNAL_DB']


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short', '-s'])  # -s to show print statements
