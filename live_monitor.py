#!/usr/bin/env python3
"""
Live Market Monitor for Polymarket

Real-time monitoring of markets with prices, orderbook, and volume.
Uses CLOB WebSocket for real-time trade stream (no auth required).
"""
import argparse
import time
import signal
import sys
from datetime import datetime, timezone
from typing import Dict, List, Optional
from api_client import PolymarketAPIClient
from websocket_client import MarketWebSocketClient
from display_utils import (
    clear_screen, draw_header, draw_box,
    format_price_panel, format_orderbook,
    format_trade, format_volume_metrics
)
from config import (
    DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL, ORDERBOOK_DEPTH,
    RECENT_TRADES_COUNT, CLEAR_SCREEN, CACHE_FILE
)


def lookup_market_in_cache(market_id: str) -> Optional[Dict]:
    """
    Look up market in CSV cache file

    Args:
        market_id: Market ID to find

    Returns:
        Dict with 'token1', 'token2', 'outcome1', 'outcome2', 'question' or None
    """
    import csv
    import os

    if not os.path.exists(CACHE_FILE):
        return None

    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['id'] == market_id:
                    return {
                        'token1': row['token1'],
                        'token2': row['token2'],
                        'outcome1': row['outcome1'],
                        'outcome2': row['outcome2'],
                        'question': row['question']
                    }
    except Exception as e:
        print(f"Warning: Could not read cache file: {e}")

    return None


def resolve_tokens_from_market_id(market_id: str) -> Optional[Dict]:
    """
    Resolve token IDs and outcomes from market ID

    Tries API first, falls back to CSV cache

    Args:
        market_id: Market ID to look up

    Returns:
        Dict with keys: token_up, token_down, outcome_up, outcome_down, question
        or None if not found
    """
    import json
    client = PolymarketAPIClient()

    # Try API first
    print(f"Looking up market {market_id} via API...")
    market = client.get_market_by_id(market_id)

    if market:
        # Extract token IDs (API returns as JSON string)
        clob_tokens_raw = market.get('clobTokenIds', [])
        outcomes_raw = market.get('outcomes', [])
        question = market.get('question', '')

        # Parse JSON strings if needed
        try:
            clob_tokens = json.loads(clob_tokens_raw) if isinstance(clob_tokens_raw, str) else clob_tokens_raw
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        except json.JSONDecodeError:
            print(f"⚠ Failed to parse market data for {market_id}")
            clob_tokens = []
            outcomes = []

        if len(clob_tokens) >= 2 and len(outcomes) >= 2:
            print(f"✓ Found market: {question}")
            return {
                'token_up': clob_tokens[0],
                'token_down': clob_tokens[1],
                'outcome_up': outcomes[0],
                'outcome_down': outcomes[1],
                'question': question
            }
        else:
            print(f"⚠ Market {market_id} does not have 2 tokens/outcomes")
            return None

    # Fallback to cache
    print(f"API lookup failed, trying CSV cache...")
    cached = lookup_market_in_cache(market_id)

    if cached:
        print(f"✓ Found market in cache: {cached['question']}")
        return {
            'token_up': cached['token1'],
            'token_down': cached['token2'],
            'outcome_up': cached['outcome1'],
            'outcome_down': cached['outcome2'],
            'question': cached['question']
        }

    print(f"✗ Market {market_id} not found in API or cache")
    return None


def convert_orderbook_to_floats(orderbook: List[Dict]) -> List[Dict]:
    """
    Convert orderbook entries to have float prices and sizes.
    
    The Polymarket CLOB API returns prices and sizes as strings,
    but our display functions expect floats.
    
    Args:
        orderbook: List of orderbook entries with 'price' and 'size' keys
        
    Returns:
        List of orderbook entries with float values
    """
    converted = []
    for entry in orderbook:
        try:
            converted.append({
                'price': float(entry.get('price', 0)),
                'size': float(entry.get('size', 0))
            })
        except (ValueError, TypeError):
            # Skip malformed entries
            continue
    return converted


