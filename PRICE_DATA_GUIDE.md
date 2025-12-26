# Polymarket Token Price Data Retrieval Guide

## Overview

This guide explains how to retrieve token price data from Polymarket markets with different levels of granularity.

**Key Finding**: The finest granularity available is **individual trade executions (tick data)**, accessible only via WebSocket.

---

## Available Granularities

### 1. Snapshot (Instant)
**What**: Current price at a single point in time
**Source**: REST API `/price` endpoint
**Granularity**: One data point
**Refresh**: Manual (on-demand)

**When to use**:
- Displaying current market price
- Quick price checks
- Dashboard displays

**How to get**:
```bash
# Using price_retriever.py
python price_retriever.py snapshot --market-id <MARKET_ID>

# Or programmatically
from api_client import PolymarketAPIClient
client = PolymarketAPIClient()
price_data = client.get_price(token_id)
# Returns: {'price': 0.5234, 'mid': 0.5200}
```

---

### 2. Polling Series (Seconds to Minutes)
**What**: Price snapshots collected at regular intervals
**Source**: REST API `/price` endpoint (repeated calls)
**Granularity**: Configurable (typically 1-60 seconds)
**Refresh**: Automated polling

**When to use**:
- Monitoring price changes over time
- Building low-frequency price charts
- Alerting on price movements

**How to get**:
```bash
# Poll every 5 seconds for 5 minutes
python price_retriever.py poll --market-id <MARKET_ID> --duration 300 --interval 5

# Export to CSV
python price_retriever.py poll --market-id <MARKET_ID> --duration 300 --interval 5 --output prices.csv
```

**CSV Output**:
```
timestamp,market_id,question,outcome_up,outcome_down,price_up,price_down,spread
2025-12-26T00:00:00Z,996577,Bitcoin Up or Down,Up,Down,0.5234,0.4766,0.0468
2025-12-26T00:00:05Z,996577,Bitcoin Up or Down,Up,Down,0.5241,0.4759,0.0482
...
```

**Limitations**:
- Misses trades that happen between polls
- Rate limiting: minimum 0.5s between requests
- Not suitable for high-frequency analysis

---

### 3. Tick Data (Individual Trades) ⭐ **FINEST GRANULARITY**
**What**: Every single trade execution with exact timing
**Source**: WebSocket API (real-time stream)
**Granularity**: Individual trades (millisecond timestamps)
**Refresh**: Real-time (no delay)

**When to use**:
- Building candlestick/OHLC charts
- Volume analysis
- High-frequency trading strategies
- Backtesting
- Reconstructing exact price action

**How to get**:
```bash
# Start recording trades
python tick_tool.py record --market-ids <MARKET_ID>

# Or auto-discover unresolved markets from cache
python tick_tool.py record --from-cache --filter-unresolved --min-volume 1000

# Query recorded trades
python tick_tool.py query --market-id <MARKET_ID>

# Export to CSV
python tick_tool.py export --market-id <MARKET_ID> --output trades.csv
```

**Trade Data Structure**:
```python
{
    'timestamp': '2025-12-26T00:15:30.123Z',  # Exact execution time
    'market_id': '996577',
    'asset_id': '96335067832619596...',  # Token ID
    'side': 'BUY',  # or 'SELL'
    'outcome': 'UP',  # or 'DOWN'
    'price': 0.5234,
    'size': 100.50,
    'fee_rate_bps': 10,
    'source': 'websocket'
}
```

**Limitations**:
- **No historical backfill**: REST `/trades` endpoint requires authentication (401 Unauthorized)
- **Must record in real-time**: Start recording NOW to build historical database
- **Cannot retrieve past trades**: No public access to historical tick data

---

## Summary Table

| Granularity | Resolution | Source | Historical? | Auth Required? | Best For |
|-------------|-----------|--------|-------------|----------------|----------|
| **Snapshot** | Single point | REST `/price` | No | No ✅ | Current price display |
| **Polling** | 1-60 seconds | REST `/price` (loop) | User-created | No ✅ | Price monitoring |
| **Tick Data** | Per trade | WebSocket `last_trade_price` | User-created | No ✅ | Precise analysis, charting |

---

## Workflow: Given a Market ID, Get Price Data

### Step 1: Get Market Information
```bash
# Show market details and token IDs
python price_retriever.py info --market-id 996577
```

