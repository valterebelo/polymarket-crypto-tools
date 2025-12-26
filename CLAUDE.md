# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository contains two focused tools for working with Polymarket crypto markets:

1. **crypto_market_finder.py** - Find and display resolved/unresolved crypto markets with metadata
2. **live_monitor.py** - Real-time terminal monitoring of markets with prices, orderbook, and volume

## Package Manager

This project uses [UV](https://docs.astral.sh/uv/) for dependency management:

```bash
# Install dependencies
uv sync

# Run scripts directly
uv run python crypto_market_finder.py --unresolved
uv run python live_monitor.py --token-up <ID> --token-down <ID>

# Or use installed commands
uv run market-finder --help
uv run live-monitor --help
```

## Quick Start

### Find Crypto Markets

```bash
# Find all crypto markets (newest first by default)
uv run python crypto_market_finder.py --all

# Find only unresolved markets
uv run python crypto_market_finder.py --unresolved

# Find short-term "Up or Down" markets (15min, 1hr, 4hr)
uv run python crypto_market_finder.py --unresolved --short-term

# Filter by minimum volume
uv run python crypto_market_finder.py --unresolved --min-volume 1000

# Date range filtering (YYYY-MM-DD format)
uv run python crypto_market_finder.py --start-date 2025-12-01 --end-date 2025-12-22

# Fetch more markets (default: 5000, API returns 500 per request)
uv run python crypto_market_finder.py --unresolved --max-markets 10000

# Get oldest markets first instead of newest
uv run python crypto_market_finder.py --oldest-first --max-markets 2000

# Custom output file
uv run python crypto_market_finder.py --output my_markets.csv
```

### Monitor a Market Live

```bash
# Basic monitoring (copy token IDs from market finder output)
uv run python live_monitor.py --token-up <TOKEN_ID_1> --token-down <TOKEN_ID_2>

# Custom poll interval (default: 5s)
uv run python live_monitor.py --token-up <ID1> --token-down <ID2> --interval 10

# Named market for display
uv run python live_monitor.py --token-up <ID1> --token-down <ID2> --market-name "BTC 1hr"
```

## Architecture

### File Structure

```
/Users/valter/polymarket/
├── config.py                     # Shared configuration (API URLs, keywords, settings)
├── api_client.py                 # API wrapper with rate limiting and retries
├── display_utils.py              # Terminal UI formatting utilities
├── crypto_market_finder.py       # Main script: Find crypto markets
├── live_monitor.py               # Main script: Live market monitoring
├── pyproject.toml                # Dependencies: requests, pandas
├── CLAUDE.md                     # This file
├── README.md                     # User documentation
├── data/                         # Output directory
│   └── crypto_markets_cache.csv  # Cached crypto markets
└── archive/                      # Historical CSV data
    ├── crypto_markets.csv
    ├── markets.csv
    └── ...
```

### Core Components

**config.py**: Centralized configuration
- API endpoints (Gamma API, CLOB API)
- Rate limiting parameters (0.5s delay, exponential backoff)
- Crypto keywords for filtering (bitcoin, ethereum, solana, xrp, etc.)
- Market finder settings:
  - `MARKET_FETCH_BATCH_SIZE = 500` (API hard limit)
  - `DEFAULT_MAX_MARKETS = 5000` (default max markets to fetch)
  - `MAX_DISPLAY_RESOLVED = 20` (show top 20 resolved markets)
  - `MAX_DISPLAY_UNRESOLVED = 20` (show top 20 unresolved markets)
- Display settings (colors, box width, poll intervals)

**api_client.py**: `PolymarketAPIClient` class
- Automatic rate limiting (enforces minimum delay between requests)
- Retry logic for 429 (rate limit) and 500 (server error) responses
- Exponential backoff: [1s, 2s, 5s, 10s, 30s]
- Methods:
  - `get_markets()` - Fetch markets from Gamma API
  - `get_events()` - Fetch events from Gamma API
  - `get_price()` - Get current price from CLOB API
  - `get_orderbook()` - Get order book from CLOB API (may not be available)
  - `get_trades()` - Get recent trades from CLOB API (may not be available)

**display_utils.py**: Terminal formatting
- ANSI color codes (green for UP/BUY, red for DOWN/SELL)
- Box drawing with Unicode characters (┌─┐ │ └─┘)
- Price/percentage/currency formatting
- Orderbook table formatting
- Trade stream formatting

### API Integration

**Gamma API** (Market Metadata):
- Base URL: `https://gamma-api.polymarket.com`
- `/markets` endpoint with pagination (limit/offset)
- **API hard limit**: Maximum 500 markets per request (even if limit=1000)
- Parameters: `order=createdAt`, `ascending=true/false`, `closed=true/false`
- Default sort: **Newest first** (`ascending=false`) to get recent markets
- Returns: Market questions, outcomes, token IDs, volume, timestamps
- **Pagination**: Uses offset to fetch beyond 500 markets (offset=0, 500, 1000, etc.)

**CLOB API** (Live Data):
- Base URL: `https://clob.polymarket.com`
- `/price?token_id=X` - Current price for a token
- `/book?token_id=X` - Order book snapshot (may not be publicly available)
- `/trades?token_id=X&limit=10` - Recent trades (may not be publicly available)

**Important**: CLOB order book and trades endpoints may not be publicly accessible. The live monitor gracefully degrades to display prices only if these endpoints are unavailable.

**API Testing Results (December 2025)**:
- `/trades` endpoint **requires API authentication** (401 Unauthorized without API key)
- Historical trade data is NOT publicly accessible via REST API
- **WebSocket is the only public data source** for tick data collection
- WebSocket provides real-time trade stream without authentication

### WebSocket API (Real-Time Data - No Auth Required)

**Base URL**: `wss://ws-subscriptions-clob.polymarket.com/ws/market`

**Event Types Received**:
- `book` - Orderbook snapshots (on subscribe and after trades)
- `price_change` - When orders are placed/cancelled
- `tick_size_change` - When tick size changes
- `last_trade_price` - **Trade executions** (tick data source)

**Trade Event Structure**:
```python
{
    "asset_id": token_id,        # Token ID (70+ digits)
    "price": price,              # Trade price (0.0-1.0 range)
    "size": size,                # Trade size/volume
    "side": "BUY" or "SELL",     # Trade direction
    "fee_rate_bps": fee_rate,    # Fee in basis points
    "timestamp": ISO_timestamp,   # ISO 8601 format
    "market": market_id          # Market ID
}
```

### Crypto Market Filtering

Markets are filtered using keyword matching on the question text:

```python
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol',
    'xrp', 'ripple', 'cardano', 'ada', 'dogecoin', 'doge',
    'crypto', 'cryptocurrency', 'blockchain', 'defi', 'nft',
    'web3', 'binance', 'bnb', 'polygon', 'matic', 'avalanche',
    'avax', 'polkadot', 'dot', 'chainlink', 'link', ...
]
```

Case-insensitive matching: Any market with these keywords in the question is classified as a crypto market.

## Common Tasks

### Find Short-Term "Up or Down" Markets (15min, 1hr, 4hr)

```bash
# Find all short-term crypto markets (Bitcoin, Ethereum, Solana, XRP)
uv run python crypto_market_finder.py --unresolved --short-term

# Find short-term markets from the last 7 days
uv run python crypto_market_finder.py --unresolved --short-term --start-date 2025-12-15

# Find high-volume short-term markets
uv run python crypto_market_finder.py --unresolved --short-term --min-volume 50

# Fetch more markets to find historical short-term markets
uv run python crypto_market_finder.py --short-term --max-markets 10000
```

The `--short-term` filter looks for markets with patterns like:
- "Up or Down" in the question
- "updown" in the slug
- "15m", "1h", "4h" in the slug
- "15 min", "1 hour", "4 hour" in the question

### Get Markets from a Specific Date Range

```bash
# Get all markets from November 2025
uv run python crypto_market_finder.py --start-date 2025-11-01 --end-date 2025-12-01

# Get markets from the last week
uv run python crypto_market_finder.py --start-date 2025-12-15

# Combine with other filters
uv run python crypto_market_finder.py --unresolved --start-date 2025-12-20 --min-volume 100
```

### Monitor a Market with Live Updates

```bash
# Use token IDs from market finder
uv run python live_monitor.py \
  --token-up 123456789012345678901234567890... \
  --token-down 987654321098765432109876543210... \
  --interval 5 \
  --market-name "BTC 1hr Up/Down"
```

### Customize Crypto Keywords

Edit `config.py` and add/remove keywords from `CRYPTO_KEYWORDS` list:

```python
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc',
    'my_new_coin', 'mnc',
    ...
]
```

### Change Rate Limiting

Edit `config.py`:

```python
RATE_LIMIT_DELAY = 1.0  # Increase to 1 second between requests
RATE_LIMIT_BACKOFF = [2, 5, 10, 20, 60]  # More aggressive backoff
```

### Adjust Terminal Display

Edit `config.py`:

```python
USE_COLOR = False  # Disable colors
CLEAR_SCREEN = False  # Don't clear screen on update
BOX_WIDTH = 80  # Wider display
ORDERBOOK_DEPTH = 10  # Show more orderbook levels
RECENT_TRADES_COUNT = 20  # Show more trades
```

## Error Handling

All API calls include comprehensive error handling:

**Rate Limiting (429)**:
- Automatically waits with exponential backoff
- Increases poll interval dynamically in live monitor

**Server Errors (500)**:
- Retries up to 3 times with exponential backoff
- Continues monitoring if retries fail

**Network Timeouts**:
- Retries with backoff
- Displays "Waiting for connection..." in live monitor

**Missing/Invalid Data**:
- Graceful degradation (e.g., prices only if orderbook unavailable)
- Clear warning messages to user
- Continues operation where possible

## Data Files

**data/crypto_markets_cache.csv**:
- Output from `crypto_market_finder.py`
- Contains: id, question, outcomes, token IDs, volume, status, timestamps
- Can be imported into pandas for further analysis

**archive/** directory:
- Historical CSV files from previous pipeline
- Includes: crypto_markets.csv, markets.csv (16MB snapshot)
- Useful for reference or offline testing

## Development Notes

**Adding New APIs**:
1. Add endpoint URL to `config.py`
2. Add method to `PolymarketAPIClient` in `api_client.py`
3. Include rate limiting via `_request_with_retry()`

**Adding New Display Components**:
1. Add formatting function to `display_utils.py`
2. Use existing color and box-drawing utilities
3. Test with various terminal sizes

**Testing API Calls**:
```python
from api_client import PolymarketAPIClient

client = PolymarketAPIClient()
markets = client.get_markets(limit=10)
print(markets[0])  # Inspect structure
```

## Troubleshooting

**"Error: Unable to fetch price data"**:
- Check token IDs are correct (70+ digit numeric strings)
- CLOB API may be temporarily unavailable
- Try again with different token IDs from market finder

**"Order book data not available"**:
- This is expected - CLOB `/book` endpoint may not be publicly accessible
- Live monitor will show prices only

**"No crypto markets found"**:
- Check internet connection
- Gamma API may be temporarily unavailable
- Try with `--min-volume 0` to see all markets

**Rate limiting errors**:
- Decrease poll interval in live monitor (use `--interval 10` instead of `--interval 1`)
- Reduce concurrent API calls
- Wait a few minutes before retrying

## Important Notes

### Pagination and API Limits

- **API Hard Limit**: Polymarket Gamma API returns maximum 500 markets per request
- **Batch Size**: `MARKET_FETCH_BATCH_SIZE = 500` in `config.py`
- **Default Fetch Limit**: 5000 markets (`DEFAULT_MAX_MARKETS` in `config.py`)
- **Pagination**: Script automatically fetches multiple batches using offset (0, 500, 1000, 1500, etc.)
- **Sort Order**: Default is **newest first** to get recent markets (use `--oldest-first` for reverse)
- **Date Filtering**: Use `--start-date` and `--end-date` to efficiently stop pagination early

**Why newest first?**
- Most users want recent markets (hourly "Up or Down" markets, current events)
- Fetching oldest first (from 2020) requires thousands of requests to reach 2025 markets
- With newest first, you get today's markets in the first batch (500 markets)

### Market Data

- **Token IDs**: Always stored as strings (can be 70+ digits)
- **Timestamps**: Market times in UTC (ISO 8601 format)
- **Prices**: Decimal format (0.0 to 1.0 range typical)
- **Volumes**: In USD
- **Resolved Markets**: Have `closed=true` and `closedTime` field populated
- **Unresolved Markets**: Have `closed=false` and `closedTime` is empty

### CSV Output

The `data/crypto_markets_cache.csv` file contains:
- `id`: Market ID
- `question`: Market question text
- `outcome1`, `outcome2`: Outcome labels (e.g., "Up", "Down" or "Yes", "No")
- `token1`, `token2`: Token IDs for each outcome (use these for live monitoring)
- `volume`: Total volume in USD
- `closed`: Boolean (true/false) indicating if market is resolved
- `closedTime`: Timestamp when market closed (empty for open markets)
- `createdAt`: Timestamp when market was created

---

## Tick Data System (NEW)

The tick data system records individual trade executions to a SQLite database for historical analysis and candlestick generation.

### Overview

**Purpose**: Collect tick-by-tick trade data for backtesting and analysis

**Data Source**: WebSocket API only (REST `/trades` endpoint requires authentication)

**Storage**: SQLite database at `data/ticks.db`

**Key Insight**: Since historical trade data is NOT publicly accessible via REST API, you must start recording NOW to build a historical database for future analysis.

### Quick Start

```bash
# Record trades for specific markets (use market IDs from crypto_market_finder.py)
uv run tick-tool record --market-ids 996577,996578,996579

# Record all unresolved crypto markets from cache
uv run tick-tool record --from-cache --filter-unresolved --min-volume 100

# Query trades for a market
uv run tick-tool query --market-id 996577

# Export to CSV
uv run tick-tool export --market-id 996577 --output trades.csv

# Show market summary
uv run tick-tool summary --market-id 996577

# List all markets in database
uv run tick-tool list
```

### Architecture

```
WebSocket (wss://ws-subscriptions-clob.polymarket.com)
    ↓ (trade events: price, size, side, timestamp)
tick_recorder.py
    ↓ (enriched with market_id, outcome)
tick_database.py (SQLite)
    ↓ (queries, exports)
tick_tool.py (CLI)
```

### Database Schema

**markets table**: Market metadata cache
- `market_id`: Market ID (primary key)
- `question`: Market question text
- `outcome_up`, `outcome_down`: Outcome labels
- `token_up`, `token_down`: Token IDs
- `created_at`, `closed`, `closed_time`: Market status

**trades table**: Individual trade records
- `trade_id`: Unique composite ID (prevents duplicates)
- `market_id`: Market ID (foreign key)
- `asset_id`: Token ID (70+ digits)
- `side`: "BUY" or "SELL"
- `outcome`: "UP", "DOWN", etc. (enriched by recorder)
- `price`: Trade price (0.0-1.0 range)
- `size`: Trade size/volume
- `fee_rate_bps`: Fee rate in basis points
- `timestamp`: ISO 8601 timestamp
- `source`: "websocket" (always, since REST requires auth)
- `recorded_at`: When we stored this trade

**Indices**: Optimized for queries by market_id, asset_id, and timestamp

### CLI Commands

#### record - Start Recording

```bash
# Record specific markets
uv run tick-tool record --market-ids 996577,996578

# Auto-discover from cache with filters
uv run tick-tool record --from-cache --filter-unresolved --min-volume 1000 --limit 10

# Read market IDs from file
uv run tick-tool record --markets-file my_markets.txt

# Custom database path
uv run tick-tool record --market-ids 996577 --db-path /path/to/ticks.db
```

**Options**:
- `--market-ids`: Comma-separated market IDs
- `--from-cache`: Auto-discover from `crypto_markets_cache.csv`
- `--filter-unresolved`: Only unresolved markets (with `--from-cache`)
- `--min-volume`: Minimum volume filter (with `--from-cache`)
- `--limit`: Limit number of markets to record
- `--markets-file`: Read market IDs from file (one per line)

**Behavior**:
- Fetches market metadata from Gamma API
- Subscribes to WebSocket for all tokens across markets
- Records trades continuously until Ctrl+C
- Auto-reconnects on disconnect
- Shows periodic status updates

#### query - Query Trades

```bash
# Query by market ID
uv run tick-tool query --market-id 996577

# Query by token ID
uv run tick-tool query --token-id 96335067832619596263476394965563507657401324223032703267023353422994551721776

# Date range filtering
uv run tick-tool query --market-id 996577 --start-time 2025-12-23T20:00:00 --end-time 2025-12-23T21:00:00

# Filter by outcome
uv run tick-tool query --market-id 996577 --outcome UP

# Export to CSV
uv run tick-tool query --market-id 996577 --output trades.csv
```

**Output**: Displays trades in terminal or exports to CSV

#### export - Export to CSV

```bash
# Export all trades for a market
uv run tick-tool export --market-id 996577 --output btc_trades.csv
```

**CSV Format**:
```
timestamp,market_id,asset_id,side,outcome,price,size,value,fee_rate_bps,source
2025-12-23T20:15:30Z,996577,96335067...,BUY,UP,0.5234,100.50,52.63,10,websocket
```

#### list - List Markets

```bash
# List all markets
uv run tick-tool list

# Filter by status
uv run tick-tool list --filter-closed --closed true
```

#### summary - Market Summary

```bash
# Show summary statistics
uv run tick-tool summary --market-id 996577
```

**Output**:
- Market metadata (question, outcomes, status)
- Total trades count
- Total volume
- Time range (oldest/newest trade)
- Data sources breakdown

### Integration with Market Finder

**Workflow**: Find markets → Record trades → Analyze

```bash
# Step 1: Find interesting markets
uv run market-finder --unresolved --min-volume 1000

# Step 2: Start recording (output goes to crypto_markets_cache.csv)
uv run tick-tool record --from-cache --filter-unresolved --min-volume 1000

# Step 3: Let it run for hours/days to build historical data

# Step 4: Query and analyze
uv run tick-tool query --market-id 996577 --output analysis.csv
```

### Data Completeness

**What You Get**:
- ✓ All trades from the moment you start recording
- ✓ Real-time data with sub-second latency
- ✓ Complete trade history going forward

**What You DON'T Get**:
- ✗ Historical trades from before you started recording
- ✗ Trades from resolved markets (unless you recorded them live)
- ✗ Backfilled data (REST API requires authentication)

**Recommendation**: Start recording NOW for markets you're interested in to build up historical data over time.

### Files

**New Files**:
- `tick_database.py` (~480 lines) - SQLite database layer
- `tick_recorder.py` (~280 lines) - WebSocket recorder
- `tick_tool.py` (~330 lines) - CLI interface
- `test_trades_api.py` (~220 lines) - API testing script

**Data Files**:
- `data/ticks.db` - SQLite database (created on first use)
- Exported CSVs go to current directory or specified path

### Configuration

In `config.py`:

```python
# Tick Database Settings
TICK_DB_PATH = "data/ticks.db"
TICK_BATCH_COMMIT_SIZE = 100  # Commit every N trades
TICK_METADATA_REFRESH_INTERVAL = 300  # Refresh market metadata every 5min

# Historical Fetch Settings (not used - REST API requires auth)
MAX_HISTORICAL_FETCH_PER_TOKEN = 10000
HISTORICAL_FETCH_BATCH_SIZE = 100
```

### Troubleshooting

**"Error: Market X not found"**
- Check market ID is correct
- Market may have been delisted
- Try fetching fresh markets with `market-finder`

**"No trades recorded"**
- Check if market is active (has recent trading activity)
- Verify WebSocket connection (look for connection messages)
- Try with a different, more active market

**"Database locked"**
- Another process may be using the database
- Close other tick-tool instances
- SQLite allows concurrent reads but only one writer

**WebSocket disconnects**
- Auto-reconnect is built-in
- Check internet connection
- If persistent, check Polymarket WebSocket status

### Future Enhancements

Possible additions for later:
- Candlestick aggregation (1m, 5m, 15m, 1h, 4h, 1d)
- Order book snapshot recording
- Market-wide statistics
- Real-time dashboard/visualization
- Export to Parquet for analysis in pandas/polars
- Integration with trading strategies

### API Testing Notes

From `test_trades_api.py` findings (December 2025):
- `/trades` endpoint returns 401 Unauthorized without API key
- Historical data NOT publicly accessible via REST API
- WebSocket is the ONLY public source for tick data
- Must record in real-time; cannot backfill historical data