class MarketMonitor:
    """Live market monitoring class with WebSocket integration"""

    def __init__(self, token_up: str, token_down: str, market_name: str = "",
                 poll_interval: int = DEFAULT_POLL_INTERVAL,
                 use_websocket: bool = True, verbose: bool = False):
        self.token_up = token_up
        self.token_down = token_down
        self.market_name = market_name or "Market Monitor"
        self.poll_interval = poll_interval
        self.use_websocket = use_websocket
        self.verbose = verbose
        
        self.client = PolymarketAPIClient()
        self.ws_client: Optional[MarketWebSocketClient] = None
        self.running = True

        # Track previous prices for change calculation
        self.prev_up_price = None
        self.prev_down_price = None
        
        # WebSocket trade buffer (populated by callbacks)
        self.ws_trades: List[Dict] = []
        self.ws_trades_lock = None  # Will be initialized if using websocket
        
        # Track orderbooks from WebSocket
        self.ws_orderbooks: Dict[str, Dict] = {}

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n" + "=" * 65)
        print("Monitor stopped by user")
        print("=" * 65)
        self.running = False
        
        # Clean up WebSocket connection
        if self.ws_client:
            self.ws_client.disconnect()
        
        sys.exit(0)

    def validate_token_ids(self) -> bool:
        """Validate token IDs"""
        if not self.token_up or not self.token_down:
            print("Error: Both token IDs are required")
            return False

        if not self.token_up.isdigit() or not self.token_down.isdigit():
            print("Error: Token IDs must be numeric")
            return False

        if len(self.token_up) < 10 or len(self.token_down) < 10:
            print("Error: Token IDs appear invalid (too short)")
            return False

        return True

    def _on_ws_trade(self, trade: Dict):
        """Callback for WebSocket trade events"""
        import threading
        
        # Determine which token this trade is for
        asset_id = trade.get('asset_id', '')
        
        if asset_id == self.token_up:
            trade['outcome'] = 'UP'
        elif asset_id == self.token_down:
            trade['outcome'] = 'DOWN'
        else:
            trade['outcome'] = 'UNKNOWN'
        
        # Convert string values to floats (WebSocket returns strings)
        try:
            trade['price'] = float(trade.get('price', 0))
            trade['size'] = float(trade.get('size', 0))
        except (ValueError, TypeError):
            trade['price'] = 0.0
            trade['size'] = 0.0
        
        # Add to buffer (thread-safe)
        if self.ws_trades_lock:
            with self.ws_trades_lock:
                self.ws_trades.insert(0, trade)
                # Keep only recent trades
                self.ws_trades = self.ws_trades[:RECENT_TRADES_COUNT * 2]
        
        if self.verbose:
            print(f"🔔 Trade: {trade['outcome']} {trade['side']} {trade['size']:.2f} @ ${trade['price']:.4f}")

    def _on_ws_book(self, book: Dict):
        """Callback for WebSocket orderbook events"""
        asset_id = book.get('asset_id', '')
        self.ws_orderbooks[asset_id] = {
            'bids': book.get('bids', []),
            'asks': book.get('asks', [])
        }

    def _on_ws_connected(self):
        """Callback when WebSocket connects"""
        if self.verbose:
            print("✅ WebSocket connected - receiving real-time trade stream")

    def _on_ws_disconnected(self):
        """Callback when WebSocket disconnects"""
        if self.verbose:
            print("⚠ WebSocket disconnected")

    def _on_ws_error(self, error):
        """Callback for WebSocket errors"""
        if self.verbose:
            print(f"⚠ WebSocket error: {error}")

    def init_websocket(self):
        """Initialize WebSocket connection for real-time data"""
        import threading
        
        self.ws_trades_lock = threading.Lock()
        
        self.ws_client = MarketWebSocketClient(
            asset_ids=[self.token_up, self.token_down],
            on_trade=self._on_ws_trade,
            on_book=self._on_ws_book,
            on_connected=self._on_ws_connected,
            on_disconnected=self._on_ws_disconnected,
            on_error=self._on_ws_error,
            max_trades_history=RECENT_TRADES_COUNT * 2,
            verbose=self.verbose
        )
        
        print("Connecting to WebSocket for real-time trade stream...")
        self.ws_client.connect()
        
        # Wait for connection
        for _ in range(50):  # Wait up to 5 seconds
            if self.ws_client.is_connected():
                break
            time.sleep(0.1)
        
        if self.ws_client.is_connected():
            print("✓ WebSocket connected!")
        else:
            print("⚠ WebSocket connection pending...")

    def fetch_price_data(self, token_id: str) -> Optional[Dict]:
        """Fetch current price for a token"""
        try:
            data = self.client.get_price(token_id)
            if data:
                return {
                    'price': float(data.get('price', 0)),
                    'mid': float(data.get('mid', 0))
                }
        except Exception as e:
            if self.verbose:
                print(f"Error fetching price: {e}")

        return None

    def fetch_orderbook_data(self, token_id: str) -> Optional[Dict]:
        """Fetch orderbook for a token (tries WebSocket first, falls back to REST)"""
        # Try WebSocket data first
        if self.ws_client and token_id in self.ws_orderbooks:
            ws_book = self.ws_orderbooks[token_id]
            if ws_book.get('bids') or ws_book.get('asks'):
                return {
                    'bids': convert_orderbook_to_floats(ws_book.get('bids', [])),
                    'asks': convert_orderbook_to_floats(ws_book.get('asks', []))
                }
        
        # Fall back to REST API
        try:
            data = self.client.get_orderbook(token_id)
            if data and isinstance(data, dict):
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                return {
                    'bids': convert_orderbook_to_floats(bids),
                    'asks': convert_orderbook_to_floats(asks)
                }
        except Exception as e:
            pass  # Orderbook may not be available, fail silently

        return None

    def get_trades_from_websocket(self) -> List[Dict]:
        """Get recent trades from WebSocket buffer"""
        if not self.ws_trades_lock:
            return []
        
        with self.ws_trades_lock:
            return list(self.ws_trades[:RECENT_TRADES_COUNT])

    def update_display(self):
        """Update the terminal display with latest data"""
        if CLEAR_SCREEN:
            clear_screen()

        # Fetch data for both tokens
        up_price_data = self.fetch_price_data(self.token_up)
        down_price_data = self.fetch_price_data(self.token_down)

        if not up_price_data or not down_price_data:
            print("⚠ Error: Unable to fetch price data")
            print("Possible reasons:")
            print("  • Market has not started trading yet (check start time)")
            print("  • Market is closed or resolved")
            print("  • No orderbook exists for this market")
            print("  • CLOB API may be temporarily unavailable")
            return False

        # Extract prices
        up_price = up_price_data['price']
        down_price = down_price_data['price']

        # Calculate price changes
        up_change = None
        down_change = None
        if self.prev_up_price is not None:
            up_change = ((up_price - self.prev_up_price) / self.prev_up_price) * 100 if self.prev_up_price != 0 else 0
            down_change = ((down_price - self.prev_down_price) / self.prev_down_price) * 100 if self.prev_down_price != 0 else 0

        # Update previous prices
        self.prev_up_price = up_price
        self.prev_down_price = down_price

        # Calculate market caps (assuming $1M total market cap)
        total_cap = 1_000_000
        up_cap = up_price * total_cap
        down_cap = down_price * total_cap

        # Draw header
        ws_status = "🔴" if not (self.ws_client and self.ws_client.is_connected()) else "🟢"
        subtitle = f"Updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC  {ws_status} WSS"
        print(draw_header(self.market_name, subtitle))
        print()

        # Price panel
        price_content = format_price_panel(
            up_price, down_price,
            up_change, down_change,
            up_cap, down_cap
        )
        print(draw_box("CURRENT PRICES", price_content))
        print()

        # Orderbook panel (if available)
        up_book = self.fetch_orderbook_data(self.token_up)
        down_book = self.fetch_orderbook_data(self.token_down)

        if up_book and down_book:
            orderbook_content = format_orderbook(
                up_book.get('bids', []),
                down_book.get('asks', []),
                depth=ORDERBOOK_DEPTH
            )
            print(draw_box(f"ORDER BOOK DEPTH (Top {ORDERBOOK_DEPTH} Levels)", orderbook_content))
            print()
        else:
            # Orderbook not available
            print(draw_box("ORDER BOOK DEPTH", [
                "⚠ Order book data not available via CLOB API",
                "Displaying prices only"
            ]))
            print()

        # Recent trades panel (from WebSocket)
        if self.use_websocket and self.ws_client:
            trades = self.get_trades_from_websocket()
            
            if trades:
                # Format trades for display
                trade_lines = []
                for t in trades[:RECENT_TRADES_COUNT]:
                    trade_lines.append(format_trade(t))
                
                print(draw_box(f"RECENT TRADES (Live via WebSocket)", trade_lines))
                print()

                # Volume metrics
                volume_content = format_volume_metrics(trades)
                print(draw_box("VOLUME METRICS", volume_content))
                print()
            else:
                print(draw_box("RECENT TRADES (Live via WebSocket)", [
                    "ℹ Waiting for trades...",
                    "Trade stream connected, no trades yet"
                ]))
                print()
        else:
            print(draw_box("RECENT TRADES", [
                "ℹ WebSocket disabled - use --websocket to enable real-time trades"
            ]))
            print()

        # Footer
        ws_info = ""
        if self.ws_client:
            if self.ws_client.is_connected():
                ws_info = " | 🟢 Live trade stream"
            else:
                ws_info = " | 🔴 Reconnecting..."
        
        print(f"Press Ctrl+C to exit | Next update in {self.poll_interval}s{ws_info}...")

        return True

    def run(self):
        """Main monitoring loop"""
        if not self.validate_token_ids():
            return

        print(f"Starting live monitor for {self.market_name}")
        print(f"UP token: {self.token_up[:20]}...")
        print(f"DOWN token: {self.token_down[:20]}...")
        print(f"Poll interval: {self.poll_interval}s")
        print(f"WebSocket: {'Enabled' if self.use_websocket else 'Disabled'}")
        print("\nPress Ctrl+C to exit\n")

        # Initialize WebSocket if enabled
        if self.use_websocket:
            self.init_websocket()
            time.sleep(1)  # Give WebSocket time to receive initial data
        
        time.sleep(1)  # Give user time to read

        while self.running:
            success = self.update_display()

            if not success:
                print(f"\nRetrying in {self.poll_interval}s...")

            time.sleep(self.poll_interval)


