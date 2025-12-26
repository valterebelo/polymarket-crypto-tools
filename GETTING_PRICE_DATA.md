# Complete Guide: Getting Price Data from Polymarket

## TL;DR - All Available Methods

| Method | Endpoint | Auth? | Granularity | Historical? | Status |
|--------|----------|-------|-------------|-------------|--------|
| **Prices History** | `/prices-history` | No | Configurable | Yes | ✅ Documented |
| **Current Price** | `/price` | No | Snapshot | No | ✅ Working |
| **Orderbook** | `/book` | No | Snapshot | No | ⚠️ Limited |
| **Trades** | `/trades` | **Yes** | Tick-level | Limited | ⚠️ Requires Auth |
| **WebSocket** | `wss://` | No | Real-time | No | ✅ Working |

---

## Method 1: Prices History API ⭐ **RECOMMENDED FOR HISTORICAL DATA**

### Endpoint
```
GET https://clob.polymarket.com/prices-history
```

### Parameters

**Required:**
- `market` (string) - CLOB token ID

**Time Selection (choose one):**
- `interval` (enum) - Predefined duration: `1m`, `1h`, `6h`, `1d`, `1w`, `max`
- OR `startTs` (number) + `endTs` (number) - Unix timestamps

**Optional:**
- `fidelity` (number) - Resolution in minutes

### Response Format
```json
{
  "history": [
    {"t": 1697875200, "p": 0.5234},
    {"t": 1697878800, "p": 0.5289}
  ]
}
```

Where:
- `t` = Unix timestamp (seconds)
- `p` = Price value

### Usage

**Using our tool:**
```bash
# Get last 24 hours
python price_history.py --token-id <TOKEN_ID> --interval 1d

# Get last week at hourly resolution
python price_history.py --market-id <MARKET_ID> --interval 1w --fidelity 60

# Specific date range
python price_history.py --market-id <MARKET_ID> \\
  --start 2025-12-20 --end 2025-12-25 --fidelity 60

# Export to CSV
python price_history.py --market-id <MARKET_ID> --interval 1d --output prices.csv
```

**Direct API call:**
```python
import requests

url = "https://clob.polymarket.com/prices-history"
params = {
    "market": "96335067...",  # Token ID
    "interval": "1d",  # Last 24 hours
    "fidelity": 60  # 1-hour resolution
}

response = requests.get(url, params=params)
data = response.json()

for point in data["history"]:
    timestamp = point["t"]
    price = point["p"]
    print(f"{timestamp}: {price}")
```

### Notes

- ✅ No authentication required
- ✅ Configurable time ranges
- ✅ Configurable resolution (fidelity)
- ⚠️ May not have data for all markets (especially very new/old ones)
- ⚠️ Data availability varies by market

---

## Method 2: Current Price Snapshot

### Endpoint
```
GET https://clob.polymarket.com/price
```

### Parameters
- `token_id` (string) - Token ID
- `side` (string) - "buy" or "sell"

### Response
```json
{
  "price": 0.5234,
  "mid": 0.5200
}
```

### Usage

**Using our tool:**
```bash
python price_retriever.py snapshot --market-id <MARKET_ID>
```

**Direct:**
```python
import requests

response = requests.get(
    "https://clob.polymarket.com/price",
    params={"token_id": "123...", "side": "buy"}
)
price_data = response.json()
print(f"Price: {price_data['price']}")
```

---

## Method 3: Orderbook Data

### Endpoint
```
GET https://clob.polymarket.com/book
```

### Parameters
- `token_id` (string)

### Response
```json
{
  "bids": [{"price": "0.52", "size": "100"}, ...],
  "asks": [{"price": "0.53", "size": "150"}, ...]
}
```

### Usage

```python
from api_client import PolymarketAPIClient

client = PolymarketAPIClient()
book = client.get_orderbook(token_id)

if book:
    best_bid = book['bids'][0] if book['bids'] else None
    best_ask = book['asks'][0] if book['asks'] else None
```

**Note**: May not be available for all markets

---

## Method 4: Trade History (Authenticated)

### Endpoint
```
GET https://clob.polymarket.com/trades
```

### Parameters
- `token_id` (string)
- `limit` (number) - Max 1000

### Requirements
- **Authentication required** (API key, secret, passphrase)
- See `AUTHENTICATION_SETUP.md` for setup

### Response
```json
[
  {
    "id": "...",
    "price": "0.5234",
    "size": "100.50",
    "side": "BUY",
    "timestamp": "2025-12-26T00:00:00Z",
    "fee_rate_bps": "10"
  }
]
```

### Usage

```python
from api_client import PolymarketAPIClient
from auth_manager import AuthManager

auth = AuthManager()  # Requires env vars set
client = PolymarketAPIClient(auth_manager=auth)

trades = client.get_trades(token_id, limit=1000)
```

**Note**: May only return recent trades, not full history

---

## Method 5: WebSocket Real-Time Stream

### Endpoint
```
wss://ws-subscriptions-clob.polymarket.com/ws/market
```

### Usage

**Using our tool:**
```bash
python tick_tool.py record --market-ids <ID1>,<ID2>
```

**Direct:**
```python
from websocket_client import MarketWebSocketClient

def on_trade(trade):
    print(f"Trade: {trade['price']} @ {trade['size']}")

client = MarketWebSocketClient(
    asset_ids=[token_id],
    on_trade_callback=on_trade
)
client.connect()
```

**Trade Event:**
```python
{
    "asset_id": "123...",
    "price": "0.5234",
    "size": "100.50",
    "side": "BUY",
    "timestamp": "2025-12-26T00:00:00.123Z",
    "market": "996577"
}
```

