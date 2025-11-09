"""
Crypto Perpetuals Trading Journal
A Streamlit app for logging, reviewing, and analyzing crypto perpetuals trades.

Timezone: Europe/Berlin
Database: SQLite (trades.db)
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, Float, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pytz
import io
import csv

# ============================================================================
# Configuration & Setup
# ============================================================================

st.set_page_config(
    page_title="Crypto Perp Trading Journal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Timezone setup
BERLIN_TZ = pytz.timezone('Europe/Berlin')

# Database setup
DATABASE_URL = "sqlite:///trades.db"
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()
Session = sessionmaker(bind=engine)

# ============================================================================
# Database Model
# ============================================================================

class Trade(Base):
    """SQLAlchemy model for trades table.

    Timestamps are stored in UTC and converted to Europe/Berlin for display.
    """
    __tablename__ = 'trades'

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Trade metadata (raw inputs)
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

    # Trade thesis & execution (qualitative)
    setup_strategy = Column(String, nullable=False)
    market_context = Column(Text, default="")
    entry_rationale = Column(Text, default="")
    trigger_confirmation = Column(Text, default="")
    execution_notes = Column(Text, default="")
    emotional_state = Column(Text, default="")
    strategy_tags = Column(String, default="")
    market_tags = Column(String, default="")
    mistake_tag = Column(String, default="")
    screenshot_entry_url = Column(String, default="")
    screenshot_exit_url = Column(String, default="")
    system_compliance = Column(Integer, default=3)
    confidence = Column(Integer, default=3)

    # Derived fields (computed and stored)
    quantity = Column(Float, nullable=True)
    gross_pnl_usd = Column(Float, nullable=True)
    risk_usd = Column(Float, nullable=True)
    net_pnl_usd = Column(Float, nullable=True)
    pnl_pct = Column(Float, nullable=True)
    r_multiple = Column(Float, nullable=True)
    win_loss = Column(String, nullable=True)  # Win/Loss/Breakeven
    holding_period_hours = Column(Float, nullable=True)

    # Audit timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(engine)

# ============================================================================
# Helper Functions for Calculations
# ============================================================================

def compute_derived_fields(trade_data):
    """
    Compute all derived fields from raw trade data.

    Args:
        trade_data: dict with trade fields

    Returns:
        dict with derived fields added/updated
    """
    data = trade_data.copy()

    # Extract key fields
    entry_price = data.get('entry_price')
    exit_price = data.get('exit_price')
    stop_price = data.get('stop_price')
    position_notional = data.get('position_notional')
    direction = data.get('direction')
    fees_usd = data.get('fees_usd', 0.0)
    funding_usd = data.get('funding_usd', 0.0)
    entry_ts = data.get('entry_ts')
    exit_ts = data.get('exit_ts')

    # Compute quantity
    if entry_price and position_notional:
        data['quantity'] = position_notional / entry_price
    else:
        data['quantity'] = None

    quantity = data['quantity']

    # Compute gross PnL
    if exit_price and quantity and entry_price:
        if direction == 'Long':
            data['gross_pnl_usd'] = (exit_price - entry_price) * quantity
        elif direction == 'Short':
            data['gross_pnl_usd'] = (entry_price - exit_price) * quantity
        else:
            data['gross_pnl_usd'] = None
    else:
        data['gross_pnl_usd'] = None

    # Compute risk
    if stop_price and quantity and entry_price:
        if direction == 'Long':
            data['risk_usd'] = (entry_price - stop_price) * quantity
        elif direction == 'Short':
            data['risk_usd'] = (stop_price - entry_price) * quantity
        else:
            data['risk_usd'] = None
    else:
        data['risk_usd'] = None

    # Compute net PnL
    gross_pnl = data['gross_pnl_usd']
    if gross_pnl is not None:
        data['net_pnl_usd'] = gross_pnl - fees_usd - funding_usd
    else:
        data['net_pnl_usd'] = None

    # Compute PnL %
    net_pnl = data['net_pnl_usd']
    if net_pnl is not None and position_notional:
        data['pnl_pct'] = net_pnl / position_notional
    else:
        data['pnl_pct'] = None

    # Compute R multiple
    risk = data['risk_usd']
    if net_pnl is not None and risk and risk != 0:
        data['r_multiple'] = net_pnl / risk
    else:
        data['r_multiple'] = None

    # Compute win/loss
    if net_pnl is not None:
        if net_pnl > 0:
            data['win_loss'] = 'Win'
        elif net_pnl < 0:
            data['win_loss'] = 'Loss'
        else:
            data['win_loss'] = 'Breakeven'
    else:
        data['win_loss'] = None

    # Compute holding period
    if entry_ts and exit_ts:
        if isinstance(entry_ts, str):
            entry_ts = pd.to_datetime(entry_ts)
        if isinstance(exit_ts, str):
            exit_ts = pd.to_datetime(exit_ts)
        delta = exit_ts - entry_ts
        data['holding_period_hours'] = delta.total_seconds() / 3600
    else:
        data['holding_period_hours'] = None

    return data

def localize_datetime(dt, from_tz='UTC'):
    """Convert datetime to Berlin timezone for display."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    return dt.astimezone(BERLIN_TZ)