Output:
```
MARKET INFORMATION
======================================================================
Market ID:  996577
Question:   Bitcoin Up or Down - December 23, 4:10PM-4:15PM ET
Status:     Open
Volume:     $12,345.67

----------------------------------------------------------------------
TOKENS
----------------------------------------------------------------------
Outcome 1: Up
Token ID:  96335067832619596263476394965563507657401324223032703267023353422994551721776

Outcome 2: Down
Token ID:  111599321245469042312348515264237995024098552374708904114333636985258638050285
```

### Step 2: Choose Your Granularity

**Option A: Quick Price Check**
```bash
python price_retriever.py snapshot --market-id 996577
```

**Option B: Monitor Over Time**
```bash
# Poll for 1 hour, every 10 seconds
python price_retriever.py poll --market-id 996577 --duration 3600 --interval 10 --output prices.csv
```

**Option C: Record All Trades (Finest Granularity)**
```bash
# Start recording (runs until Ctrl+C)
python tick_tool.py record --market-ids 996577

# Later: Query trades for analysis
python tick_tool.py query --market-id 996577 --output all_trades.csv
```

### Step 3: Analyze Price Data

**From Snapshot**: Single data point, use for display

**From Polling Series**: Time series CSV
- Load into pandas/Excel
- Calculate price changes over time
- Plot basic price chart

**From Tick Data**: Complete trade history
- Aggregate into candles (1m, 5m, 1h)
- Calculate volume-weighted prices
- Build orderflow analysis
- Backtest trading strategies

---

## Constructing Candlesticks from Tick Data

Once you have tick data, you can build candlestick charts:

```python
from tick_database import TickDatabase
import pandas as pd

# Get all trades for a market
db = TickDatabase()
trades = db.get_trades_by_market(
    '996577',
    start_time='2025-12-26T00:00:00',
    end_time='2025-12-26T23:59:59'
)

# Convert to DataFrame
df = pd.DataFrame(trades)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.set_index('timestamp')

# Resample into 1-minute candles
candles_1m = df.groupby(pd.Grouper(freq='1min')).agg({
    'price': ['first', 'max', 'min', 'last'],  # OHLC
    'size': 'sum'  # Volume
})

# Resample into 5-minute candles
candles_5m = df.groupby(pd.Grouper(freq='5min')).agg({
    'price': ['first', 'max', 'min', 'last'],
    'size': 'sum'
})

# Export
candles_1m.to_csv('candles_1min.csv')
candles_5m.to_csv('candles_5min.csv')
```

---

## API Endpoints Reference

### REST API (CLOB)
Base URL: `https://clob.polymarket.com`

#### `/price` ✅ PUBLIC
```
GET /price?token_id=<TOKEN_ID>&side=buy

Response:
{
  "price": 0.5234,
  "mid": 0.5200
}
```

#### `/book` ⚠️ UNCERTAIN
```
GET /book?token_id=<TOKEN_ID>

Response:
{
  "bids": [{"price": 0.52, "size": 100}, ...],
  "asks": [{"price": 0.53, "size": 150}, ...]
}
```
May not be publicly available for all markets.

#### `/trades` ❌ REQUIRES AUTH
```
GET /trades?token_id=<TOKEN_ID>&limit=100

Response: 401 Unauthorized without API key
```

### WebSocket API ✅ PUBLIC
Endpoint: `wss://ws-subscriptions-clob.polymarket.com/ws/market`

**Events received**:
- `book` - Orderbook snapshots
- `price_change` - Order placement/cancellation
- `last_trade_price` - **Trade executions (TICK DATA)**
- `tick_size_change` - Tick size updates

**Trade event structure**:
```json
{
  "event_type": "last_trade_price",
  "asset_id": "96335067832619596...",
  "price": "0.5234",
  "size": "100.50",
  "side": "BUY",
  "fee_rate_bps": "10",
  "timestamp": "2025-12-26T00:15:30.123Z",
  "market": "996577"
}
```

---

## Rate Limiting

**REST API**:
- Minimum delay: 0.5 seconds between requests (configured in `config.py`)
- Automatic exponential backoff on 429 errors: [1s, 2s, 5s, 10s, 30s]
- Maximum retries: 3

**WebSocket API**:
- No rate limiting (event-driven, server-pushed)
- Auto-reconnect on disconnect

---

## Tools Available

### 1. price_retriever.py
**Purpose**: Get current prices or build polling-based price series

