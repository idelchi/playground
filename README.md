# Crypto Perpetuals Trading Journal

A comprehensive Streamlit application for logging, analyzing, and improving your cryptocurrency perpetual futures trading performance.

## Features

### 📝 Trade Logging
- **Comprehensive Trade Form**: Log all trade details including entry/exit times, prices, leverage, stops, and targets
- **Qualitative Analysis**: Document market context, entry rationale, emotional state, and execution notes
- **Auto-calculated Metrics**: Automatically computes PnL, R-multiples, risk amounts, and holding periods
- **Screenshot Links**: Attach entry and exit chart screenshots for visual review

### 📊 Trade Management
- **Filterable Table**: View and filter trades by date, pair, direction, exchange, strategy, and outcome
- **Inline Editing**: Edit any trade and automatically recompute derived metrics
- **Bulk Actions**: Delete multiple trades at once
- **CSV Import/Export**: Backup and restore your trading journal data

### 📈 Analytics Dashboard
- **Key Performance Metrics**: Win rate, net PnL, average R-multiple, expectancy, best/worst trades
- **Equity Curve**: Track your account growth from a customizable starting balance
- **Strategy Performance**: Analyze which setups work best for you
- **Time-based Analysis**: Discover your best trading days and hours
- **Visual Charts**: Interactive Plotly charts for all analytics

### 🎯 Trading Psychology
- **Mistake Tracking**: Tag and analyze common trading mistakes
- **System Compliance**: Rate how well you followed your trading plan (1-5)
- **Confidence Levels**: Track your confidence in each trade (1-5)
- **Emotional State**: Document your mindset during trade execution

## Installation

1. **Clone or download this repository**

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

## Usage

1. **Run the application**:
```bash
streamlit run app.py
```

2. **Access the app**: Your browser should automatically open to `http://localhost:8501`

3. **Start logging trades**:
   - Use the "📝 New Trade" tab to add trades
   - View and edit trades in the "📊 Trades" tab
   - Analyze performance in the "📈 Dashboard" tab
   - Import existing data via the "📤 Import" tab

## Database

- Trades are stored in a local SQLite database (`trades.db`)
- All timestamps are stored in UTC but displayed in Europe/Berlin timezone
- Derived fields (PnL, R-multiples, etc.) are automatically calculated and stored

## Data Model

Each trade includes:

### Raw Input Fields
- Entry/Exit timestamps
- Pair, direction, leverage
- Position size, entry/stop/exit prices
- Take profit levels (TP1, TP2)
- Fees and funding costs
- Exchange

### Qualitative Fields
- Setup/strategy type
- Market context
- Entry rationale and trigger confirmation
- Execution notes and emotional state
- Strategy and market tags
- Mistake categorization
- Screenshot URLs
- System compliance and confidence ratings

### Auto-Calculated Fields
- Quantity (position size in contracts)
- Gross PnL (before fees)
- Risk amount (based on stop loss)
- Net PnL (after fees and funding)
- PnL percentage
- R-multiple (risk-adjusted return)
- Win/Loss/Breakeven classification
- Holding period (hours)

## Calculation Logic

### Long Positions
- **Gross PnL** = (Exit Price - Entry Price) × Quantity
- **Risk** = (Entry Price - Stop Price) × Quantity

### Short Positions
- **Gross PnL** = (Entry Price - Exit Price) × Quantity
- **Risk** = (Stop Price - Entry Price) × Quantity

### Common Calculations
- **Net PnL** = Gross PnL - Fees - Funding
- **PnL %** = Net PnL / Position Notional
- **R-Multiple** = Net PnL / Risk Amount
- **Win/Loss** = Win if Net PnL > 0, Loss if < 0, else Breakeven

## CSV Import/Export

### Export
Click "📥 Export CSV" in the Trades tab to download all your trades as a CSV file.

### Import
1. Go to the "📤 Import" tab
2. Upload a CSV file
3. Map the CSV columns to database fields
4. Review the preview
5. Click "Import Trades"

**Note**: Required fields are marked with asterisk (*). The app will validate data before importing.

## Filters

Use the sidebar to filter your view:
- **Date Range**: Filter by entry date
- **Pairs**: Select specific trading pairs
- **Direction**: Long or Short
- **Exchange**: Filter by trading venue
- **Strategy**: Filter by setup type
- **Win/Loss**: View only winners, losers, or breakeven trades
- **Starting Balance**: Set your initial capital for equity curve calculation

## Tips for Best Results

1. **Be Consistent**: Log every trade immediately after closing
2. **Be Honest**: Document mistakes and emotional states truthfully
3. **Review Regularly**: Analyze your dashboard weekly to identify patterns
4. **Tag Properly**: Use consistent tags for better filtering and analysis
5. **Document Context**: Rich notes help you learn from both wins and losses
6. **Track Screenshots**: Visual records are invaluable for post-trade review

## Technical Stack

- **Frontend**: Streamlit
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: pandas
- **Visualization**: Plotly
- **Timezone**: pytz (Europe/Berlin)

## License

This is a personal trading journal tool. Use at your own discretion.

## Support

For issues or feature requests, please refer to the application documentation or modify the code to suit your needs.