def to_utc(dt):
    """Convert Berlin datetime to UTC for storage."""
    if dt is None:
        return None
    if isinstance(dt, str):
        dt = pd.to_datetime(dt)
    if dt.tzinfo is None:
        dt = BERLIN_TZ.localize(dt)
    return dt.astimezone(pytz.UTC).replace(tzinfo=None)

# ============================================================================
# Database Operations
# ============================================================================

def add_trade(trade_data):
    """Add a new trade to the database."""
    # Compute derived fields
    trade_data = compute_derived_fields(trade_data)

    # Convert timestamps to UTC
    trade_data['entry_ts'] = to_utc(trade_data['entry_ts'])
    if trade_data.get('exit_ts'):
        trade_data['exit_ts'] = to_utc(trade_data['exit_ts'])

    session = Session()
    try:
        trade = Trade(**trade_data)
        session.add(trade)
        session.commit()
        return True, "Trade added successfully!"
    except Exception as e:
        session.rollback()
        return False, f"Error adding trade: {str(e)}"
    finally:
        session.close()

def update_trade(trade_id, trade_data):
    """Update an existing trade."""
    # Compute derived fields
    trade_data = compute_derived_fields(trade_data)

    # Convert timestamps to UTC
    if 'entry_ts' in trade_data:
        trade_data['entry_ts'] = to_utc(trade_data['entry_ts'])
    if trade_data.get('exit_ts'):
        trade_data['exit_ts'] = to_utc(trade_data['exit_ts'])

    trade_data['updated_at'] = datetime.utcnow()

    session = Session()
    try:
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if trade:
            for key, value in trade_data.items():
                setattr(trade, key, value)
            session.commit()
            return True, "Trade updated successfully!"
        return False, "Trade not found"
    except Exception as e:
        session.rollback()
        return False, f"Error updating trade: {str(e)}"
    finally:
        session.close()

def delete_trades(trade_ids):
    """Delete trades by IDs."""
    session = Session()
    try:
        session.query(Trade).filter(Trade.id.in_(trade_ids)).delete(synchronize_session=False)
        session.commit()
        return True, f"Deleted {len(trade_ids)} trade(s)"
    except Exception as e:
        session.rollback()
        return False, f"Error deleting trades: {str(e)}"
    finally:
        session.close()

def get_all_trades():
    """Retrieve all trades as a DataFrame."""
    session = Session()
    try:
        trades = session.query(Trade).all()
        if not trades:
            return pd.DataFrame()

        # Convert to DataFrame
        data = []
        for trade in trades:
            trade_dict = {col.name: getattr(trade, col.name) for col in Trade.__table__.columns}
            data.append(trade_dict)

        df = pd.DataFrame(data)

        # Convert timestamps to Berlin timezone
        if 'entry_ts' in df.columns:
            df['entry_ts'] = pd.to_datetime(df['entry_ts']).apply(localize_datetime)
        if 'exit_ts' in df.columns:
            df['exit_ts'] = pd.to_datetime(df['exit_ts']).apply(localize_datetime)
        if 'created_at' in df.columns:
            df['created_at'] = pd.to_datetime(df['created_at']).apply(localize_datetime)
        if 'updated_at' in df.columns:
            df['updated_at'] = pd.to_datetime(df['updated_at']).apply(localize_datetime)

        return df
    finally:
        session.close()

def get_trade_by_id(trade_id):
    """Get a single trade by ID."""
    session = Session()
    try:
        trade = session.query(Trade).filter_by(id=trade_id).first()
        if trade:
            return {col.name: getattr(trade, col.name) for col in Trade.__table__.columns}
        return None
    finally:
        session.close()

# ============================================================================
# Streamlit UI Components
# ============================================================================

