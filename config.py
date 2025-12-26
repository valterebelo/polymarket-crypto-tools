"""
Shared configuration for Polymarket tools
"""

# API Endpoints
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# Rate Limiting
RATE_LIMIT_DELAY = 0.5  # seconds between requests
RATE_LIMIT_BACKOFF = [1, 2, 5, 10, 30]  # exponential backoff on 429 (seconds)

# Retry Logic
MAX_RETRIES = 3
TIMEOUT_SECONDS = 30

# Crypto Keywords for Filtering
CRYPTO_KEYWORDS = [
    'bitcoin', 'btc', 'ethereum', 'eth', 'solana', 'sol',
    'xrp', 'ripple', 'cardano', 'ada', 'dogecoin', 'doge',
    'crypto', 'cryptocurrency', 'blockchain', 'defi', 'nft',
    'web3', 'binance', 'bnb', 'polygon', 'matic', 'avalanche',
    'avax', 'polkadot', 'dot', 'chainlink', 'link', 'litecoin',
    'ltc', 'stellar', 'xlm', 'tron', 'trx', 'shiba', 'shib',
    'uniswap', 'uni', 'cosmos', 'atom', 'filecoin', 'fil'
]

# Market Finder Settings
MARKET_FETCH_BATCH_SIZE = 500  # API hard limit is 500 per request
MAX_DISPLAY_RESOLVED = 20
MAX_DISPLAY_UNRESOLVED = 20
DEFAULT_MAX_MARKETS = 10000  # Default max markets to fetch (prevents infinite loops)

# Live Monitor Settings
DEFAULT_POLL_INTERVAL = 5  # seconds
MIN_POLL_INTERVAL = 1
MAX_POLL_INTERVAL = 60
ORDERBOOK_DEPTH = 10  # Top N levels to display
RECENT_TRADES_COUNT = 10

# Data Paths
DATA_DIR = "data"
ARCHIVE_DIR = "archive"
CACHE_FILE = f"{DATA_DIR}/crypto_markets_cache.csv"

# Tick Database Settings
TICK_DB_PATH = f"{DATA_DIR}/ticks.db"
TICK_BATCH_COMMIT_SIZE = 100  # Commit every N trades
TICK_METADATA_REFRESH_INTERVAL = 300  # Refresh market metadata every 5min

# Historical Fetch Settings
MAX_HISTORICAL_FETCH_PER_TOKEN = 10000
HISTORICAL_FETCH_BATCH_SIZE = 100  # Per API request

# Terminal Display Settings
USE_COLOR = True
CLEAR_SCREEN = True
BOX_WIDTH = 65
