# Crypto Perpetuals Trading Journal

A comprehensive, single-page Streamlit application for logging, reviewing, and analyzing crypto perpetual futures trades. Built with SQLite for data persistence and Plotly for interactive visualizations.

## Features

### 📝 Trade Logging
- **Comprehensive trade metadata**: Entry/exit timestamps, pair, direction, leverage, position size, prices, fees, and funding
- **Trade thesis documentation**: Market context, entry rationale, trigger confirmation, execution notes, emotional state
- **Automatic calculation** of derived metrics: PnL, R-multiple, win/loss status, holding period
- **Tagging system** for strategies, market conditions, and mistakes
- **Screenshot links** for entry and exit charts

### 📊 Analytics Dashboard
- **Performance overview**: Total trades, win rate, net PnL, average R, expectancy
- **Equity curve**: Visualize account growth over time from a configurable starting balance
- **Strategy analysis**: Compare performance across different setups
- **Time-based insights**: Performance by weekday and hour of day
- **Interactive charts** with Plotly

### 🔍 Advanced Filtering
- Filter trades by date range, pair, direction, exchange, strategy, and outcome
- Multi-select filters for comprehensive data slicing
- Real-time dashboard updates based on active filters

### 💾 Data Management
- **CSV export/import** for backup and data portability
- **Inline editing** of trades with automatic recalculation of derived fields
- **Duplicate and delete** operations for trade management
- **SQLite persistence** (trades.db) - no data loss between sessions

## Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Setup

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### Running the Application

Start the Streamlit app:
```bash
streamlit run app.py
```

The app will open in your default browser at `http://localhost:8501`

### Adding Your First Trade

1. Navigate to the **"➕ New Trade"** tab
2. Fill in the trade metadata:
   - Entry date/time (Europe/Berlin timezone)
   - Trading pair (e.g., BTC/USDT)
   - Direction (Long/Short)
   - Leverage, position size, entry/stop prices
   - Optional: Exit details, take-profit levels, fees, funding
3. Document your trade thesis:
   - Setup/strategy type
   - Market context and entry rationale
   - Trigger confirmation and execution notes
   - Emotional state and tags
4. Set system compliance and confidence ratings (1-5)
5. Click **"💾 Save Trade"**

The app automatically calculates:
- Position quantity
- Gross and net PnL
- Risk in USD
- PnL percentage
- R-multiple
- Win/Loss status
- Holding period in hours

### Managing Trades

Go to the **"📋 Trades Table"** tab to:
- View all trades in a sortable table
- Export trades to CSV
- Import trades from CSV
- Edit individual trades (recalculates derived metrics)
- Duplicate trades for similar setups
- Delete trades

### Analyzing Performance

The **"📊 Dashboard"** tab provides:
- **Top metrics cards**: Quick overview of key statistics
- **Equity curve**: Cumulative PnL over time (set starting balance in sidebar)
- **Strategy breakdown**: Which setups perform best
- **Weekday analysis**: Identify your best trading days
- **Hourly performance**: Find optimal entry times

Use the **sidebar filters** to analyze specific subsets of your trades.

## Data Model

### Raw Input Fields
- `entry_ts`, `exit_ts` - Trade timestamps (stored in UTC, displayed in Europe/Berlin)
- `pair` - Trading pair (e.g., BTC/USDT)
- `direction` - Long or Short
- `leverage_x` - Leverage multiplier
- `position_notional` - Position size in USD
- `entry_price`, `stop_price`, `exit_price` - Price levels
- `tp1`, `tp2` - Take-profit targets (optional)
- `fees_usd`, `funding_usd` - Trading costs
- `exchange` - Trading venue
- `setup_strategy` - Trade setup type
- `market_context`, `entry_rationale`, etc. - Qualitative documentation
- `system_compliance`, `confidence` - Self-assessment (1-5 scale)

### Derived Fields (Auto-calculated)
- `quantity` = position_notional / entry_price
- `gross_pnl_usd` = price difference × quantity (direction-aware)
- `risk_usd` = distance to stop × quantity
- `net_pnl_usd` = gross_pnl - fees - funding
- `pnl_pct` = net_pnl / position_notional
- `r_multiple` = net_pnl / risk (reward-to-risk ratio)
- `win_loss` = Win/Loss/Breakeven
- `holding_period_hours` = exit_ts - entry_ts in hours

## Database

- **File**: `trades.db` (SQLite)
- **Location**: Same directory as app.py
- **Timezone**: Timestamps stored in UTC, displayed in Europe/Berlin
- **Backup**: Export to CSV regularly for safety

## Tips for Effective Journaling

1. **Be thorough with documentation**: The more context you provide, the more you'll learn from reviewing past trades
2. **Use tags consistently**: This helps identify patterns in your strategy performance
3. **Log emotions**: Understanding your emotional state helps identify psychological patterns
4. **Review weekly**: Use the dashboard to identify what's working and what needs improvement
5. **Track mistakes**: The mistake_tag field helps you avoid repeating errors
6. **Update open trades**: Add exit details when positions close to see complete metrics

## Technical Details

- **Framework**: Streamlit 1.28+
- **Database**: SQLAlchemy 2.0+ with SQLite
- **Data Processing**: pandas 2.0+
- **Visualization**: Plotly 5.14+
- **Timezone Handling**: pytz
- **File Format**: CSV for import/export

## Calculation Formulas

### Long Positions
- Gross PnL: `(exit_price - entry_price) × quantity`
- Risk: `(entry_price - stop_price) × quantity`

### Short Positions
- Gross PnL: `(entry_price - exit_price) × quantity`
- Risk: `(stop_price - entry_price) × quantity`

### Universal
- Net PnL: `gross_pnl - fees - funding`
- PnL %: `net_pnl / position_notional`
- R-multiple: `net_pnl / risk`

## Troubleshooting

**Database not persisting?**
- Ensure `trades.db` file has write permissions
- Check that you're running from the same directory

**Timezone issues?**
- All times are displayed in Europe/Berlin timezone
- Internally stored as UTC for consistency

**Import CSV not working?**
- Ensure CSV has proper headers matching the database schema
- Date columns should be parseable by pandas

**Charts not displaying?**
- Ensure you have closed trades (with exit_ts and exit_price)
- Check that filters aren't excluding all data

## License

This project is provided as-is for personal trading journal use.

## Disclaimer

This tool is for educational and record-keeping purposes only. It does not provide trading advice or guarantees of trading success. Trade at your own risk.