def render_sidebar_filters(df):
    """Render sidebar filters and return filtered dataframe."""
    st.sidebar.header("🔍 Filters")

    filters = {}

    # Starting balance
    st.sidebar.header("💰 Settings")
    filters['starting_balance'] = st.sidebar.number_input(
        "Starting Balance (USD)",
        min_value=0.0,
        value=10000.0,
        step=100.0,
        format="%.2f"
    )

    if df.empty:
        return df, filters

    # Date range filter
    st.sidebar.subheader("📅 Date Range")
    if 'entry_ts' in df.columns and not df['entry_ts'].isna().all():
        min_date = df['entry_ts'].min().date()
        max_date = df['entry_ts'].max().date()

        date_range = st.sidebar.date_input(
            "Entry Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date
        )
        if len(date_range) == 2:
            filters['date_range'] = date_range

    # Pair filter
    if 'pair' in df.columns:
        pairs = sorted(df['pair'].dropna().unique())
        if pairs:
            filters['pairs'] = st.sidebar.multiselect("Pairs", pairs, default=pairs)

    # Direction filter
    if 'direction' in df.columns:
        directions = df['direction'].dropna().unique()
        if len(directions) > 0:
            filters['direction'] = st.sidebar.multiselect("Direction", directions, default=list(directions))

    # Exchange filter
    if 'exchange' in df.columns:
        exchanges = sorted(df['exchange'].dropna().unique())
        if exchanges:
            filters['exchanges'] = st.sidebar.multiselect("Exchanges", exchanges, default=exchanges)

    # Strategy filter
    if 'setup_strategy' in df.columns:
        strategies = sorted(df['setup_strategy'].dropna().unique())
        if strategies:
            filters['strategies'] = st.sidebar.multiselect("Strategies", strategies, default=strategies)

    # Win/Loss filter
    if 'win_loss' in df.columns:
        win_loss_options = df['win_loss'].dropna().unique()
        if len(win_loss_options) > 0:
            filters['win_loss'] = st.sidebar.multiselect("Win/Loss", win_loss_options, default=list(win_loss_options))

    # Apply filters
    filtered_df = df.copy()

    if 'date_range' in filters and len(filters['date_range']) == 2:
        start_date, end_date = filters['date_range']
        filtered_df = filtered_df[
            (filtered_df['entry_ts'].dt.date >= start_date) &
            (filtered_df['entry_ts'].dt.date <= end_date)
        ]

    if 'pairs' in filters and filters['pairs']:
        filtered_df = filtered_df[filtered_df['pair'].isin(filters['pairs'])]

    if 'direction' in filters and filters['direction']:
        filtered_df = filtered_df[filtered_df['direction'].isin(filters['direction'])]

    if 'exchanges' in filters and filters['exchanges']:
        filtered_df = filtered_df[filtered_df['exchange'].isin(filters['exchanges'])]

    if 'strategies' in filters and filters['strategies']:
        filtered_df = filtered_df[filtered_df['setup_strategy'].isin(filters['strategies'])]

    if 'win_loss' in filters and filters['win_loss']:
        filtered_df = filtered_df[filtered_df['win_loss'].isin(filters['win_loss'])]

    return filtered_df, filters

