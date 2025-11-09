"""
Crypto Perpetuals Trading Journal
A Streamlit app for logging and analyzing crypto perpetual futures trades.
Timezone: Europe/Berlin
Database: SQLite (trades.db)
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import plotly.express as px
import plotly.graph_objects as go
from io import StringIO
import csv

# ============================================================================
# DATABASE SETUP
# ============================================================================

Base = declarative_base()
BERLIN_TZ = pytz.timezone('Europe/Berlin')

# Database engine
engine = create_engine('sqlite:///trades.db', echo=False)
Session = sessionmaker(bind=engine)


class Trade(Base):
    """SQLAlchemy model for trades table"""
    __tablename__ = 'trades'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Raw input fields
    entry_ts = Column(DateTime, nullable=False)
    exit_ts = Column(DateTime, nullable=True)
    pair = Column(String, nullable=False)
    direction = Column(String, nullable=False)  # Long/Short
    leverage_x = Column(Float, nullable=False)
    position_notional = Column(Float, nullable=False)
    entry_price = Column(Float, nullable=False)
    stop_price = Column(Float, nullable=False)
    tp1 = Column(Float, nullable=True)
    tp2 = Column(Float, nullable=True)
    exit_price = Column(Float, nullable=True)
    fees_usd = Column(Float, default=0.0)
    funding_usd = Column(Float, default=0.0)
    exchange = Column(String, nullable=False)

    # Qualitative fields
    setup_strategy = Column(String, nullable=False)
    market_context = Column(Text, default='')
    entry_rationale = Column(Text, default='')
    trigger_confirmation = Column(Text, default='')
    execution_notes = Column(Text, default='')
    emotional_state = Column(Text, default='')
    strategy_tags = Column(String, default='')
    market_tags = Column(String, default='')
    mistake_tag = Column(String, default='')
    screenshot_entry_url = Column(String, default='')
    screenshot_exit_url = Column(String, default='')
    system_compliance = Column(Integer, default=3)
    confidence = Column(Integer, default=3)

    # Derived fields (computed and stored)
    quantity = Column(Float, nullable=True)
    gross_pnl_usd = Column(Float, nullable=True)
    risk_usd = Column(Float, nullable=True)
    net_pnl_usd = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)
    win_loss = Column(String, nullable=True)
    holding_period_hours = Column(Float, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Create tables
Base.metadata.create_all(engine)


# ============================================================================
# CALCULATION FUNCTIONS
# ============================================================================

def compute_derived_fields(trade_data):
    """
    Compute all derived fields from raw inputs.

    Args:
        trade_data: dict with raw trade inputs

    Returns:
        dict with derived fields added
    """
    derived = trade_data.copy()

    # Quantity
    if trade_data.get('position_notional') and trade_data.get('entry_price'):
        derived['quantity'] = trade_data['position_notional'] / trade_data['entry_price']
    else:
        derived['quantity'] = None

    # Gross PnL
    if (derived.get('quantity') is not None and
        trade_data.get('entry_price') and
        trade_data.get('exit_price')):

        if trade_data['direction'] == 'Long':
            derived['gross_pnl_usd'] = (trade_data['exit_price'] - trade_data['entry_price']) * derived['quantity']
        else:  # Short
            derived['gross_pnl_usd'] = (trade_data['entry_price'] - trade_data['exit_price']) * derived['quantity']
    else:
        derived['gross_pnl_usd'] = None

    # Risk
    if (derived.get('quantity') is not None and
        trade_data.get('entry_price') and
        trade_data.get('stop_price')):

        if trade_data['direction'] == 'Long':
            derived['risk_usd'] = (trade_data['entry_price'] - trade_data['stop_price']) * derived['quantity']
        else:  # Short
            derived['risk_usd'] = (trade_data['stop_price'] - trade_data['entry_price']) * derived['quantity']
    else:
        derived['risk_usd'] = None

    # Net PnL
    if derived.get('gross_pnl_usd') is not None:
        fees = trade_data.get('fees_usd', 0) or 0
        funding = trade_data.get('funding_usd', 0) or 0
        derived['net_pnl_usd'] = derived['gross_pnl_usd'] - fees - funding
    else:
        derived['net_pnl_usd'] = None

    # PnL Percentage
    if (derived.get('net_pnl_usd') is not None and
        trade_data.get('position_notional') and
        trade_data['position_notional'] != 0):
        derived['pnl_pct'] = derived['net_pnl_usd'] / trade_data['position_notional']
    else:
        derived['pnl_pct'] = None

    # R Multiple
    if (derived.get('net_pnl_usd') is not None and
        derived.get('risk_usd') is not None and
        derived['risk_usd'] != 0):
        derived['r_multiple'] = derived['net_pnl_usd'] / derived['risk_usd']
    else:
        derived['r_multiple'] = None

    # Win/Loss
    if derived.get('net_pnl_usd') is not None:
        if derived['net_pnl_usd'] > 0:
            derived['win_loss'] = 'Win'
        elif derived['net_pnl_usd'] < 0:
            derived['win_loss'] = 'Loss'
        else:
            derived['win_loss'] = 'Breakeven'
    else:
        derived['win_loss'] = None

    # Holding period
    if trade_data.get('entry_ts') and trade_data.get('exit_ts'):
        delta = trade_data['exit_ts'] - trade_data['entry_ts']
        derived['holding_period_hours'] = delta.total_seconds() / 3600
    else:
        derived['holding_period_hours'] = None

    return derived


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

def get_all_trades():
    """Fetch all trades from database as DataFrame"""
    session = Session()
    try:
        trades = session.query(Trade).all()
        if not trades:
            return pd.DataFrame()

        data = []
        for trade in trades:
            data.append({col.name: getattr(trade, col.name) for col in Trade.__table__.columns})

        df = pd.DataFrame(data)

        # Convert timestamps to Berlin timezone for display
        if 'entry_ts' in df.columns:
            df['entry_ts'] = pd.to_datetime(df['entry_ts']).dt.tz_localize('UTC').dt.tz_convert(BERLIN_TZ)
        if 'exit_ts' in df.columns:
            df['exit_ts'] = pd.to_datetime(df['exit_ts']).dt.tz_localize('UTC').dt.tz_convert(BERLIN_TZ)

        return df
    finally:
        session.close()


def add_trade(trade_data):
    """Add a new trade to the database"""
    session = Session()
    try:
        # Compute derived fields
        complete_data = compute_derived_fields(trade_data)

        # Convert Berlin time to UTC for storage
        if 'entry_ts' in complete_data and complete_data['entry_ts']:
            if complete_data['entry_ts'].tzinfo is None:
                complete_data['entry_ts'] = BERLIN_TZ.localize(complete_data['entry_ts']).astimezone(pytz.UTC)
            else:
                complete_data['entry_ts'] = complete_data['entry_ts'].astimezone(pytz.UTC)

        if 'exit_ts' in complete_data and complete_data['exit_ts']:
            if complete_data['exit_ts'].tzinfo is None:
                complete_data['exit_ts'] = BERLIN_TZ.localize(complete_data['exit_ts']).astimezone(pytz.UTC)
            else:
                complete_data['exit_ts'] = complete_data['exit_ts'].astimezone(pytz.UTC)

        trade = Trade(**complete_data)
        session.add(trade)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Error adding trade: {e}")
        return False
    finally:
        session.close()


def update_trade(trade_id, trade_data):
    """Update an existing trade"""
    session = Session()
    try:
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if not trade:
            return False

        # Compute derived fields
        complete_data = compute_derived_fields(trade_data)

        # Convert Berlin time to UTC for storage
        if 'entry_ts' in complete_data and complete_data['entry_ts']:
            if complete_data['entry_ts'].tzinfo is None:
                complete_data['entry_ts'] = BERLIN_TZ.localize(complete_data['entry_ts']).astimezone(pytz.UTC)
            else:
                complete_data['entry_ts'] = complete_data['entry_ts'].astimezone(pytz.UTC)

        if 'exit_ts' in complete_data and complete_data['exit_ts']:
            if complete_data['exit_ts'].tzinfo is None:
                complete_data['exit_ts'] = BERLIN_TZ.localize(complete_data['exit_ts']).astimezone(pytz.UTC)
            else:
                complete_data['exit_ts'] = complete_data['exit_ts'].astimezone(pytz.UTC)

        # Update fields
        for key, value in complete_data.items():
            if hasattr(trade, key):
                setattr(trade, key, value)

        trade.updated_at = datetime.utcnow()
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Error updating trade: {e}")
        return False
    finally:
        session.close()


def delete_trades(trade_ids):
    """Delete trades by IDs"""
    session = Session()
    try:
        session.query(Trade).filter(Trade.id.in_(trade_ids)).delete(synchronize_session=False)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Error deleting trades: {e}")
        return False
    finally:
        session.close()


def duplicate_trade(trade_id):
    """Duplicate a trade (without id, created_at, updated_at)"""
    session = Session()
    try:
        original = session.query(Trade).filter_by(id=trade_id).first()
        if not original:
            return False

        # Get all data except id and timestamps
        trade_data = {col.name: getattr(original, col.name)
                     for col in Trade.__table__.columns
                     if col.name not in ['id', 'created_at', 'updated_at']}

        # Convert to dict and handle datetime conversion
        if trade_data.get('entry_ts'):
            trade_data['entry_ts'] = trade_data['entry_ts']
        if trade_data.get('exit_ts'):
            trade_data['exit_ts'] = trade_data['exit_ts']

        new_trade = Trade(**trade_data)
        session.add(new_trade)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        st.error(f"Error duplicating trade: {e}")
        return False
    finally:
        session.close()


# ============================================================================
# UI HELPER FUNCTIONS
# ============================================================================

def format_currency(value):
    """Format value as currency"""
    if pd.isna(value) or value is None:
        return "N/A"
    return f"${value:,.2f}"


def format_percent(value):
    """Format value as percentage"""
    if pd.isna(value) or value is None:
        return "N/A"
    return f"{value * 100:.2f}%"


def format_number(value, decimals=2):
    """Format number with specified decimals"""
    if pd.isna(value) or value is None:
        return "N/A"
    return f"{value:.{decimals}f}"


# ============================================================================
# STREAMLIT APP
# ============================================================================

def main():
    st.set_page_config(
        page_title="Crypto Perp Trading Journal",
        page_icon="📊",
        layout="wide"
    )

    st.title("📊 Crypto Perpetuals Trading Journal")

    # Initialize session state
    if 'refresh' not in st.session_state:
        st.session_state.refresh = 0

    # ========================================================================
    # SIDEBAR - FILTERS & CONTROLS
    # ========================================================================

    with st.sidebar:
        st.header("🔍 Filters")

        # Load all trades for filter options
        all_trades_df = get_all_trades()

        # Starting balance for equity curve
        starting_balance = st.number_input(
            "Starting Balance (USD)",
            min_value=0.0,
            value=10000.0,
            step=1000.0,
            help="Used for equity curve calculation"
        )

        st.divider()

        # Date range filter
        if not all_trades_df.empty and 'entry_ts' in all_trades_df.columns:
            min_date = all_trades_df['entry_ts'].min().date()
            max_date = all_trades_df['entry_ts'].max().date()

            date_range = st.date_input(
                "Date Range (Entry)",
                value=(min_date, max_date),
                help="Filter by entry timestamp"
            )
        else:
            date_range = None

        # Pair filter
        if not all_trades_df.empty and 'pair' in all_trades_df.columns:
            unique_pairs = sorted(all_trades_df['pair'].unique().tolist())
            selected_pairs = st.multiselect(
                "Trading Pairs",
                options=unique_pairs,
                default=unique_pairs
            )
        else:
            selected_pairs = []

        # Direction filter
        selected_direction = st.multiselect(
            "Direction",
            options=['Long', 'Short'],
            default=['Long', 'Short']
        )

        # Exchange filter
        if not all_trades_df.empty and 'exchange' in all_trades_df.columns:
            unique_exchanges = sorted(all_trades_df['exchange'].unique().tolist())
            selected_exchanges = st.multiselect(
                "Exchanges",
                options=unique_exchanges,
                default=unique_exchanges
            )
        else:
            selected_exchanges = []

        # Strategy filter
        if not all_trades_df.empty and 'setup_strategy' in all_trades_df.columns:
            unique_strategies = sorted(all_trades_df['setup_strategy'].unique().tolist())
            selected_strategies = st.multiselect(
                "Strategies",
                options=unique_strategies,
                default=unique_strategies
            )
        else:
            selected_strategies = []

        # Win/Loss filter
        selected_win_loss = st.multiselect(
            "Win/Loss",
            options=['Win', 'Loss', 'Breakeven'],
            default=['Win', 'Loss', 'Breakeven']
        )

        st.divider()

        if st.button("🔄 Refresh Data"):
            st.session_state.refresh += 1
            st.rerun()

    # ========================================================================
    # APPLY FILTERS
    # ========================================================================

    filtered_df = all_trades_df.copy()

    if not filtered_df.empty:
        # Date range
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            filtered_df = filtered_df[
                (filtered_df['entry_ts'].dt.date >= start_date) &
                (filtered_df['entry_ts'].dt.date <= end_date)
            ]

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

    # ========================================================================
    # MAIN CONTENT - TABS
    # ========================================================================

    tab1, tab2, tab3 = st.tabs(["➕ New Trade", "📋 Trades Table", "📊 Dashboard"])

    # ========================================================================
    # TAB 1: NEW TRADE FORM
    # ========================================================================

    with tab1:
        st.header("Log New Trade")

        with st.form("new_trade_form", clear_on_submit=True):
            st.subheader("Trade Metadata")

            col1, col2 = st.columns(2)

            with col1:
                entry_ts = st.date_input("Entry Date", value=datetime.now(BERLIN_TZ).date())
                entry_time = st.time_input("Entry Time", value=datetime.now(BERLIN_TZ).time())
                pair = st.text_input("Pair", value="BTC/USDT", help="e.g., BTC/USDT, ETH/USDT")
                direction = st.selectbox("Direction", options=['Long', 'Short'])
                leverage_x = st.number_input("Leverage", min_value=0.1, value=5.0, step=0.5)
                position_notional = st.number_input("Position Notional (USD)", min_value=0.0, value=1000.0, step=10.0)
                entry_price = st.number_input("Entry Price", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                stop_price = st.number_input("Stop Price", min_value=0.0, value=0.0, step=0.01, format="%.8f")

            with col2:
                exit_date = st.date_input("Exit Date (Optional)", value=None)
                exit_time = st.time_input("Exit Time (Optional)", value=datetime.now(BERLIN_TZ).time())
                tp1 = st.number_input("TP1 (Optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                tp2 = st.number_input("TP2 (Optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                exit_price = st.number_input("Exit Price (Optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                fees_usd = st.number_input("Fees (USD)", value=0.0, step=0.01)
                funding_usd = st.number_input("Funding (USD)", value=0.0, step=0.01)
                exchange = st.selectbox("Exchange",
                                       options=['Binance', 'Bybit', 'OKX', 'Bitget',
                                               'Deribit', 'Hyperliquid', 'Kraken', 'Other'])

            st.subheader("Trade Thesis & Execution")

            col3, col4 = st.columns(2)

            with col3:
                setup_strategy = st.selectbox("Setup/Strategy",
                    options=['Breakout', 'Range Reversion', 'Trend Continuation',
                            'VWAP Mean Reversion', 'News Catalyst', 'Liquidity Sweep',
                            'Pullback', 'Other'])

                market_context = st.text_area("Market Context", height=100)
                entry_rationale = st.text_area("Entry Rationale", height=100)
                trigger_confirmation = st.text_area("Trigger Confirmation", height=100)
                execution_notes = st.text_area("Execution Notes", height=100)

            with col4:
                emotional_state = st.text_area("Emotional State", height=100)
                strategy_tags = st.text_input("Strategy Tags (comma-separated)")
                market_tags = st.text_input("Market Tags (comma-separated)")
                mistake_tag = st.selectbox("Mistake Tag (if any)",
                    options=['', 'Overleverage', 'No Confirmation', 'Moved Stop',
                            'FOMO Entry', 'Revenge Trade', 'Ignored Plan',
                            'Late Entry', 'Fatigue', 'Other'])

                screenshot_entry_url = st.text_input("Screenshot Entry URL")
                screenshot_exit_url = st.text_input("Screenshot Exit URL")

                system_compliance = st.slider("System Compliance", 1, 5, 3)
                confidence = st.slider("Confidence", 1, 5, 3)

            submitted = st.form_submit_button("💾 Save Trade", use_container_width=True)

            if submitted:
                # Combine date and time
                entry_datetime = datetime.combine(entry_ts, entry_time)
                entry_datetime = BERLIN_TZ.localize(entry_datetime)

                exit_datetime = None
                if exit_date:
                    exit_datetime = datetime.combine(exit_date, exit_time)
                    exit_datetime = BERLIN_TZ.localize(exit_datetime)

                # Prepare trade data
                trade_data = {
                    'entry_ts': entry_datetime,
                    'exit_ts': exit_datetime,
                    'pair': pair,
                    'direction': direction,
                    'leverage_x': leverage_x,
                    'position_notional': position_notional,
                    'entry_price': entry_price if entry_price > 0 else None,
                    'stop_price': stop_price if stop_price > 0 else None,
                    'tp1': tp1 if tp1 > 0 else None,
                    'tp2': tp2 if tp2 > 0 else None,
                    'exit_price': exit_price if exit_price > 0 else None,
                    'fees_usd': fees_usd,
                    'funding_usd': funding_usd,
                    'exchange': exchange,
                    'setup_strategy': setup_strategy,
                    'market_context': market_context,
                    'entry_rationale': entry_rationale,
                    'trigger_confirmation': trigger_confirmation,
                    'execution_notes': execution_notes,
                    'emotional_state': emotional_state,
                    'strategy_tags': strategy_tags,
                    'market_tags': market_tags,
                    'mistake_tag': mistake_tag,
                    'screenshot_entry_url': screenshot_entry_url,
                    'screenshot_exit_url': screenshot_exit_url,
                    'system_compliance': system_compliance,
                    'confidence': confidence,
                }

                # Validate
                if not entry_price or entry_price <= 0:
                    st.error("Entry price is required and must be greater than 0")
                elif not stop_price or stop_price <= 0:
                    st.error("Stop price is required and must be greater than 0")
                else:
                    if add_trade(trade_data):
                        st.success("✅ Trade saved successfully!")
                        st.session_state.refresh += 1
                        st.rerun()

    # ========================================================================
    # TAB 2: TRADES TABLE & EDITOR
    # ========================================================================

    with tab2:
        st.header("Trades Table")

        if filtered_df.empty:
            st.info("No trades found. Add your first trade to get started!")
        else:
            # CSV Export/Import
            col_exp1, col_exp2 = st.columns([1, 1])

            with col_exp1:
                csv_data = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📥 Export to CSV",
                    data=csv_data,
                    file_name=f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )

            with col_exp2:
                uploaded_file = st.file_uploader("📤 Import CSV", type=['csv'])
                if uploaded_file:
                    try:
                        import_df = pd.read_csv(uploaded_file)
                        st.write("Preview:")
                        st.dataframe(import_df.head())

                        if st.button("Confirm Import"):
                            # Import trades
                            for _, row in import_df.iterrows():
                                trade_dict = row.to_dict()

                                # Parse dates
                                if 'entry_ts' in trade_dict:
                                    trade_dict['entry_ts'] = pd.to_datetime(trade_dict['entry_ts'])
                                if 'exit_ts' in trade_dict and pd.notna(trade_dict['exit_ts']):
                                    trade_dict['exit_ts'] = pd.to_datetime(trade_dict['exit_ts'])
                                else:
                                    trade_dict['exit_ts'] = None

                                # Remove id if present
                                trade_dict.pop('id', None)
                                trade_dict.pop('created_at', None)
                                trade_dict.pop('updated_at', None)

                                add_trade(trade_dict)

                            st.success(f"✅ Imported {len(import_df)} trades!")
                            st.session_state.refresh += 1
                            st.rerun()
                    except Exception as e:
                        st.error(f"Import error: {e}")

            st.divider()

            # Display table with key columns
            display_cols = ['id', 'entry_ts', 'exit_ts', 'pair', 'direction', 'exchange',
                          'setup_strategy', 'entry_price', 'exit_price', 'position_notional',
                          'net_pnl_usd', 'pnl_pct', 'r_multiple', 'win_loss']

            available_cols = [col for col in display_cols if col in filtered_df.columns]
            display_df = filtered_df[available_cols].copy()

            # Format for display
            if 'entry_ts' in display_df.columns:
                display_df['entry_ts'] = display_df['entry_ts'].dt.strftime('%Y-%m-%d %H:%M')
            if 'exit_ts' in display_df.columns:
                display_df['exit_ts'] = display_df['exit_ts'].dt.strftime('%Y-%m-%d %H:%M')

            st.dataframe(
                display_df,
                use_container_width=True,
                hide_index=True
            )

            st.divider()

            # Trade detail viewer and editor
            st.subheader("Trade Details & Editor")

            if not filtered_df.empty:
                trade_ids = filtered_df['id'].tolist()
                selected_id = st.selectbox("Select Trade ID to View/Edit", options=trade_ids)

                if selected_id:
                    trade_row = filtered_df[filtered_df['id'] == selected_id].iloc[0]

                    col_btn1, col_btn2, col_btn3 = st.columns(3)

                    with col_btn1:
                        if st.button("🗑️ Delete", use_container_width=True):
                            if delete_trades([selected_id]):
                                st.success("Trade deleted!")
                                st.session_state.refresh += 1
                                st.rerun()

                    with col_btn2:
                        if st.button("📋 Duplicate", use_container_width=True):
                            if duplicate_trade(selected_id):
                                st.success("Trade duplicated!")
                                st.session_state.refresh += 1
                                st.rerun()

                    with st.expander("📝 Edit Trade", expanded=True):
                        with st.form(f"edit_form_{selected_id}"):
                            st.subheader("Edit Trade Metadata")

                            e_col1, e_col2 = st.columns(2)

                            with e_col1:
                                e_entry_date = st.date_input("Entry Date",
                                    value=trade_row['entry_ts'].date() if pd.notna(trade_row['entry_ts']) else datetime.now().date())
                                e_entry_time = st.time_input("Entry Time",
                                    value=trade_row['entry_ts'].time() if pd.notna(trade_row['entry_ts']) else datetime.now().time())
                                e_pair = st.text_input("Pair", value=trade_row['pair'])
                                e_direction = st.selectbox("Direction", options=['Long', 'Short'],
                                    index=0 if trade_row['direction'] == 'Long' else 1)
                                e_leverage = st.number_input("Leverage", value=float(trade_row['leverage_x']), step=0.5)
                                e_notional = st.number_input("Position Notional", value=float(trade_row['position_notional']), step=10.0)
                                e_entry_price = st.number_input("Entry Price", value=float(trade_row['entry_price']), step=0.01, format="%.8f")
                                e_stop_price = st.number_input("Stop Price", value=float(trade_row['stop_price']), step=0.01, format="%.8f")

                            with e_col2:
                                e_exit_date = st.date_input("Exit Date",
                                    value=trade_row['exit_ts'].date() if pd.notna(trade_row['exit_ts']) else None)
                                e_exit_time = st.time_input("Exit Time",
                                    value=trade_row['exit_ts'].time() if pd.notna(trade_row['exit_ts']) else datetime.now().time())
                                e_tp1 = st.number_input("TP1", value=float(trade_row['tp1']) if pd.notna(trade_row['tp1']) else 0.0, step=0.01, format="%.8f")
                                e_tp2 = st.number_input("TP2", value=float(trade_row['tp2']) if pd.notna(trade_row['tp2']) else 0.0, step=0.01, format="%.8f")
                                e_exit_price = st.number_input("Exit Price",
                                    value=float(trade_row['exit_price']) if pd.notna(trade_row['exit_price']) else 0.0, step=0.01, format="%.8f")
                                e_fees = st.number_input("Fees", value=float(trade_row['fees_usd']), step=0.01)
                                e_funding = st.number_input("Funding", value=float(trade_row['funding_usd']), step=0.01)
                                e_exchange = st.selectbox("Exchange",
                                    options=['Binance', 'Bybit', 'OKX', 'Bitget', 'Deribit', 'Hyperliquid', 'Kraken', 'Other'],
                                    index=['Binance', 'Bybit', 'OKX', 'Bitget', 'Deribit', 'Hyperliquid', 'Kraken', 'Other'].index(trade_row['exchange'])
                                        if trade_row['exchange'] in ['Binance', 'Bybit', 'OKX', 'Bitget', 'Deribit', 'Hyperliquid', 'Kraken', 'Other'] else 0)

                            e_strategy = st.selectbox("Strategy",
                                options=['Breakout', 'Range Reversion', 'Trend Continuation',
                                        'VWAP Mean Reversion', 'News Catalyst', 'Liquidity Sweep',
                                        'Pullback', 'Other'],
                                index=['Breakout', 'Range Reversion', 'Trend Continuation',
                                      'VWAP Mean Reversion', 'News Catalyst', 'Liquidity Sweep',
                                      'Pullback', 'Other'].index(trade_row['setup_strategy'])
                                    if trade_row['setup_strategy'] in ['Breakout', 'Range Reversion', 'Trend Continuation',
                                      'VWAP Mean Reversion', 'News Catalyst', 'Liquidity Sweep',
                                      'Pullback', 'Other'] else 0)

                            e_compliance = st.slider("System Compliance", 1, 5, int(trade_row['system_compliance']))
                            e_confidence = st.slider("Confidence", 1, 5, int(trade_row['confidence']))

                            update_submitted = st.form_submit_button("💾 Update Trade", use_container_width=True)

                            if update_submitted:
                                # Prepare update data
                                e_entry_dt = BERLIN_TZ.localize(datetime.combine(e_entry_date, e_entry_time))
                                e_exit_dt = None
                                if e_exit_date:
                                    e_exit_dt = BERLIN_TZ.localize(datetime.combine(e_exit_date, e_exit_time))

                                update_data = {
                                    'entry_ts': e_entry_dt,
                                    'exit_ts': e_exit_dt,
                                    'pair': e_pair,
                                    'direction': e_direction,
                                    'leverage_x': e_leverage,
                                    'position_notional': e_notional,
                                    'entry_price': e_entry_price,
                                    'stop_price': e_stop_price,
                                    'tp1': e_tp1 if e_tp1 > 0 else None,
                                    'tp2': e_tp2 if e_tp2 > 0 else None,
                                    'exit_price': e_exit_price if e_exit_price > 0 else None,
                                    'fees_usd': e_fees,
                                    'funding_usd': e_funding,
                                    'exchange': e_exchange,
                                    'setup_strategy': e_strategy,
                                    'system_compliance': e_compliance,
                                    'confidence': e_confidence,
                                    # Keep existing qualitative fields
                                    'market_context': trade_row['market_context'],
                                    'entry_rationale': trade_row['entry_rationale'],
                                    'trigger_confirmation': trade_row['trigger_confirmation'],
                                    'execution_notes': trade_row['execution_notes'],
                                    'emotional_state': trade_row['emotional_state'],
                                    'strategy_tags': trade_row['strategy_tags'],
                                    'market_tags': trade_row['market_tags'],
                                    'mistake_tag': trade_row['mistake_tag'],
                                    'screenshot_entry_url': trade_row['screenshot_entry_url'],
                                    'screenshot_exit_url': trade_row['screenshot_exit_url'],
                                }

                                if update_trade(selected_id, update_data):
                                    st.success("✅ Trade updated!")
                                    st.session_state.refresh += 1
                                    st.rerun()

                    # Show full details
                    with st.expander("📄 Full Trade Details", expanded=False):
                        for col in filtered_df.columns:
                            st.text(f"{col}: {trade_row[col]}")

    # ========================================================================
    # TAB 3: DASHBOARD
    # ========================================================================

    with tab3:
        st.header("Dashboard & Analytics")

        if filtered_df.empty:
            st.info("No trades to display. Add trades to see analytics.")
        else:
            # Calculate metrics
            total_trades = len(filtered_df)

            closed_trades = filtered_df[filtered_df['net_pnl_usd'].notna()]

            if not closed_trades.empty:
                wins = len(closed_trades[closed_trades['win_loss'] == 'Win'])
                win_rate = (wins / len(closed_trades)) * 100 if len(closed_trades) > 0 else 0

                net_pnl = closed_trades['net_pnl_usd'].sum()
                avg_r = closed_trades['r_multiple'].mean()
                expectancy = closed_trades['r_multiple'].mean()

                best_trade = closed_trades['net_pnl_usd'].max()
                worst_trade = closed_trades['net_pnl_usd'].min()
            else:
                win_rate = 0
                net_pnl = 0
                avg_r = 0
                expectancy = 0
                best_trade = 0
                worst_trade = 0

            # Top metrics cards
            st.subheader("Performance Overview")

            met_col1, met_col2, met_col3, met_col4 = st.columns(4)

            with met_col1:
                st.metric("Total Trades", total_trades)
                st.metric("Win Rate", f"{win_rate:.2f}%")

            with met_col2:
                st.metric("Net PnL", format_currency(net_pnl))
                st.metric("Best Trade", format_currency(best_trade))

            with met_col3:
                st.metric("Avg R", format_number(avg_r, 2))
                st.metric("Worst Trade", format_currency(worst_trade))

            with met_col4:
                st.metric("Expectancy (R)", format_number(expectancy, 2))

            st.divider()

            # ================================================================
            # EQUITY CURVE
            # ================================================================

            if not closed_trades.empty:
                st.subheader("📈 Equity Curve")

                equity_df = closed_trades.sort_values('exit_ts').copy()
                equity_df['cumulative_pnl'] = equity_df['net_pnl_usd'].cumsum()
                equity_df['equity'] = starting_balance + equity_df['cumulative_pnl']

                fig_equity = go.Figure()
                fig_equity.add_trace(go.Scatter(
                    x=equity_df['exit_ts'],
                    y=equity_df['equity'],
                    mode='lines',
                    name='Equity',
                    line=dict(color='#00D9FF', width=2)
                ))

                fig_equity.add_hline(
                    y=starting_balance,
                    line_dash="dash",
                    line_color="gray",
                    annotation_text="Starting Balance"
                )

                fig_equity.update_layout(
                    title="Account Equity Over Time",
                    xaxis_title="Date",
                    yaxis_title="Equity (USD)",
                    hovermode='x unified',
                    height=400
                )

                st.plotly_chart(fig_equity, use_container_width=True)

            st.divider()

            # ================================================================
            # PNL BY STRATEGY
            # ================================================================

            if not closed_trades.empty:
                st.subheader("📊 Performance by Strategy")

                strategy_stats = closed_trades.groupby('setup_strategy').agg({
                    'id': 'count',
                    'net_pnl_usd': 'sum',
                    'r_multiple': 'mean',
                    'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100
                }).reset_index()

                strategy_stats.columns = ['Strategy', 'Trades', 'Net PnL', 'Avg R', 'Win Rate %']

                # Bar chart
                fig_strategy = px.bar(
                    strategy_stats,
                    x='Strategy',
                    y='Net PnL',
                    title='Total PnL by Strategy',
                    color='Net PnL',
                    color_continuous_scale=['red', 'yellow', 'green']
                )

                st.plotly_chart(fig_strategy, use_container_width=True)

                # Table
                st.dataframe(
                    strategy_stats.style.format({
                        'Net PnL': '${:,.2f}',
                        'Avg R': '{:.2f}',
                        'Win Rate %': '{:.2f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            st.divider()

            # ================================================================
            # PERFORMANCE BY WEEKDAY
            # ================================================================

            if not closed_trades.empty:
                st.subheader("📅 Performance by Weekday")

                weekday_df = closed_trades.copy()
                weekday_df['weekday'] = weekday_df['entry_ts'].dt.day_name()

                weekday_stats = weekday_df.groupby('weekday').agg({
                    'id': 'count',
                    'net_pnl_usd': 'sum',
                    'r_multiple': 'mean',
                    'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100 if len(x) > 0 else 0
                }).reset_index()

                weekday_stats.columns = ['Weekday', 'Trades', 'Net PnL', 'Avg R', 'Win Rate %']

                # Order by weekday
                weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                weekday_stats['Weekday'] = pd.Categorical(weekday_stats['Weekday'], categories=weekday_order, ordered=True)
                weekday_stats = weekday_stats.sort_values('Weekday')

                fig_weekday = px.bar(
                    weekday_stats,
                    x='Weekday',
                    y='Net PnL',
                    title='PnL by Weekday',
                    color='Net PnL',
                    color_continuous_scale=['red', 'yellow', 'green']
                )

                st.plotly_chart(fig_weekday, use_container_width=True)

                st.dataframe(
                    weekday_stats.style.format({
                        'Net PnL': '${:,.2f}',
                        'Avg R': '{:.2f}',
                        'Win Rate %': '{:.2f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )

            st.divider()

            # ================================================================
            # PERFORMANCE BY HOUR
            # ================================================================

            if not closed_trades.empty:
                st.subheader("🕐 Performance by Entry Hour")

                hour_df = closed_trades.copy()
                hour_df['hour'] = hour_df['entry_ts'].dt.hour

                hour_stats = hour_df.groupby('hour').agg({
                    'id': 'count',
                    'net_pnl_usd': 'sum',
                    'r_multiple': 'mean',
                    'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100 if len(x) > 0 else 0
                }).reset_index()

                hour_stats.columns = ['Hour', 'Trades', 'Net PnL', 'Avg R', 'Win Rate %']

                fig_hour = px.bar(
                    hour_stats,
                    x='Hour',
                    y='Net PnL',
                    title='PnL by Entry Hour (Europe/Berlin)',
                    color='Net PnL',
                    color_continuous_scale=['red', 'yellow', 'green']
                )

                st.plotly_chart(fig_hour, use_container_width=True)

                st.dataframe(
                    hour_stats.style.format({
                        'Net PnL': '${:,.2f}',
                        'Avg R': '{:.2f}',
                        'Win Rate %': '{:.2f}%'
                    }),
                    use_container_width=True,
                    hide_index=True
                )


if __name__ == '__main__':
    main()
