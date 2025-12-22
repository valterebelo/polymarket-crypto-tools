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
# Find all crypto markets
uv run python crypto_market_finder.py --all

# Find only unresolved markets
uv run python crypto_market_finder.py --unresolved

# Filter by minimum volume
uv run python crypto_market_finder.py --unresolved --min-volume 1000

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
- Crypto keywords for filtering
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
- Parameters: `order=createdAt`, `ascending=true`, `closed=true/false`
- Returns: Market questions, outcomes, token IDs, volume, timestamps

**CLOB API** (Live Data):
- Base URL: `https://clob.polymarket.com`
- `/price?token_id=X` - Current price for a token
- `/book?token_id=X` - Order book snapshot (may not be publicly available)
- `/trades?token_id=X&limit=10` - Recent trades (may not be publicly available)

**Important**: CLOB order book and trades endpoints may not be publicly accessible. The live monitor gracefully degrades to display prices only if these endpoints are unavailable.

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

### Find 1-Hour BTC/ETH Markets

```bash
# Find all unresolved crypto markets
uv run python crypto_market_finder.py --unresolved

# Look for markets with "Bitcoin Up or Down" or "Ethereum Up or Down" in output
# Copy the token IDs (shown as "Tokens: UP=..., DOWN=...")
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

- **Token IDs**: Always stored as strings (can be 70+ digits)
- **Timestamps**: Market times in UTC
- **Prices**: Decimal format (0.0 to 1.0 range typical)
- **Volumes**: In USD
- **Resolved Markets**: Have `closedTime` field populated
- **Unresolved Markets**: `closedTime` is empty/null