def render_new_trade_form():
    """Render the new trade entry form."""
    with st.expander("➕ Log New Trade", expanded=False):
        with st.form("new_trade_form", clear_on_submit=True):
            st.subheader("Trade Metadata")

            col1, col2, col3 = st.columns(3)

            with col1:
                entry_ts = st.datetime_input(
                    "Entry Timestamp",
                    value=datetime.now(BERLIN_TZ),
                    help="Europe/Berlin timezone"
                )
                pair = st.text_input("Pair", value="BTC/USDT", placeholder="e.g., BTC/USDT")
                direction = st.selectbox("Direction", ["Long", "Short"])
                leverage_x = st.number_input("Leverage (x)", min_value=0.1, value=5.0, step=0.5, format="%.1f")

            with col2:
                exit_ts = st.datetime_input(
                    "Exit Timestamp (optional)",
                    value=None,
                    help="Leave empty if position is still open"
                )
                position_notional = st.number_input("Position Notional (USD)", min_value=0.0, value=1000.0, step=10.0, format="%.2f")
                entry_price = st.number_input("Entry Price", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                stop_price = st.number_input("Stop Price", min_value=0.0, value=0.0, step=0.01, format="%.8f")

            with col3:
                exchange = st.selectbox(
                    "Exchange",
                    ["Binance", "Bybit", "OKX", "Bitget", "Deribit", "Hyperliquid", "Kraken", "Other"]
                )
                tp1 = st.number_input("TP1 (optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                tp2 = st.number_input("TP2 (optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")
                exit_price = st.number_input("Exit Price (optional)", min_value=0.0, value=0.0, step=0.01, format="%.8f")

            col4, col5 = st.columns(2)
            with col4:
                fees_usd = st.number_input("Fees (USD)", value=0.0, step=0.01, format="%.2f", help="Can be negative")
            with col5:
                funding_usd = st.number_input("Funding (USD)", value=0.0, step=0.01, format="%.2f", help="Can be negative")

            st.subheader("Trade Thesis & Execution")

            col6, col7 = st.columns(2)

            with col6:
                setup_strategy = st.selectbox(
                    "Setup/Strategy",
                    ["Breakout", "Range Reversion", "Trend Continuation", "VWAP Mean Reversion",
                     "News Catalyst", "Liquidity Sweep", "Pullback", "Other"]
                )
                market_context = st.text_area("Market Context", height=100)
                entry_rationale = st.text_area("Entry Rationale", height=100)
                trigger_confirmation = st.text_area("Trigger/Confirmation", height=100)

            with col7:
                execution_notes = st.text_area("Execution Notes", height=100)
                emotional_state = st.text_area("Emotional State", height=100)
                strategy_tags = st.text_input("Strategy Tags (comma-separated)", placeholder="scalp, momentum, breakout")
                market_tags = st.text_input("Market Tags (comma-separated)", placeholder="high-vol, ranging, trending")

            col8, col9, col10 = st.columns(3)

            with col8:
                mistake_tag = st.selectbox(
                    "Mistake Tag (if any)",
                    ["", "Overleverage", "No Confirmation", "Moved Stop", "FOMO Entry",
                     "Revenge Trade", "Ignored Plan", "Late Entry", "Fatigue", "Other"]
                )

            with col9:
                system_compliance = st.slider("System Compliance", 1, 5, 3)

            with col10:
                confidence = st.slider("Confidence", 1, 5, 3)

            screenshot_entry_url = st.text_input("Screenshot Entry URL (optional)")
            screenshot_exit_url = st.text_input("Screenshot Exit URL (optional)")

            submitted = st.form_submit_button("💾 Save Trade", use_container_width=True)

            if submitted:
                # Validation
                if not pair:
                    st.error("Pair is required")
                    return
                if entry_price <= 0:
                    st.error("Entry price must be greater than 0")
                    return
                if position_notional <= 0:
                    st.error("Position notional must be greater than 0")
                    return

                # Prepare trade data
                trade_data = {
                    'entry_ts': entry_ts,
                    'exit_ts': exit_ts if exit_ts else None,
                    'pair': pair,
                    'direction': direction,
                    'leverage_x': leverage_x,
                    'position_notional': position_notional,
                    'entry_price': entry_price,
                    'stop_price': stop_price,
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

                success, message = add_trade(trade_data)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)

def format_currency(value):
    """Format value as currency."""
    if pd.isna(value) or value is None:
        return "—"
    return f"${value:,.2f}"

def format_percentage(value):
    """Format value as percentage."""
    if pd.isna(value) or value is None:
        return "—"
    return f"{value:.2%}"

def format_number(value, decimals=2):
    """Format number with specified decimals."""
    if pd.isna(value) or value is None:
        return "—"
    return f"{value:.{decimals}f}"

def render_trades_table(df):
    """Render trades table with inline editing capabilities."""
    st.header("📊 Trades Table")

    if df.empty:
        st.info("No trades logged yet. Use the form above to add your first trade.")
        return

    # CSV Export
    col1, col2, col3 = st.columns([1, 1, 4])
    with col1:
        csv_buffer = io.StringIO()
        df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Export CSV",
            data=csv_buffer.getvalue(),
            file_name=f"trades_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            st.rerun()

    # Display columns selection
    display_columns = [
        'id', 'entry_ts', 'exit_ts', 'pair', 'direction', 'exchange',
        'position_notional', 'entry_price', 'exit_price', 'leverage_x',
        'net_pnl_usd', 'pnl_pct', 'r_multiple', 'win_loss',
        'setup_strategy', 'holding_period_hours'
    ]

    # Filter to existing columns
    display_columns = [col for col in display_columns if col in df.columns]

    # Format DataFrame for display
    display_df = df[display_columns].copy()

    # Format specific columns
    if 'entry_ts' in display_df.columns:
        display_df['entry_ts'] = display_df['entry_ts'].dt.strftime('%Y-%m-%d %H:%M')
    if 'exit_ts' in display_df.columns:
        display_df['exit_ts'] = display_df['exit_ts'].apply(lambda x: x.strftime('%Y-%m-%d %H:%M') if pd.notna(x) else '—')
    if 'position_notional' in display_df.columns:
        display_df['position_notional'] = display_df['position_notional'].apply(format_currency)
    if 'entry_price' in display_df.columns:
        display_df['entry_price'] = display_df['entry_price'].apply(lambda x: format_number(x, 8))
    if 'exit_price' in display_df.columns:
        display_df['exit_price'] = display_df['exit_price'].apply(lambda x: format_number(x, 8))
    if 'net_pnl_usd' in display_df.columns:
        display_df['net_pnl_usd'] = display_df['net_pnl_usd'].apply(format_currency)
    if 'pnl_pct' in display_df.columns:
        display_df['pnl_pct'] = display_df['pnl_pct'].apply(format_percentage)
    if 'r_multiple' in display_df.columns:
        display_df['r_multiple'] = display_df['r_multiple'].apply(lambda x: format_number(x, 2))
    if 'holding_period_hours' in display_df.columns:
        display_df['holding_period_hours'] = display_df['holding_period_hours'].apply(lambda x: format_number(x, 2))

    # Display table
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400,
        hide_index=True
    )

    # Trade actions
    st.subheader("Trade Actions")

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        # Delete trades
        with st.expander("🗑️ Delete Trades"):
            trade_ids_to_delete = st.multiselect(
                "Select Trade IDs to delete",
                options=df['id'].tolist(),
                format_func=lambda x: f"ID {x} - {df[df['id']==x]['pair'].values[0]} {df[df['id']==x]['direction'].values[0]}"
            )
            if st.button("Delete Selected", type="primary"):
                if trade_ids_to_delete:
                    success, message = delete_trades(trade_ids_to_delete)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)

    with col_b:
        # Edit trade
        with st.expander("✏️ Edit Trade"):
            trade_id_to_edit = st.selectbox(
                "Select Trade to Edit",
                options=df['id'].tolist(),
                format_func=lambda x: f"ID {x} - {df[df['id']==x]['pair'].values[0]} {df[df['id']==x]['direction'].values[0]}"
            )
            if st.button("Edit Selected Trade"):
                st.session_state['editing_trade_id'] = trade_id_to_edit
                st.rerun()

    # Edit form
    if 'editing_trade_id' in st.session_state:
        render_edit_trade_form(st.session_state['editing_trade_id'])

def render_edit_trade_form(trade_id):
    """Render edit form for a specific trade."""
    trade = get_trade_by_id(trade_id)
    if not trade:
        st.error("Trade not found")
        del st.session_state['editing_trade_id']
        return

    st.subheader(f"Editing Trade ID: {trade_id}")

    with st.form(f"edit_trade_form_{trade_id}"):
        col1, col2, col3 = st.columns(3)

        with col1:
            entry_ts = st.datetime_input(
                "Entry Timestamp",
                value=localize_datetime(trade['entry_ts']) if trade['entry_ts'] else datetime.now(BERLIN_TZ)
            )
            pair = st.text_input("Pair", value=trade['pair'] or "")
            direction = st.selectbox("Direction", ["Long", "Short"], index=0 if trade['direction'] == 'Long' else 1)
            leverage_x = st.number_input("Leverage (x)", min_value=0.1, value=float(trade['leverage_x'] or 1.0), step=0.5, format="%.1f")

        with col2:
            exit_ts_value = localize_datetime(trade['exit_ts']) if trade.get('exit_ts') else None
            exit_ts = st.datetime_input("Exit Timestamp (optional)", value=exit_ts_value)
            position_notional = st.number_input("Position Notional (USD)", min_value=0.0, value=float(trade['position_notional'] or 0.0), step=10.0, format="%.2f")
            entry_price = st.number_input("Entry Price", min_value=0.0, value=float(trade['entry_price'] or 0.0), step=0.01, format="%.8f")
            stop_price = st.number_input("Stop Price", min_value=0.0, value=float(trade['stop_price'] or 0.0), step=0.01, format="%.8f")

        with col3:
            exchange = st.selectbox(
                "Exchange",
                ["Binance", "Bybit", "OKX", "Bitget", "Deribit", "Hyperliquid", "Kraken", "Other"],
                index=["Binance", "Bybit", "OKX", "Bitget", "Deribit", "Hyperliquid", "Kraken", "Other"].index(trade['exchange']) if trade['exchange'] in ["Binance", "Bybit", "OKX", "Bitget", "Deribit", "Hyperliquid", "Kraken", "Other"] else 0
            )
            tp1 = st.number_input("TP1 (optional)", min_value=0.0, value=float(trade['tp1'] or 0.0), step=0.01, format="%.8f")
            tp2 = st.number_input("TP2 (optional)", min_value=0.0, value=float(trade['tp2'] or 0.0), step=0.01, format="%.8f")
            exit_price = st.number_input("Exit Price (optional)", min_value=0.0, value=float(trade['exit_price'] or 0.0), step=0.01, format="%.8f")

        col4, col5 = st.columns(2)
        with col4:
            fees_usd = st.number_input("Fees (USD)", value=float(trade['fees_usd'] or 0.0), step=0.01, format="%.2f")
        with col5:
            funding_usd = st.number_input("Funding (USD)", value=float(trade['funding_usd'] or 0.0), step=0.01, format="%.2f")

        setup_strategy = st.selectbox(
            "Setup/Strategy",
            ["Breakout", "Range Reversion", "Trend Continuation", "VWAP Mean Reversion",
             "News Catalyst", "Liquidity Sweep", "Pullback", "Other"],
            index=["Breakout", "Range Reversion", "Trend Continuation", "VWAP Mean Reversion",
                   "News Catalyst", "Liquidity Sweep", "Pullback", "Other"].index(trade['setup_strategy']) if trade['setup_strategy'] in ["Breakout", "Range Reversion", "Trend Continuation", "VWAP Mean Reversion", "News Catalyst", "Liquidity Sweep", "Pullback", "Other"] else 0
        )

        col6, col7 = st.columns(2)
        with col6:
            market_context = st.text_area("Market Context", value=trade['market_context'] or "", height=100)
            entry_rationale = st.text_area("Entry Rationale", value=trade['entry_rationale'] or "", height=100)
        with col7:
            trigger_confirmation = st.text_area("Trigger/Confirmation", value=trade['trigger_confirmation'] or "", height=100)
            execution_notes = st.text_area("Execution Notes", value=trade['execution_notes'] or "", height=100)

        emotional_state = st.text_area("Emotional State", value=trade['emotional_state'] or "")

        col8, col9 = st.columns(2)
        with col8:
            strategy_tags = st.text_input("Strategy Tags", value=trade['strategy_tags'] or "")
            screenshot_entry_url = st.text_input("Screenshot Entry URL", value=trade['screenshot_entry_url'] or "")
        with col9:
            market_tags = st.text_input("Market Tags", value=trade['market_tags'] or "")
            screenshot_exit_url = st.text_input("Screenshot Exit URL", value=trade['screenshot_exit_url'] or "")

        col10, col11, col12 = st.columns(3)
        with col10:
            mistake_tag = st.selectbox(
                "Mistake Tag",
                ["", "Overleverage", "No Confirmation", "Moved Stop", "FOMO Entry",
                 "Revenge Trade", "Ignored Plan", "Late Entry", "Fatigue", "Other"],
                index=["", "Overleverage", "No Confirmation", "Moved Stop", "FOMO Entry",
                       "Revenge Trade", "Ignored Plan", "Late Entry", "Fatigue", "Other"].index(trade['mistake_tag']) if trade['mistake_tag'] in ["", "Overleverage", "No Confirmation", "Moved Stop", "FOMO Entry", "Revenge Trade", "Ignored Plan", "Late Entry", "Fatigue", "Other"] else 0
            )
        with col11:
            system_compliance = st.slider("System Compliance", 1, 5, int(trade['system_compliance'] or 3))
        with col12:
            confidence = st.slider("Confidence", 1, 5, int(trade['confidence'] or 3))

        col_submit, col_cancel = st.columns(2)

        with col_submit:
            submitted = st.form_submit_button("💾 Update Trade", use_container_width=True, type="primary")

        with col_cancel:
            cancelled = st.form_submit_button("❌ Cancel", use_container_width=True)

        if cancelled:
            del st.session_state['editing_trade_id']
            st.rerun()

        if submitted:
            trade_data = {
                'entry_ts': entry_ts,
                'exit_ts': exit_ts if exit_ts else None,
                'pair': pair,
                'direction': direction,
                'leverage_x': leverage_x,
                'position_notional': position_notional,
                'entry_price': entry_price,
                'stop_price': stop_price,
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

            success, message = update_trade(trade_id, trade_data)
            if success:
                st.success(message)
                del st.session_state['editing_trade_id']
                st.rerun()
            else:
                st.error(message)

def render_dashboard(df, starting_balance):
    """Render analytics dashboard."""
    st.header("📈 Dashboard")

    if df.empty:
        st.info("No data to display. Add some trades to see analytics.")
        return

    # Filter to closed trades for most metrics
    closed_df = df[df['exit_price'].notna()].copy()

    if closed_df.empty:
        st.warning("No closed trades yet. Close some positions to see full analytics.")
        return

    # KPI Cards
    st.subheader("Key Metrics")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_trades = len(closed_df)
        st.metric("Total Trades", total_trades)

    with col2:
        wins = len(closed_df[closed_df['win_loss'] == 'Win'])
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        st.metric("Win Rate", f"{win_rate:.1f}%")

    with col3:
        net_pnl = closed_df['net_pnl_usd'].sum()
        st.metric("Net PnL", format_currency(net_pnl))

    with col4:
        avg_r = closed_df['r_multiple'].mean()
        st.metric("Avg R", format_number(avg_r, 2))

    col5, col6, col7, col8 = st.columns(4)

    with col5:
        expectancy = closed_df['r_multiple'].dropna().mean()
        st.metric("Expectancy (R/trade)", format_number(expectancy, 2))

    with col6:
        best_trade = closed_df['net_pnl_usd'].max()
        st.metric("Best Trade", format_currency(best_trade))

    with col7:
        worst_trade = closed_df['net_pnl_usd'].min()
        st.metric("Worst Trade", format_currency(worst_trade))

    with col8:
        avg_holding = closed_df['holding_period_hours'].mean()
        st.metric("Avg Holding (hrs)", format_number(avg_holding, 2))

    st.divider()

    # Charts
    col_left, col_right = st.columns(2)

    with col_left:
        # Equity Curve
        st.subheader("💰 Equity Curve")

        equity_df = closed_df.sort_values('exit_ts').copy()
        equity_df['cumulative_pnl'] = equity_df['net_pnl_usd'].cumsum()
        equity_df['equity'] = starting_balance + equity_df['cumulative_pnl']

        fig_equity = go.Figure()
        fig_equity.add_trace(go.Scatter(
            x=equity_df['exit_ts'],
            y=equity_df['equity'],
            mode='lines+markers',
            name='Equity',
            line=dict(color='#00D4AA', width=2),
            fill='tonexty',
            fillcolor='rgba(0, 212, 170, 0.1)'
        ))
        fig_equity.add_hline(
            y=starting_balance,
            line_dash="dash",
            line_color="gray",
            annotation_text="Starting Balance"
        )
        fig_equity.update_layout(
            xaxis_title="Date",
            yaxis_title="Equity (USD)",
            hovermode='x unified',
            height=400
        )
        st.plotly_chart(fig_equity, use_container_width=True)

    with col_right:
        # PnL by Strategy
        st.subheader("📊 PnL by Strategy")

        strategy_stats = closed_df.groupby('setup_strategy').agg({
            'net_pnl_usd': 'sum',
            'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100,
            'r_multiple': 'mean',
            'id': 'count'
        }).reset_index()
        strategy_stats.columns = ['Strategy', 'Net PnL', 'Win %', 'Avg R', 'Trades']
        strategy_stats = strategy_stats.sort_values('Net PnL', ascending=True)

        fig_strategy = go.Figure()
        fig_strategy.add_trace(go.Bar(
            y=strategy_stats['Strategy'],
            x=strategy_stats['Net PnL'],
            orientation='h',
            marker=dict(
                color=strategy_stats['Net PnL'],
                colorscale='RdYlGn',
                showscale=False
            ),
            text=strategy_stats['Net PnL'].apply(lambda x: format_currency(x)),
            textposition='auto'
        ))
        fig_strategy.update_layout(
            xaxis_title="Net PnL (USD)",
            yaxis_title="Strategy",
            height=400
        )
        st.plotly_chart(fig_strategy, use_container_width=True)

        # Strategy table
        display_strategy_stats = strategy_stats.copy()
        display_strategy_stats['Win %'] = display_strategy_stats['Win %'].apply(lambda x: f"{x:.1f}%")
        display_strategy_stats['Avg R'] = display_strategy_stats['Avg R'].apply(lambda x: format_number(x, 2))
        display_strategy_stats['Net PnL'] = display_strategy_stats['Net PnL'].apply(format_currency)
        st.dataframe(display_strategy_stats, use_container_width=True, hide_index=True)

    st.divider()

    # Performance by Time
    col_day, col_hour = st.columns(2)

    with col_day:
        # Performance by Weekday
        st.subheader("📅 Performance by Weekday")

        weekday_df = closed_df.copy()
        weekday_df['weekday'] = weekday_df['entry_ts'].dt.day_name()
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        weekday_stats = weekday_df.groupby('weekday').agg({
            'net_pnl_usd': 'sum',
            'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100,
            'r_multiple': 'mean',
            'id': 'count'
        }).reset_index()
        weekday_stats.columns = ['Weekday', 'Net PnL', 'Win %', 'Avg R', 'Trades']

        # Sort by weekday order
        weekday_stats['weekday_num'] = weekday_stats['Weekday'].apply(lambda x: weekday_order.index(x) if x in weekday_order else 7)
        weekday_stats = weekday_stats.sort_values('weekday_num')

        fig_weekday = go.Figure()
        fig_weekday.add_trace(go.Bar(
            x=weekday_stats['Weekday'],
            y=weekday_stats['Net PnL'],
            marker=dict(
                color=weekday_stats['Net PnL'],
                colorscale='RdYlGn',
                showscale=False
            ),
            text=weekday_stats['Net PnL'].apply(lambda x: format_currency(x)),
            textposition='auto'
        ))
        fig_weekday.update_layout(
            xaxis_title="Weekday",
            yaxis_title="Net PnL (USD)",
            height=350
        )
        st.plotly_chart(fig_weekday, use_container_width=True)

        # Weekday table
        display_weekday_stats = weekday_stats[['Weekday', 'Trades', 'Win %', 'Avg R', 'Net PnL']].copy()
        display_weekday_stats['Win %'] = display_weekday_stats['Win %'].apply(lambda x: f"{x:.1f}%")
        display_weekday_stats['Avg R'] = display_weekday_stats['Avg R'].apply(lambda x: format_number(x, 2))
        display_weekday_stats['Net PnL'] = display_weekday_stats['Net PnL'].apply(format_currency)
        st.dataframe(display_weekday_stats, use_container_width=True, hide_index=True)

    with col_hour:
        # Performance by Hour
        st.subheader("🕐 Performance by Hour (Entry)")

        hour_df = closed_df.copy()
        hour_df['hour'] = hour_df['entry_ts'].dt.hour

        hour_stats = hour_df.groupby('hour').agg({
            'net_pnl_usd': 'sum',
            'win_loss': lambda x: (x == 'Win').sum() / len(x) * 100,
            'r_multiple': 'mean',
            'id': 'count'
        }).reset_index()
        hour_stats.columns = ['Hour', 'Net PnL', 'Win %', 'Avg R', 'Trades']

        fig_hour = go.Figure()
        fig_hour.add_trace(go.Bar(
            x=hour_stats['Hour'],
            y=hour_stats['Net PnL'],
            marker=dict(
                color=hour_stats['Net PnL'],
                colorscale='RdYlGn',
                showscale=False
            ),
            text=hour_stats['Net PnL'].apply(lambda x: format_currency(x)),
            textposition='auto'
        ))
        fig_hour.update_layout(
            xaxis_title="Hour of Day (24h)",
            yaxis_title="Net PnL (USD)",
            height=350,
            xaxis=dict(tickmode='linear', tick0=0, dtick=2)
        )
        st.plotly_chart(fig_hour, use_container_width=True)

        # Hour table (top 10)
        display_hour_stats = hour_stats.sort_values('Net PnL', ascending=False).head(10).copy()
        display_hour_stats['Win %'] = display_hour_stats['Win %'].apply(lambda x: f"{x:.1f}%")
        display_hour_stats['Avg R'] = display_hour_stats['Avg R'].apply(lambda x: format_number(x, 2))
        display_hour_stats['Net PnL'] = display_hour_stats['Net PnL'].apply(format_currency)
        st.dataframe(display_hour_stats, use_container_width=True, hide_index=True)

def render_csv_import():
    """Render CSV import functionality."""
    st.header("📤 Import Trades from CSV")

    uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])

    if uploaded_file is not None:
        try:
            # Read CSV
            import_df = pd.read_csv(uploaded_file)

            st.subheader("Preview")
            st.dataframe(import_df.head(10), use_container_width=True)

            st.info(f"Found {len(import_df)} rows in the CSV file.")

            # Column mapping
            st.subheader("Column Mapping")
            st.write("Map CSV columns to database fields (leave empty to skip):")

            required_fields = ['entry_ts', 'pair', 'direction', 'leverage_x', 'position_notional',
                             'entry_price', 'stop_price', 'exchange', 'setup_strategy']

            col_map = {}

            col1, col2, col3 = st.columns(3)
            csv_columns = [''] + list(import_df.columns)

            with col1:
                for field in required_fields[:5]:
                    col_map[field] = st.selectbox(
                        f"{field} *",
                        csv_columns,
                        index=csv_columns.index(field) if field in csv_columns else 0
                    )

            with col2:
                for field in required_fields[5:]:
                    col_map[field] = st.selectbox(
                        f"{field} *",
                        csv_columns,
                        index=csv_columns.index(field) if field in csv_columns else 0
                    )

            with col3:
                optional_fields = ['exit_ts', 'tp1', 'tp2', 'exit_price', 'fees_usd', 'funding_usd']
                for field in optional_fields:
                    col_map[field] = st.selectbox(
                        field,
                        csv_columns,
                        index=csv_columns.index(field) if field in csv_columns else 0
                    )

            if st.button("Import Trades", type="primary"):
                # Validate required fields
                missing_fields = [f for f in required_fields if not col_map.get(f)]
                if missing_fields:
                    st.error(f"Missing required fields: {', '.join(missing_fields)}")
                else:
                    success_count = 0
                    error_count = 0

                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for idx, row in import_df.iterrows():
                        try:
                            trade_data = {}

                            # Map fields
                            for db_field, csv_field in col_map.items():
                                if csv_field and csv_field in row:
                                    value = row[csv_field]
                                    if pd.notna(value):
                                        trade_data[db_field] = value

                            # Add default values for fields not in mapping
                            if 'market_context' not in trade_data:
                                trade_data['market_context'] = ""
                            if 'entry_rationale' not in trade_data:
                                trade_data['entry_rationale'] = ""
                            if 'trigger_confirmation' not in trade_data:
                                trade_data['trigger_confirmation'] = ""
                            if 'execution_notes' not in trade_data:
                                trade_data['execution_notes'] = ""
                            if 'emotional_state' not in trade_data:
                                trade_data['emotional_state'] = ""
                            if 'strategy_tags' not in trade_data:
                                trade_data['strategy_tags'] = ""
                            if 'market_tags' not in trade_data:
                                trade_data['market_tags'] = ""
                            if 'mistake_tag' not in trade_data:
                                trade_data['mistake_tag'] = ""
                            if 'screenshot_entry_url' not in trade_data:
                                trade_data['screenshot_entry_url'] = ""
                            if 'screenshot_exit_url' not in trade_data:
                                trade_data['screenshot_exit_url'] = ""
                            if 'system_compliance' not in trade_data:
                                trade_data['system_compliance'] = 3
                            if 'confidence' not in trade_data:
                                trade_data['confidence'] = 3
                            if 'fees_usd' not in trade_data:
                                trade_data['fees_usd'] = 0.0
                            if 'funding_usd' not in trade_data:
                                trade_data['funding_usd'] = 0.0

                            success, message = add_trade(trade_data)
                            if success:
                                success_count += 1
                            else:
                                error_count += 1
                                st.warning(f"Row {idx + 1}: {message}")

                        except Exception as e:
                            error_count += 1
                            st.warning(f"Row {idx + 1}: {str(e)}")

                        # Update progress
                        progress = (idx + 1) / len(import_df)
                        progress_bar.progress(progress)
                        status_text.text(f"Processing: {idx + 1}/{len(import_df)}")

                    progress_bar.empty()
                    status_text.empty()

                    st.success(f"Import complete! Successfully imported {success_count} trades. {error_count} errors.")

                    if success_count > 0:
                        if st.button("Refresh Data"):
                            st.rerun()

        except Exception as e:
            st.error(f"Error reading CSV file: {str(e)}")

# ============================================================================
# Main Application
# ============================================================================

def main():
    st.title("📈 Crypto Perpetuals Trading Journal")
    st.markdown("*Track, analyze, and improve your perpetual futures trading*")

    # Load data
    df = get_all_trades()

    # Sidebar filters
    filtered_df, filters = render_sidebar_filters(df)
    starting_balance = filters.get('starting_balance', 10000.0)

    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📝 New Trade", "📊 Trades", "📈 Dashboard", "📤 Import"])

    with tab1:
        render_new_trade_form()

    with tab2:
        render_trades_table(filtered_df)

    with tab3:
        render_dashboard(filtered_df, starting_balance)

    with tab4:
        render_csv_import()

    # Footer
    st.divider()
    st.caption(f"💾 Database: trades.db | 🕐 Timezone: Europe/Berlin | Total Trades: {len(df)}")

if __name__ == "__main__":
    main()