**Commands**:
```bash
# Snapshot
python price_retriever.py snapshot --market-id <ID>

# Poll
python price_retriever.py poll --market-id <ID> --duration 300 --interval 5

# Info
python price_retriever.py info --market-id <ID>
```

### 2. tick_tool.py
**Purpose**: Record and query tick-level trade data

**Commands**:
```bash
# Record
python tick_tool.py record --market-ids <ID1>,<ID2>
python tick_tool.py record --from-cache --filter-unresolved

# Query
python tick_tool.py query --market-id <ID> --output trades.csv

# Export
python tick_tool.py export --market-id <ID> --output trades.csv

# Summary
python tick_tool.py summary --market-id <ID>

# List
python tick_tool.py list
```

### 3. live_monitor.py
**Purpose**: Real-time terminal UI for market monitoring

```bash
python live_monitor.py --market-id <ID> --interval 5
```

---

## Recommendations by Use Case

### I want to display current prices on a dashboard
→ Use `price_retriever.py snapshot` and poll every 5-10 seconds

### I want to analyze price movements over the past hour
→ Use `price_retriever.py poll --duration 3600 --interval 5 --output prices.csv`

### I want to build candlestick charts
→ Start recording with `tick_tool.py record` NOW, then query tick data later

### I want historical data from last week
→ ❌ Not available via public API
→ ✅ Start recording now to build future historical database

### I want to backtest a trading strategy
→ Start recording with `tick_tool.py record` for weeks/months to build dataset

---

## Important Notes

### Historical Data Limitation
⚠️ **Critical**: Historical trade data is NOT publicly accessible via REST API (returns 401 Unauthorized)

**Impact**:
- Cannot retrieve past tick data
- Cannot backfill price history
- Must start recording NOW to build database

**Solution**: Start recording active markets immediately using `tick_tool.py record`

### Data Completeness
For tick data recording:
- ✅ Captures every trade from the moment you start recording
- ✅ Real-time with millisecond precision
- ❌ No data from before you started recording
- ❌ Lost trades during downtime/disconnects

**Best Practice**: Run tick recorder continuously in background for important markets

---

## Example Workflows

### Workflow 1: Quick Price Check
```bash
python price_retriever.py snapshot --market-id 996577
```
Duration: ~2 seconds
Output: Terminal display with current prices

### Workflow 2: Build 1-Hour Price Chart
```bash
# Collect data (runs for 1 hour)
python price_retriever.py poll --market-id 996577 --duration 3600 --interval 10 --output prices_1h.csv

# Analyze in spreadsheet or pandas
import pandas as pd
df = pd.read_csv('prices_1h.csv')
df['timestamp'] = pd.to_datetime(df['timestamp'])
df.plot(x='timestamp', y=['price_up', 'price_down'])
```

### Workflow 3: Record Tick Data for Analysis
```bash
# Terminal 1: Start recording (leave running)
python tick_tool.py record --market-ids 996577,996578,996579

# Terminal 2: After some time, query data
python tick_tool.py query --market-id 996577 --output trades.csv

# Analyze
python -c "
from tick_database import TickDatabase
db = TickDatabase()
summary = db.get_market_summary('996577')
print(f'Total trades: {summary[\"total_trades\"]}')
print(f'Total volume: {summary[\"total_volume\"]:.2f}')
"
```

---

## Files

**Core API Client**:
- `api_client.py` - REST API wrapper with rate limiting

**Price Retrieval**:
- `price_retriever.py` - **NEW** - Snapshot and polling tool
- `tick_tool.py` - Tick data recording and querying
- `tick_database.py` - SQLite storage for tick data
- `tick_recorder.py` - WebSocket to database recorder

**WebSocket**:
- `websocket_client.py` - WebSocket connection manager

**Monitoring**:
- `live_monitor.py` - Real-time terminal UI

**Configuration**:
- `config.py` - API endpoints, rate limits, database paths

**Documentation**:
- `CLAUDE.md` - Comprehensive project documentation
- `PRICE_DATA_GUIDE.md` - This file

---

## Next Steps

1. **Test snapshot**: `python price_retriever.py snapshot --market-id <ID>`
2. **Start recording tick data**: `python tick_tool.py record --from-cache --filter-unresolved`
3. **Build price series**: Choose polling or tick data based on your needs
4. **Analyze**: Use pandas, Excel, or your preferred tools

For detailed API documentation and troubleshooting, see `CLAUDE.md`.
