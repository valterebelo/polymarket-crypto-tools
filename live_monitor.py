#!/usr/bin/env python3
"""
Live Market Monitor for Polymarket

Real-time monitoring of markets with beautiful terminal UI.
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
from terminal_ui import TerminalUI
from config import (
    DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL, ORDERBOOK_DEPTH,
    RECENT_TRADES_COUNT, CACHE_FILE
)


def lookup_market_in_cache(market_id: str) -> Optional[Dict]:
    """Look up market in CSV cache file"""
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
        pass

    return None


def resolve_tokens_from_market_id(market_id: str) -> Optional[Dict]:
    """Resolve token IDs and outcomes from market ID"""
    import json
    client = PolymarketAPIClient()

    print(f"Looking up market {market_id}...")
    market = client.get_market_by_id(market_id)

    if market:
        clob_tokens_raw = market.get('clobTokenIds', [])
        outcomes_raw = market.get('outcomes', [])
        question = market.get('question', '')

        try:
            clob_tokens = json.loads(clob_tokens_raw) if isinstance(clob_tokens_raw, str) else clob_tokens_raw
            outcomes = json.loads(outcomes_raw) if isinstance(outcomes_raw, str) else outcomes_raw
        except json.JSONDecodeError:
            clob_tokens = []
            outcomes = []

        if len(clob_tokens) >= 2 and len(outcomes) >= 2:
            print(f"✓ Found: {question}")
            return {
                'token_up': clob_tokens[0],
                'token_down': clob_tokens[1],
                'outcome_up': outcomes[0],
                'outcome_down': outcomes[1],
                'question': question
            }

    # Fallback to cache
    cached = lookup_market_in_cache(market_id)
    if cached:
        print(f"✓ Found in cache: {cached['question']}")
        return {
            'token_up': cached['token1'],
            'token_down': cached['token2'],
            'outcome_up': cached['outcome1'],
            'outcome_down': cached['outcome2'],
            'question': cached['question']
        }

    print(f"✗ Market {market_id} not found")
    return None


def convert_orderbook_to_floats(orderbook: List[Dict]) -> List[Dict]:
    """Convert orderbook string values to floats"""
    converted = []
    for entry in orderbook:
        try:
            converted.append({
                'price': float(entry.get('price', 0)),
                'size': float(entry.get('size', 0))
            })
        except (ValueError, TypeError):
            continue
    return converted


class MarketMonitor:
    """Live market monitoring with Rich terminal UI"""

    def __init__(self, token_up: str, token_down: str, market_name: str = "",
                 poll_interval: int = DEFAULT_POLL_INTERVAL):
        self.token_up = token_up
        self.token_down = token_down
        self.market_name = market_name or "Market Monitor"
        self.poll_interval = poll_interval
        
        self.client = PolymarketAPIClient()
        self.ws_client: Optional[MarketWebSocketClient] = None
        self.ui: Optional[TerminalUI] = None
        self.running = True

        # Track previous prices for change calculation
        self.prev_up_price: Optional[float] = None
        self.prev_down_price: Optional[float] = None
        
        # WebSocket data (populated by callbacks)
        self.ws_orderbooks: Dict[str, Dict] = {}

        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        self.running = False
        if self.ui:
            self.ui.stop()
        if self.ws_client:
            self.ws_client.disconnect()
        print("\n\nMonitor stopped.")
        sys.exit(0)

    def validate_token_ids(self) -> bool:
        """Validate token IDs"""
        if not self.token_up or not self.token_down:
            return False
        if not self.token_up.isdigit() or not self.token_down.isdigit():
            return False
        if len(self.token_up) < 10 or len(self.token_down) < 10:
            return False
        return True

    def _on_ws_trade(self, trade: Dict):
        """Callback for WebSocket trade events"""
        asset_id = trade.get('asset_id', '')
        
        if asset_id == self.token_up:
            trade['outcome'] = 'UP'
        elif asset_id == self.token_down:
            trade['outcome'] = 'DOWN'
        else:
            trade['outcome'] = '?'
        
        # Convert strings to floats
        try:
            trade['price'] = float(trade.get('price', 0))
            trade['size'] = float(trade.get('size', 0))
        except (ValueError, TypeError):
            trade['price'] = 0.0
            trade['size'] = 0.0
        
        # Update UI
        if self.ui:
            self.ui.add_trade(trade)

    def _on_ws_book(self, book: Dict):
        """Callback for WebSocket orderbook events"""
        asset_id = book.get('asset_id', '')
        bids = convert_orderbook_to_floats(book.get('bids', []))
        asks = convert_orderbook_to_floats(book.get('asks', []))
        
        self.ws_orderbooks[asset_id] = {'bids': bids, 'asks': asks}
        
        # Update UI
        if self.ui:
            if asset_id == self.token_up:
                self.ui.update_orderbook('up', bids, asks)
            elif asset_id == self.token_down:
                self.ui.update_orderbook('down', bids, asks)

    def _on_ws_price_change(self, data: Dict):
        """Callback for price change events (just count, don't log)"""
        if self.ui:
            self.ui.increment_events()

    def _on_ws_connected(self):
        """Callback when WebSocket connects"""
        if self.ui:
            self.ui.set_ws_status(True)

    def _on_ws_disconnected(self):
        """Callback when WebSocket disconnects"""
        if self.ui:
            self.ui.set_ws_status(False)

    def init_websocket(self):
        """Initialize WebSocket connection"""
        self.ws_client = MarketWebSocketClient(
            asset_ids=[self.token_up, self.token_down],
            on_trade=self._on_ws_trade,
            on_book=self._on_ws_book,
            on_price_change=self._on_ws_price_change,
            on_connected=self._on_ws_connected,
            on_disconnected=self._on_ws_disconnected,
            max_trades_history=RECENT_TRADES_COUNT * 2,
            verbose=False  # No verbose logging - UI handles display
        )
        
        self.ws_client.connect()
        
        # Wait for connection
        for _ in range(30):
            if self.ws_client.is_connected():
                break
            time.sleep(0.1)

    def fetch_price_data(self, token_id: str) -> Optional[Dict]:
        """Fetch current price for a token"""
        try:
            data = self.client.get_price(token_id)
            if data:
                return {
                    'price': float(data.get('price', 0)),
                    'mid': float(data.get('mid', 0))
                }
        except Exception:
            pass
        return None

    def fetch_orderbook_data(self, token_id: str) -> Optional[Dict]:
        """Fetch orderbook (WebSocket first, then REST fallback)"""
        # Try WebSocket data first
        if token_id in self.ws_orderbooks:
            ws_book = self.ws_orderbooks[token_id]
            if ws_book.get('bids') or ws_book.get('asks'):
                return ws_book
        
        # Fall back to REST API
        try:
            data = self.client.get_orderbook(token_id)
            if data and isinstance(data, dict):
                return {
                    'bids': convert_orderbook_to_floats(data.get('bids', [])),
                    'asks': convert_orderbook_to_floats(data.get('asks', []))
                }
        except Exception:
            pass
        return None

    def update_data(self):
        """Fetch and update all data"""
        # Fetch prices
        up_price_data = self.fetch_price_data(self.token_up)
        down_price_data = self.fetch_price_data(self.token_down)

        if not up_price_data or not down_price_data:
            return False

        up_price = up_price_data['price']
        down_price = down_price_data['price']

        # Calculate changes
        up_change = None
        down_change = None
        if self.prev_up_price is not None and self.prev_up_price > 0:
            up_change = ((up_price - self.prev_up_price) / self.prev_up_price) * 100
        if self.prev_down_price is not None and self.prev_down_price > 0:
            down_change = ((down_price - self.prev_down_price) / self.prev_down_price) * 100

        self.prev_up_price = up_price
        self.prev_down_price = down_price

        # Update UI with prices
        if self.ui:
            self.ui.update_prices(up_price, down_price, up_change, down_change)

        # Fetch orderbooks (if not getting from WebSocket)
        if self.token_up not in self.ws_orderbooks:
            up_book = self.fetch_orderbook_data(self.token_up)
            if up_book and self.ui:
                self.ui.update_orderbook('up', up_book.get('bids', []), up_book.get('asks', []))
        
        if self.token_down not in self.ws_orderbooks:
            down_book = self.fetch_orderbook_data(self.token_down)
            if down_book and self.ui:
                self.ui.update_orderbook('down', down_book.get('bids', []), down_book.get('asks', []))

        return True

    def run(self):
        """Main monitoring loop"""
        if not self.validate_token_ids():
            print("Error: Invalid token IDs")
            return

        print(f"Starting monitor for: {self.market_name}")
        print(f"Connecting to WebSocket...")
        
        # Initialize WebSocket
        self.init_websocket()
        
        # Initialize UI
        self.ui = TerminalUI(market_name=self.market_name, max_trades=RECENT_TRADES_COUNT)
        
        # Set initial WebSocket status
        if self.ws_client:
            self.ui.set_ws_status(self.ws_client.is_connected())
        
        # Start the UI
        self.ui.start()
        
        try:
            while self.running:
                self.update_data()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            pass
        finally:
            self.ui.stop()
            if self.ws_client:
                self.ws_client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description='Live market monitor for Polymarket with rich terminal UI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python live_monitor.py --market-id 990592
  python live_monitor.py --market-id 990592 --interval 3
  python live_monitor.py --token-up 123... --token-down 456...
        '''
    )
    parser.add_argument('--market-id', type=str, default=None,
                       help='Market ID (recommended)')
    parser.add_argument('--token-up', type=str, default=None,
                       help='Token ID for UP outcome')
    parser.add_argument('--token-down', type=str, default=None,
                       help='Token ID for DOWN outcome')
    parser.add_argument('--interval', type=int, default=DEFAULT_POLL_INTERVAL,
                       help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})')
    parser.add_argument('--market-name', type=str, default="",
                       help='Display name for the market')

    args = parser.parse_args()

    has_market_id = args.market_id is not None
    has_tokens = args.token_up is not None and args.token_down is not None

    if not has_market_id and not has_tokens:
        parser.error("Must provide either --market-id OR both --token-up and --token-down")

    if has_market_id and has_tokens:
        parser.error("Cannot use both --market-id and --token-up/--token-down together")

    if args.interval < MIN_POLL_INTERVAL or args.interval > MAX_POLL_INTERVAL:
        print(f"Error: Interval must be between {MIN_POLL_INTERVAL} and {MAX_POLL_INTERVAL} seconds")
        sys.exit(1)

    # Resolve tokens
    if args.market_id:
        resolved = resolve_tokens_from_market_id(args.market_id)
        if not resolved:
            print(f"Error: Could not find market ID {args.market_id}")
            sys.exit(1)

        token_up = resolved['token_up']
        token_down = resolved['token_down']
        market_name = args.market_name or resolved['question']
    else:
        token_up = args.token_up
        token_down = args.token_down
        market_name = args.market_name or "Market Monitor"

    # Create and run monitor
    monitor = MarketMonitor(
        token_up=token_up,
        token_down=token_down,
        market_name=market_name,
        poll_interval=args.interval
    )

    monitor.run()


if __name__ == "__main__":
    main()