def main():
    parser = argparse.ArgumentParser(
        description='Live market monitor for Polymarket with real-time WebSocket trades',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Monitor using market ID (easiest)
  python live_monitor.py --market-id 995839

  # Monitor using token IDs (advanced)
  python live_monitor.py --token-up 123456... --token-down 789012...

  # With verbose WebSocket logging
  python live_monitor.py --market-id 995839 --verbose

  # Disable WebSocket (REST only, no trades)
  python live_monitor.py --market-id 995839 --no-websocket
        '''
    )
    # Input method 1: Market ID (recommended)
    parser.add_argument('--market-id', type=str, default=None,
                       help='Market ID (e.g., 995839) - easiest way to start monitoring')

    # Input method 2: Token IDs (advanced)
    parser.add_argument('--token-up', type=str, default=None,
                       help='Token ID for UP outcome (advanced usage)')
    parser.add_argument('--token-down', type=str, default=None,
                       help='Token ID for DOWN outcome (advanced usage)')
    parser.add_argument('--interval', type=int, default=DEFAULT_POLL_INTERVAL,
                       help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})')
    parser.add_argument('--market-name', type=str, default="",
                       help='Display name for the market')
    
    # WebSocket options
    parser.add_argument('--no-websocket', action='store_true',
                       help='Disable WebSocket (no real-time trades)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging (including WebSocket events)')

    args = parser.parse_args()

    # Validation: Must provide either market-id OR both token IDs
    has_market_id = args.market_id is not None
    has_tokens = args.token_up is not None and args.token_down is not None

    if not has_market_id and not has_tokens:
        parser.error("Must provide either --market-id OR both --token-up and --token-down")

    if has_market_id and has_tokens:
        parser.error("Cannot use both --market-id and --token-up/--token-down together")

    # Validate interval
    if args.interval < MIN_POLL_INTERVAL or args.interval > MAX_POLL_INTERVAL:
        print(f"Error: Interval must be between {MIN_POLL_INTERVAL} and {MAX_POLL_INTERVAL} seconds")
        sys.exit(1)

    # Resolve tokens
    if args.market_id:
        # Resolve from market ID
        resolved = resolve_tokens_from_market_id(args.market_id)

        if not resolved:
            print(f"\n✗ Error: Could not find market ID {args.market_id}")
            print("Please check the ID and try again, or use --token-up/--token-down directly")
            sys.exit(1)

        token_up = resolved['token_up']
        token_down = resolved['token_down']

        # Auto-populate market name if not provided
        if not args.market_name:
            market_name = resolved['question']
        else:
            market_name = args.market_name

        # Show what was resolved
        print(f"\n✓ Resolved market tokens:")
        print(f"  {resolved['outcome_up']}: {token_up[:20]}...")
        print(f"  {resolved['outcome_down']}: {token_down[:20]}...")
        print()

    else:
        # Use provided tokens
        token_up = args.token_up
        token_down = args.token_down
        market_name = args.market_name or "Market Monitor"

    # Create and run monitor
    monitor = MarketMonitor(
        token_up=token_up,
        token_down=token_down,
        market_name=market_name,
        poll_interval=args.interval,
        use_websocket=not args.no_websocket,
        verbose=args.verbose
    )

    monitor.run()


if __name__ == "__main__":
    main()