---

## Complete Workflow: Market ID → Price Data

### Step 1: Get Token IDs

```python
from api_client import PolymarketAPIClient

client = PolymarketAPIClient()
market = client.get_market_by_id("996577")

token_up = market['clobTokenIds'][0]
token_down = market['clobTokenIds'][1]
outcome_up = market['outcomes'][0]
outcome_down = market['outcomes'][1]

print(f"{outcome_up}: {token_up}")
print(f"{outcome_down}: {token_down}")
```

### Step 2: Choose Your Data Source

**For historical price series:**
```bash
# Method 1: Prices History API (recommended)
python price_history.py --market-id 996577 --interval 1w --output prices.csv
```

**For current price:**
```bash
# Method 2: Current price snapshot
python price_retriever.py snapshot --market-id 996577
```

**For real-time monitoring:**
```bash
# Method 5: WebSocket
python tick_tool.py record --market-ids 996577
```

**For recent trade history (requires auth):**
```bash
# Method 4: Authenticated trades
# (Set env vars first)
python test_authenticated_trades.py --token-id <TOKEN_ID>
```

### Step 3: Process & Analyze

**Load CSV into pandas:**
```python
import pandas as pd

# From prices-history export
df = pd.read_csv('prices.csv')
df['datetime'] = pd.to_datetime(df['datetime'])
df = df.set_index('datetime')

# Plot
df.groupby('outcome')['price'].plot(legend=True)

# Resample to different timeframes
hourly = df.groupby('outcome')['price'].resample('1H').mean()
daily = df.groupby('outcome')['price'].resample('1D').mean()
```

**Build candlesticks:**
```python
# Assuming you have tick data from WebSocket or trades
df_ticks = pd.read_csv('trades.csv')
df_ticks['datetime'] = pd.to_datetime(df_ticks['timestamp'])
df_ticks = df_ticks.set_index('datetime')

# 5-minute candles
candles = df_ticks.groupby('outcome')['price'].resample('5min').agg({
    'open': 'first',
    'high': 'max',
    'low': 'min',
    'close': 'last'
})
```

---

## Recommended Approach by Use Case

### Use Case: "I want historical price data NOW"
→ Use **prices-history** endpoint
```bash
python price_history.py --market-id <ID> --interval max --output prices.csv
```

### Use Case: "I want to monitor prices every few seconds"
→ Use **polling** with current price
```bash
python price_retriever.py poll --market-id <ID> --duration 3600 --interval 5
```

### Use Case: "I want tick-by-tick data for backtesting"
→ Use **WebSocket recorder** + **authenticated trades** (if available)
```bash
# Start recording now (for future data)
python tick_tool.py record --market-ids <ID>

# Try fetching recent history (requires auth)
python test_authenticated_trades.py --token-id <TOKEN_ID>
```

### Use Case: "I want to build a price chart"
→ Use **prices-history** with appropriate fidelity
```bash
# Hourly candles for last week
python price_history.py --market-id <ID> --interval 1w --fidelity 60 --output chart_data.csv
```

---

## Data Availability Matrix

| Data Source | New Markets | Active Markets | Closed Markets | Granularity |
|-------------|-------------|----------------|----------------|-------------|
| prices-history | ⚠️ May be empty | ✅ Should work | ⚠️ Varies | Configurable |
| Current price | ✅ Works | ✅ Works | ❌ May not work | Single point |
| Authenticated trades | ⚠️ Limited | ✅ Recent only | ⚠️ May be purged | Tick-level |
| WebSocket | ✅ Works | ✅ Works | ❌ N/A | Real-time |

---

## Tools Quick Reference

| Tool | Purpose | Command |
|------|---------|---------|
| `price_history.py` | Fetch historical price series | `--market-id <ID> --interval 1d` |
| `price_retriever.py` | Current price or polling | `snapshot --market-id <ID>` |
| `tick_tool.py` | Record real-time trades | `record --market-ids <ID>` |
| `test_authenticated_trades.py` | Test auth & fetch trades | `--token-id <TOKEN_ID>` |

---

## Troubleshooting

### "Empty history returned from prices-history"

**Possible causes:**
1. Market is very new (no data accumulated yet)
2. Market is very old (data purged)
3. Low trading volume (no price updates)
4. Wrong token ID

**Solutions:**
- Try `interval: max` to get all available data
- Try different token (from active market)
- Check market is actually traded (has volume)
- Use WebSocket to start collecting data

### "401 Unauthorized on /trades"

**Cause:** Authentication required

**Solution:** See `AUTHENTICATION_SETUP.md` to configure credentials

### "No data points returned"

**Cause:** Time range or interval doesn't have data

**Solution:**
- Use `interval: max` first to see what's available
- Try shorter intervals (`1h` instead of `1w`)
- Check market creation date vs your query range

---

## API Documentation Links

- [Polymarket CLOB API Docs](https://docs.polymarket.com/developers/CLOB/)
- [Timeseries Endpoint](https://docs.polymarket.com/developers/CLOB/timeseries)
- [Authentication](https://docs.polymarket.com/developers/CLOB/authentication)

---

## Summary

**Best for most use cases:** `prices-history` endpoint
- No auth required
- Configurable time ranges and resolution
- Export to CSV for analysis
- Works with our `price_history.py` tool

**For real-time monitoring:** WebSocket + `tick_tool.py`

**For maximum data:** Combine all methods
- Historical: `prices-history`
- Recent trades: authenticated `/trades`
- Real-time: WebSocket
- Current: `/price` snapshot
