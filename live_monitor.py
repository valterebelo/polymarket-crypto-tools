#!/usr/bin/env python3
"""
Live Market Monitor for Polymarket

Real-time monitoring of markets with prices, orderbook, and volume.
"""
import argparse
import time
import signal
import sys
from datetime import datetime
from typing import Dict, Optional
from api_client import PolymarketAPIClient
from display_utils import (
    clear_screen, draw_header, draw_box,
    format_price_panel, format_orderbook,
    format_trade, format_volume_metrics
)
from config import (
    DEFAULT_POLL_INTERVAL, MIN_POLL_INTERVAL,
    MAX_POLL_INTERVAL, ORDERBOOK_DEPTH,
    RECENT_TRADES_COUNT, CLEAR_SCREEN
)


class MarketMonitor:
    """Live market monitoring class"""

    def __init__(self, token_up: str, token_down: str, market_name: str = "",
                 poll_interval: int = DEFAULT_POLL_INTERVAL):
        self.token_up = token_up
        self.token_down = token_down
        self.market_name = market_name or "Market Monitor"
        self.poll_interval = poll_interval
        self.client = PolymarketAPIClient()
        self.running = True

        # Track previous prices for change calculation
        self.prev_up_price = None
        self.prev_down_price = None

        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)

    def signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully"""
        print("\n\n" + "=" * 65)
        print("Monitor stopped by user")
        print("=" * 65)
        self.running = False
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
            print(f"Error fetching price: {e}")

        return None

    def fetch_orderbook_data(self, token_id: str) -> Optional[Dict]:
        """Fetch orderbook for a token"""
        try:
            data = self.client.get_orderbook(token_id)
            if data and isinstance(data, dict):
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                return {'bids': bids, 'asks': asks}
        except Exception as e:
            pass  # Orderbook may not be available, fail silently

        return None

    def fetch_trades_data(self, token_id: str, limit: int = RECENT_TRADES_COUNT) -> list:
        """Fetch recent trades for a token"""
        try:
            trades = self.client.get_trades(token_id, limit=limit)
            if trades and isinstance(trades, list):
                return trades
        except Exception as e:
            pass  # Trades may not be available, fail silently

        return []

    def update_display(self):
        """Update the terminal display with latest data"""
        if CLEAR_SCREEN:
            clear_screen()

        # Fetch data for both tokens
        up_price_data = self.fetch_price_data(self.token_up)
        down_price_data = self.fetch_price_data(self.token_down)

        if not up_price_data or not down_price_data:
            print("⚠ Error: Unable to fetch price data")
            print("The CLOB API may be unavailable or token IDs may be invalid")
            return False

        # Extract prices
        up_price = up_price_data['price']
        down_price = down_price_data['price']

        # Calculate price changes
        up_change = None
        down_change = None
        if self.prev_up_price is not None:
            up_change = ((up_price - self.prev_up_price) / self.prev_up_price) * 100
            down_change = ((down_price - self.prev_down_price) / self.prev_down_price) * 100

        # Update previous prices
        self.prev_up_price = up_price
        self.prev_down_price = down_price

        # Calculate market caps (assuming $1M total market cap)
        total_cap = 1_000_000
        up_cap = up_price * total_cap
        down_cap = down_price * total_cap

        # Draw header
        subtitle = f"Updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
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

        # Recent trades panel (if available)
        up_trades = self.fetch_trades_data(self.token_up)
        down_trades = self.fetch_trades_data(self.token_down)

        if up_trades or down_trades:
            # Combine and sort trades
            all_trades = []

            for trade in up_trades:
                all_trades.append({
                    **trade,
                    'side': 'BUY',
                    'outcome': 'UP'
                })

            for trade in down_trades:
                all_trades.append({
                    **trade,
                    'side': 'SELL',
                    'outcome': 'DOWN'
                })

            # Sort by timestamp (if available)
            if all_trades and 'timestamp' in all_trades[0]:
                all_trades.sort(key=lambda t: t.get('timestamp', ''), reverse=True)

            # Format trades
            trade_lines = [format_trade(t) for t in all_trades[:RECENT_TRADES_COUNT]]
            print(draw_box(f"RECENT TRADES (Last {len(trade_lines)})", trade_lines))
            print()

            # Volume metrics
            volume_content = format_volume_metrics(all_trades)
            print(draw_box("VOLUME METRICS", volume_content))
            print()
        else:
            # Trades not available
            print(draw_box("RECENT TRADES", [
                "⚠ Trade stream not available via CLOB API"
            ]))
            print()

        # Footer
        print(f"Press Ctrl+C to exit | Next update in {self.poll_interval}s...")

        return True

    def run(self):
        """Main monitoring loop"""
        if not self.validate_token_ids():
            return

        print(f"Starting live monitor for {self.market_name}")
        print(f"UP token: {self.token_up[:20]}...")
        print(f"DOWN token: {self.token_down[:20]}...")
        print(f"Poll interval: {self.poll_interval}s")
        print("\nPress Ctrl+C to exit\n")

        time.sleep(2)  # Give user time to read

        while self.running:
            success = self.update_display()

            if not success:
                print(f"\nRetrying in {self.poll_interval}s...")

            time.sleep(self.poll_interval)


def main():
    parser = argparse.ArgumentParser(
        description='Live market monitor for Polymarket',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Monitor a 1-hour BTC market
  python live_monitor.py --token-up 123456... --token-down 789012...

  # Custom poll interval
  python live_monitor.py --token-up 123456... --token-down 789012... --interval 10

  # Named market
  python live_monitor.py --token-up 123456... --token-down 789012... --market-name "BTC 1hr"
        '''
    )
    parser.add_argument('--token-up', type=str, required=True,
                       help='Token ID for UP outcome')
    parser.add_argument('--token-down', type=str, required=True,
                       help='Token ID for DOWN outcome')
    parser.add_argument('--interval', type=int, default=DEFAULT_POLL_INTERVAL,
                       help=f'Poll interval in seconds (default: {DEFAULT_POLL_INTERVAL})')
    parser.add_argument('--market-name', type=str, default="",
                       help='Display name for the market')

    args = parser.parse_args()

    # Validate interval
    if args.interval < MIN_POLL_INTERVAL or args.interval > MAX_POLL_INTERVAL:
        print(f"Error: Interval must be between {MIN_POLL_INTERVAL} and {MAX_POLL_INTERVAL} seconds")
        sys.exit(1)

    # Create and run monitor
    monitor = MarketMonitor(
        token_up=args.token_up,
        token_down=args.token_down,
        market_name=args.market_name,
        poll_interval=args.interval
    )

    monitor.run()


if __name__ == "__main__":
    main()
