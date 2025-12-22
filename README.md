# Polymarket Crypto Tools

Two focused tools for working with Polymarket crypto markets:

1. **Market Finder** - Discover resolved and unresolved crypto markets
2. **Live Monitor** - Real-time terminal monitoring with prices, orderbook, and trades

## Installation

This project uses [UV](https://docs.astral.sh/uv/) for fast dependency management:

```bash
# Install UV (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

## Quick Start

### 1. Find Crypto Markets

```bash
# Find all unresolved crypto markets
uv run python crypto_market_finder.py --unresolved

# Find all markets (resolved + unresolved)
uv run python crypto_market_finder.py --all

# Filter by minimum volume ($1000+)
uv run python crypto_market_finder.py --unresolved --min-volume 1000

# Save to custom file
uv run python crypto_market_finder.py --output my_markets.csv
```

**Example Output:**
```
=================================================================
CRYPTO MARKET FINDER
=================================================================

Fetching markets from Polymarket...
✓ Fetched 5,234 total markets

Filtering for crypto keywords...
✓ Found 234 crypto markets

=================================================================
SUMMARY
=================================================================
Total crypto markets: 234
  Resolved: 89 (38.0%)
  Unresolved: 145 (62.0%)
Total volume: $12,345,678

=================================================================
UNRESOLVED MARKETS (Top 20 by volume)
=================================================================
[1] Bitcoin Up or Down - December 22, 1:00PM-2:00PM ET
    Volume: $234,567 | Market ID: 0x1234abcd...
    Status: OPEN
    Tokens: UP=1234567890..., DOWN=0987654321...

[2] Ethereum Up or Down - December 22, 2:00PM-3:00PM ET
    Volume: $156,789 | Market ID: 0x5678efgh...
    Status: OPEN
    Tokens: YES=5555666677..., NO=9999888877...
```

### 2. Monitor a Market Live

Copy token IDs from the market finder output and use them to monitor:

```bash
# Basic monitoring (updates every 5 seconds)
uv run python live_monitor.py \
  --token-up 1234567890123456789012345678901234567890 \
  --token-down 0987654321098765432109876543210987654321

# Custom poll interval (10 seconds)
uv run python live_monitor.py \
  --token-up <UP_TOKEN> \
  --token-down <DOWN_TOKEN> \
  --interval 10

# Named display
uv run python live_monitor.py \
  --token-up <UP_TOKEN> \
  --token-down <DOWN_TOKEN> \
  --market-name "BTC 1hr"
```

**Example Output:**
```
╔═══════════════════════════════════════════════════════════════╗
║  BTC 1hr                                                      ║
║  Updated: 2025-12-22 13:45:32 UTC                            ║
╚═══════════════════════════════════════════════════════════════╝

┌───────────────────────────────────────────────────────────────┐
│ CURRENT PRICES                                                │
├───────────────────────────────────────────────────────────────┤
│ UP:   $0.5234 (▲ +0.12%)    Market Cap: $523,400            │
│ DOWN: $0.4766 (▼ -0.12%)    Market Cap: $476,600            │
│ Spread: $0.0468 (4.68%)                                       │
└───────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────┐
│ ORDER BOOK DEPTH (Top 5 Levels)                              │
├───────────────────────────────────────────────────────────────┤
│      BIDS (UP)          │       ASKS (DOWN)                  │
│ $0.5230 x  1,250        │ $0.4770 x  2,100                  │
│ $0.5225 x  3,400        │ $0.4775 x  1,800                  │
│ ...                                                           │
└───────────────────────────────────────────────────────────────┘

Press Ctrl+C to exit | Next update in 5s...
```

## Features

### Market Finder

- Fetches all markets from Polymarket Gamma API
- Filters for crypto keywords (bitcoin, ethereum, solana, etc.)
- Separates resolved vs unresolved markets
- Sorts by volume
- Saves results to CSV for further analysis
- Displays token IDs for easy copy-paste into live monitor

### Live Monitor

- Real-time price updates for UP/DOWN outcomes
- Price change tracking (percentage)
- Market cap calculation
- Order book depth display (if available via API)
- Recent trade stream (if available via API)
- Volume metrics
- Graceful degradation if some API endpoints unavailable
- Terminal UI with colors and box drawing
- Ctrl+C for graceful shutdown

## Configuration

Edit `config.py` to customize:

```python
# Crypto keywords for filtering
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', 'eth', ...
]

# Rate limiting
RATE_LIMIT_DELAY = 0.5  # seconds between API calls
RATE_LIMIT_BACKOFF = [1, 2, 5, 10, 30]  # exponential backoff

# Live monitor settings
DEFAULT_POLL_INTERVAL = 5  # update every 5 seconds
ORDERBOOK_DEPTH = 5  # show top 5 levels
RECENT_TRADES_COUNT = 10  # show last 10 trades

# Display settings
USE_COLOR = True  # colored terminal output
CLEAR_SCREEN = True  # clear screen on each update
BOX_WIDTH = 65  # terminal box width
```

## API Details

This tool uses two Polymarket APIs:

1. **Gamma API** (https://gamma-api.polymarket.com)
   - Market metadata, questions, outcomes, volumes
   - Publicly accessible

2. **CLOB API** (https://clob.polymarket.com)
   - Real-time prices, orderbook, trades
   - Some endpoints may not be publicly available

The live monitor gracefully handles unavailable endpoints by displaying prices only.

## Output Files

**data/crypto_markets_cache.csv**:
- Generated by market finder
- Contains: market ID, question, outcomes, token IDs, volume, status
- Can be analyzed with pandas/Excel

**archive/** directory:
- Historical data from previous data pipeline
- Reference files for offline testing

## Troubleshooting

**"No crypto markets found"**
- Check internet connection
- Verify Gamma API is accessible
- Try with `--min-volume 0` to see all results

**"Error: Unable to fetch price data"**
- Verify token IDs are correct (should be 70+ digit numbers)
- CLOB API may be temporarily unavailable
- Try different tokens from market finder

**"Order book data not available"**
- This is expected - CLOB `/book` endpoint may not be public
- Prices will still be displayed

**Rate limiting**
- Increase poll interval: `--interval 10`
- Wait a few minutes before retrying
- Reduce number of concurrent requests

## Development

Project structure:

```
├── config.py                     # Shared configuration
├── api_client.py                 # API wrapper with rate limiting
├── display_utils.py              # Terminal UI utilities
├── crypto_market_finder.py       # Market discovery tool
├── live_monitor.py               # Live monitoring tool
├── pyproject.toml                # Dependencies (requests, pandas)
├── data/                         # Output directory
└── archive/                      # Historical data
```

### Dependencies

- **requests** - HTTP requests to Polymarket APIs
- **pandas** - CSV handling in market finder

### Rate Limiting

All API calls include:
- Minimum 0.5s delay between requests
- Exponential backoff on rate limits (429)
- Retry logic for server errors (500)
- Graceful timeout handling

## License

Go wild with it

## Support

- File issues at: (your repo URL)
- See `CLAUDE.md` for technical architecture details
- Check Polymarket API docs: https://docs.polymarket.com
