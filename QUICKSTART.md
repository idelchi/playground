# Quick Start Guide - Crypto Perpetuals Trading Journal

## Installation & Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- streamlit >= 1.28.0
- pandas >= 2.0.0
- plotly >= 5.17.0
- sqlalchemy >= 2.0.0
- pytz >= 2023.3

### 2. Run the Application

```bash
streamlit run app.py
```

The app will automatically:
- Create the SQLite database (`trades.db`) on first run
- Open in your browser at `http://localhost:8501`

## First Steps

### 1. Log Your First Trade

Click on the **"📝 New Trade"** tab and fill in:

**Minimum Required Fields:**
- Entry Timestamp (defaults to now)
- Pair (e.g., BTC/USDT)
- Direction (Long or Short)
- Leverage
- Position Notional (USD)
- Entry Price
- Stop Price
- Exchange
- Setup/Strategy

**For Closed Trades, also add:**
- Exit Timestamp
- Exit Price

**Optional but Recommended:**
- TP1, TP2 (take profit levels)
- Fees and Funding costs
- Market Context & Entry Rationale
- Emotional State
- Confidence (1-5) and System Compliance (1-5)

Click **"💾 Save Trade"** when done.

### 2. View Your Trades

Switch to the **"📊 Trades"** tab to see all your logged trades in a table.

**Features:**
- Export to CSV
- Edit any trade (recalculates metrics automatically)
- Delete trades
- View formatted data with proper currency/percentage formatting

### 3. Analyze Performance

Go to the **"📈 Dashboard"** tab to see:

**Key Metrics:**
- Total Trades
- Win Rate %
- Net PnL
- Average R-multiple
- Expectancy
- Best/Worst Trade

**Charts:**
- Equity Curve (starts from your defined Starting Balance)
- PnL by Strategy
- Performance by Weekday
- Performance by Hour

### 4. Filter Your Data

Use the **left sidebar** to filter trades by:
- Date Range
- Trading Pairs
- Direction (Long/Short)
- Exchange
- Strategy
- Win/Loss outcome

Adjust the **Starting Balance** to see how your equity curve would look.

### 5. Import Existing Data

If you have trades in a CSV file:

1. Go to the **"📤 Import"** tab
2. Upload your CSV file
3. Map columns to database fields
4. Review the preview
5. Click "Import Trades"

## Understanding Auto-Calculated Fields

When you save a trade, these fields are automatically calculated:

### Quantity
```
quantity = position_notional / entry_price
```

### Gross PnL
**Long:**
```
gross_pnl = (exit_price - entry_price) × quantity
```

**Short:**
```
gross_pnl = (entry_price - exit_price) × quantity
```

### Risk Amount
**Long:**
```
risk = (entry_price - stop_price) × quantity
```

**Short:**
```
risk = (stop_price - entry_price) × quantity
```

### Net PnL
```
net_pnl = gross_pnl - fees - funding
```

### PnL Percentage
```
pnl_pct = net_pnl / position_notional
```

### R-Multiple
```
r_multiple = net_pnl / risk
```
This tells you how many times your risk you made (or lost).

### Win/Loss Classification
- **Win**: Net PnL > 0
- **Loss**: Net PnL < 0
- **Breakeven**: Net PnL = 0

## Example Trade Entry

Here's a complete example of a winning long trade:

**Trade Details:**
- Entry: 2025-11-09 14:30 (Europe/Berlin)
- Exit: 2025-11-09 18:45 (Europe/Berlin)
- Pair: BTC/USDT
- Direction: Long
- Leverage: 5x
- Position: $1,000
- Entry Price: $50,000
- Stop Price: $49,500
- Exit Price: $51,000
- Fees: $2.00
- Funding: $0.50

**Auto-Calculated Results:**
- Quantity: 0.02 BTC
- Gross PnL: $20.00
- Risk: $10.00
- Net PnL: $17.50
- PnL %: 1.75%
- R-Multiple: 1.75R
- Win/Loss: Win
- Holding Period: 4.25 hours

**Qualitative:**
- Strategy: Breakout
- Market Context: "Strong uptrend with volume confirmation"
- Entry Rationale: "Broke above previous high with increasing volume"
- Confidence: 4/5
- System Compliance: 5/5

## Tips for Best Results

### 1. Be Consistent
Log every trade immediately after closing. Don't rely on memory.

### 2. Be Honest
Document mistakes, emotional states, and rule violations truthfully.

### 3. Use Tags
Create consistent tags for filtering:
- Strategy: `scalp, swing, trend-following`
- Market: `high-vol, ranging, trending, breakout`

### 4. Track Psychology
- Rate your confidence (1-5) before entering
- Document your emotional state during execution
- Tag mistakes to identify patterns

### 5. Review Regularly
- Weekly: Review your dashboard
- Look for patterns in win/loss by:
  - Time of day
  - Day of week
  - Strategy type
  - Mistake categories

### 6. Analyze Mistakes
Filter by specific mistake tags:
- FOMO Entry
- Moved Stop
- Overleverage
- No Confirmation

Identify which mistakes cost you the most.

## Advanced Features

### CSV Export/Import
**Export**: One-click download of all trades
**Import**: Upload CSV with flexible column mapping

### Inline Editing
Edit any field and metrics recalculate automatically.

### Multiple Filters
Combine filters to analyze specific scenarios:
- "Show me all Long trades on BTC/USDT from last month"
- "Show me all losses from Breakout strategy"
- "Show me trades taken on Monday mornings"

### Equity Curve
Visualize your account growth over time. Adjust starting balance to model different scenarios.

### Strategy Performance Table
See detailed stats for each strategy:
- Number of trades
- Win rate
- Average R-multiple
- Total net PnL

## Troubleshooting

### Application won't start
```bash
# Check if Streamlit is installed
streamlit --version

# If not, install dependencies
pip install -r requirements.txt
```

### Database error
Delete `trades.db` and restart the app. It will create a fresh database.

### Timezone issues
All timestamps are displayed in Europe/Berlin timezone but stored in UTC. If you need a different timezone, modify `BERLIN_TZ` in `app.py`.

### Import CSV fails
Ensure your CSV has at minimum these columns:
- entry_ts
- pair
- direction
- leverage_x
- position_notional
- entry_price
- stop_price
- exchange
- setup_strategy

## Data Backup

Your trades are stored in `trades.db`. To backup:

1. **CSV Export**: Use the Export button (recommended)
2. **Database Copy**: Copy the `trades.db` file

To restore:
1. Place `trades.db` in the app directory, or
2. Import your CSV backup

## Getting Help

- Check the README.md for detailed documentation
- Review this Quick Start guide
- Examine the example trade above
- All fields have helpful tooltips in the UI

## Next Steps

1. ✅ Install and run the app
2. ✅ Log your first trade
3. ✅ Explore the dashboard
4. ✅ Set up filters
5. ✅ Import historical trades (if any)
6. ✅ Start building your dataset
7. ✅ Review weekly to improve

**Remember**: The journal is only as valuable as the data you put in. Be thorough, be honest, and use it consistently!
