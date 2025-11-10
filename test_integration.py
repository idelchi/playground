"""
Integration tests for database operations.
Tests actual CRUD operations with a temporary isolated database.
"""

import pytest
import os
import tempfile
from datetime import datetime, timedelta
import pytz
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set up path
import sys
sys.path.insert(0, os.path.dirname(__file__))

# Import after path setup
from app import Base, Trade, BERLIN_TZ, compute_derived_fields


class TestDatabaseIntegration:
    """Integration tests for database operations."""

    @pytest.fixture(autouse=True)
    def setup_isolated_db(self):
        """Create an isolated test database for each test."""
        # Create temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')

        # Create engine and session
        self.engine = create_engine(f'sqlite:///{self.db_path}', echo=False)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        yield

        # Cleanup
        self.session.close()
        self.engine.dispose()
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_create_trade(self):
        """Test creating a trade in the database."""
        trade_data = {
            'entry_ts': datetime(2025, 11, 9, 14, 30, 0),
            'exit_ts': datetime(2025, 11, 9, 18, 45, 0),
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

        # Compute derived fields
        trade_data = compute_derived_fields(trade_data)

        # Create trade
        trade = Trade(**trade_data)
        self.session.add(trade)
        self.session.commit()

        # Verify
        assert trade.id is not None
        assert trade.pair == 'BTC/USDT'
        assert trade.net_pnl_usd is not None

    def test_read_trade(self):
        """Test reading a trade from the database."""
        # Create trade
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            pair='ETH/USDT',
            direction='Short',
            leverage_x=10.0,
            position_notional=2000.0,
            entry_price=3000.0,
            stop_price=3100.0,
            exchange='Bybit',
            setup_strategy='Pullback',
            system_compliance=3,
            confidence=4,
        )
        self.session.add(trade)
        self.session.commit()

        trade_id = trade.id

        # Read trade
        retrieved_trade = self.session.query(Trade).filter_by(id=trade_id).first()

        # Verify
        assert retrieved_trade is not None
        assert retrieved_trade.pair == 'ETH/USDT'
        assert retrieved_trade.direction == 'Short'
        assert retrieved_trade.leverage_x == 10.0

    def test_update_trade(self):
        """Test updating a trade in the database."""
        # Create trade
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            pair='BTC/USDT',
            direction='Long',
            leverage_x=5.0,
            position_notional=1000.0,
            entry_price=50000.0,
            stop_price=49500.0,
            exchange='Binance',
            setup_strategy='Breakout',
            system_compliance=5,
            confidence=4,
        )
        self.session.add(trade)
        self.session.commit()

        trade_id = trade.id

        # Update trade
        trade.exit_price = 51000.0
        trade.exit_ts = datetime(2025, 11, 9, 18, 30, 0)

        # Recompute derived fields
        trade_data = {
            'entry_ts': trade.entry_ts,
            'exit_ts': trade.exit_ts,
            'pair': trade.pair,
            'direction': trade.direction,
            'position_notional': trade.position_notional,
            'entry_price': trade.entry_price,
            'exit_price': trade.exit_price,
            'stop_price': trade.stop_price,
            'fees_usd': 0.0,
            'funding_usd': 0.0,
            'leverage_x': trade.leverage_x,
        }
        computed = compute_derived_fields(trade_data)

        # Update derived fields
        trade.quantity = computed['quantity']
        trade.gross_pnl_usd = computed['gross_pnl_usd']
        trade.net_pnl_usd = computed['net_pnl_usd']
        trade.r_multiple = computed['r_multiple']
        trade.win_loss = computed['win_loss']

        self.session.commit()

        # Verify
        updated_trade = self.session.query(Trade).filter_by(id=trade_id).first()
        assert updated_trade.exit_price == 51000.0
        assert updated_trade.net_pnl_usd is not None
        assert updated_trade.net_pnl_usd > 0  # Should be profitable

    def test_delete_trade(self):
        """Test deleting a trade from the database."""
        # Create trade
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            pair='BTC/USDT',
            direction='Long',
            leverage_x=5.0,
            position_notional=1000.0,
            entry_price=50000.0,
            stop_price=49500.0,
            exchange='Binance',
            setup_strategy='Breakout',
            system_compliance=5,
            confidence=4,
        )
        self.session.add(trade)
        self.session.commit()

        trade_id = trade.id

        # Delete trade
        self.session.delete(trade)
        self.session.commit()

        # Verify
        deleted_trade = self.session.query(Trade).filter_by(id=trade_id).first()
        assert deleted_trade is None

    def test_query_multiple_trades(self):
        """Test querying multiple trades."""
        # Create multiple trades
        trades_data = [
            ('BTC/USDT', 'Long', 50000.0),
            ('ETH/USDT', 'Short', 3000.0),
            ('BTC/USDT', 'Long', 51000.0),
        ]

        for pair, direction, price in trades_data:
            trade = Trade(
                entry_ts=datetime(2025, 11, 9, 14, 30, 0),
                pair=pair,
                direction=direction,
                leverage_x=5.0,
                position_notional=1000.0,
                entry_price=price,
                stop_price=price * 0.99,
                exchange='Binance',
                setup_strategy='Breakout',
                system_compliance=5,
                confidence=4,
            )
            self.session.add(trade)

        self.session.commit()

        # Query all trades
        all_trades = self.session.query(Trade).all()
        assert len(all_trades) == 3

        # Query BTC trades
        btc_trades = self.session.query(Trade).filter_by(pair='BTC/USDT').all()
        assert len(btc_trades) == 2

        # Query Long trades
        long_trades = self.session.query(Trade).filter_by(direction='Long').all()
        assert len(long_trades) == 2

    def test_filter_by_exchange(self):
        """Test filtering trades by exchange."""
        exchanges = ['Binance', 'Bybit', 'OKX']

        for exchange in exchanges:
            trade = Trade(
                entry_ts=datetime(2025, 11, 9, 14, 30, 0),
                pair='BTC/USDT',
                direction='Long',
                leverage_x=5.0,
                position_notional=1000.0,
                entry_price=50000.0,
                stop_price=49500.0,
                exchange=exchange,
                setup_strategy='Breakout',
                system_compliance=5,
                confidence=4,
            )
            self.session.add(trade)

        self.session.commit()

        # Filter by exchange
        binance_trades = self.session.query(Trade).filter_by(exchange='Binance').all()
        assert len(binance_trades) == 1
        assert binance_trades[0].exchange == 'Binance'

    def test_order_by_timestamp(self):
        """Test ordering trades by timestamp."""
        timestamps = [
            datetime(2025, 11, 9, 10, 0, 0),
            datetime(2025, 11, 9, 12, 0, 0),
            datetime(2025, 11, 9, 14, 0, 0),
        ]

        for ts in timestamps:
            trade = Trade(
                entry_ts=ts,
                pair='BTC/USDT',
                direction='Long',
                leverage_x=5.0,
                position_notional=1000.0,
                entry_price=50000.0,
                stop_price=49500.0,
                exchange='Binance',
                setup_strategy='Breakout',
                system_compliance=5,
                confidence=4,
            )
            self.session.add(trade)

        self.session.commit()

        # Query ordered by timestamp
        trades = self.session.query(Trade).order_by(Trade.entry_ts).all()
        assert len(trades) == 3
        assert trades[0].entry_ts == timestamps[0]
        assert trades[2].entry_ts == timestamps[2]

    def test_nullable_fields(self):
        """Test that nullable fields can be None."""
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            exit_ts=None,  # Nullable
            pair='BTC/USDT',
            direction='Long',
            leverage_x=5.0,
            position_notional=1000.0,
            entry_price=50000.0,
            stop_price=49500.0,
            tp1=None,  # Nullable
            tp2=None,  # Nullable
            exit_price=None,  # Nullable
            exchange='Binance',
            setup_strategy='Breakout',
            system_compliance=5,
            confidence=4,
        )
        self.session.add(trade)
        self.session.commit()

        # Verify
        assert trade.id is not None
        assert trade.exit_ts is None
        assert trade.tp1 is None
        assert trade.exit_price is None

    def test_default_values(self):
        """Test that default values are set correctly."""
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            pair='BTC/USDT',
            direction='Long',
            leverage_x=5.0,
            position_notional=1000.0,
            entry_price=50000.0,
            stop_price=49500.0,
            exchange='Binance',
            setup_strategy='Breakout',
            system_compliance=5,
            confidence=4,
            # Not setting fees_usd, funding_usd - should default to 0
        )
        self.session.add(trade)
        self.session.commit()

        # Verify defaults
        assert trade.fees_usd == 0.0
        assert trade.funding_usd == 0.0
        assert trade.created_at is not None

    def test_complete_trade_lifecycle(self):
        """Test complete lifecycle: create, update exit, verify PnL."""
        # Create open trade
        trade = Trade(
            entry_ts=datetime(2025, 11, 9, 14, 30, 0),
            pair='BTC/USDT',
            direction='Long',
            leverage_x=10.0,
            position_notional=5000.0,
            entry_price=45000.0,
            stop_price=44500.0,
            exchange='Binance',
            setup_strategy='Breakout',
            system_compliance=5,
            confidence=4,
            fees_usd=10.0,
            funding_usd=2.0,
        )

        # Compute initial fields
        trade_data = {
            'entry_ts': trade.entry_ts,
            'pair': trade.pair,
            'direction': trade.direction,
            'position_notional': trade.position_notional,
            'entry_price': trade.entry_price,
            'stop_price': trade.stop_price,
            'fees_usd': trade.fees_usd,
            'funding_usd': trade.funding_usd,
            'leverage_x': trade.leverage_x,
        }
        computed = compute_derived_fields(trade_data)
        trade.quantity = computed['quantity']
        trade.risk_usd = computed['risk_usd']

        self.session.add(trade)
        self.session.commit()

        # Verify open position (no PnL yet)
        assert trade.exit_price is None
        assert trade.net_pnl_usd is None

        # Close the trade
        trade.exit_ts = datetime(2025, 11, 9, 18, 30, 0)
        trade.exit_price = 46000.0

        # Recompute with exit price
        trade_data['exit_ts'] = trade.exit_ts
        trade_data['exit_price'] = trade.exit_price
        computed = compute_derived_fields(trade_data)

        trade.gross_pnl_usd = computed['gross_pnl_usd']
        trade.net_pnl_usd = computed['net_pnl_usd']
        trade.pnl_pct = computed['pnl_pct']
        trade.r_multiple = computed['r_multiple']
        trade.win_loss = computed['win_loss']
        trade.holding_period_hours = computed['holding_period_hours']

        self.session.commit()

        # Verify closed position
        assert trade.exit_price == 46000.0
        assert trade.net_pnl_usd is not None
        assert trade.win_loss == 'Win'
        assert trade.gross_pnl_usd > 0
        assert trade.net_pnl_usd == trade.gross_pnl_usd - 10.0 - 2.0

        # Verify exact calculations
        expected_quantity = 5000.0 / 45000.0
        expected_gross_pnl = (46000.0 - 45000.0) * expected_quantity
        expected_net_pnl = expected_gross_pnl - 12.0

        assert abs(trade.quantity - expected_quantity) < 0.00001
        assert abs(trade.gross_pnl_usd - expected_gross_pnl) < 0.01
        assert abs(trade.net_pnl_usd - expected_net_pnl) < 0.01


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
