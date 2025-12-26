"""
WebSocket recorder for persistent tick data collection.

Records real-time trades from Polymarket WebSocket to SQLite database.
This is the PRIMARY data source since REST API requires authentication.

Usage:
    recorder = TickRecorder(market_ids=["996577", "996578"])
    recorder.start_recording()  # Runs until stopped with Ctrl+C
"""

import signal
import sys
import time
from typing import List, Dict, Optional
from datetime import datetime, timezone

from websocket_client import MarketWebSocketClient
from tick_database import TickDatabase
from api_client import PolymarketAPIClient
from config import TICK_DB_PATH


class TickRecorder:
    """Records trades from WebSocket to database."""

    def __init__(self, market_ids: List[str], db_path: str = TICK_DB_PATH):
        """
        Initialize tick recorder.

        Args:
            market_ids: List of market IDs to record
            db_path: Path to SQLite database
        """
        self.market_ids = market_ids
        self.db_path = db_path

        self.db: Optional[TickDatabase] = None
        self.ws_client: Optional[MarketWebSocketClient] = None
        self.api_client = PolymarketAPIClient()

        # Token-to-market mapping: token_id -> (market_id, outcome)
        self.token_map: Dict[str, tuple] = {}

        # Market metadata cache
        self.markets_metadata: Dict[str, Dict] = {}

        # Running flag
        self.running = False

        # Stats
        self.trades_recorded = 0
        self.start_time: Optional[datetime] = None

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, sig, frame):
        """Handle Ctrl+C gracefully."""
        print("\n\nStopping recorder...")
        self.stop_recording()
        sys.exit(0)

    def _fetch_market_metadata(self):
        """Fetch and cache metadata for all markets."""
        print("Fetching market metadata...")

        for market_id in self.market_ids:
            try:
                market = self.api_client.get_market_by_id(market_id)

                if not market:
                    print(f"  ⚠️  Market {market_id} not found")
                    continue

                # Extract tokens and outcomes
                clob_tokens = market.get('clobTokenIds', [])
                outcomes = market.get('outcomes', [])

                if len(clob_tokens) != 2 or len(outcomes) != 2:
                    print(f"  ⚠️  Market {market_id} doesn't have exactly 2 outcomes")
                    continue

                token_up = clob_tokens[0]
                token_down = clob_tokens[1]
                outcome_up = outcomes[0]
                outcome_down = outcomes[1]

                # Store metadata
                self.markets_metadata[market_id] = {
                    'market_id': market_id,
                    'question': market.get('question', ''),
                    'outcome_up': outcome_up,
                    'outcome_down': outcome_down,
                    'token_up': token_up,
                    'token_down': token_down,
                    'created_at': market.get('createdAt'),
                    'closed': market.get('closed', False),
                    'closed_time': market.get('closedTime')
                }

                # Build token mapping
                self.token_map[token_up] = (market_id, outcome_up)
                self.token_map[token_down] = (market_id, outcome_down)

                print(f"  ✓ {market.get('question', '')[:60]}")
                print(f"    Outcomes: {outcome_up} / {outcome_down}")

                time.sleep(0.5)  # Rate limiting

            except Exception as e:
                print(f"  ❌ Error fetching market {market_id}: {e}")

        print(f"\nTotal markets loaded: {len(self.markets_metadata)}")
        print(f"Total tokens to monitor: {len(self.token_map)}")

    def _save_market_metadata(self):
        """Save market metadata to database."""
        print("\nSaving market metadata to database...")

        for market_data in self.markets_metadata.values():
            try:
                self.db.insert_market(market_data)
            except Exception as e:
                print(f"  ⚠️  Error saving market {market_data['market_id']}: {e}")

        print("  ✓ Market metadata saved")

    def _on_trade(self, trade: Dict):
        """
        Callback for WebSocket trade events.

        Enriches trade with market/outcome info and saves to database.

        Args:
            trade: Trade data from WebSocket
        """
        try:
            asset_id = trade.get('asset_id', '')

            # Look up market and outcome
            if asset_id not in self.token_map:
                # Unknown token - skip
                return

            market_id, outcome = self.token_map[asset_id]

            # Prepare trade data for database
            trade_data = {
                'market_id': market_id,
                'asset_id': asset_id,
                'side': trade.get('side', ''),
                'outcome': outcome,
                'price': float(trade.get('price', 0)),
                'size': float(trade.get('size', 0)),
                'fee_rate_bps': int(trade.get('fee_rate_bps', 0)) if trade.get('fee_rate_bps') else None,
                'timestamp': trade.get('timestamp', ''),
                'source': 'websocket'
            }

            # Insert into database
            inserted = self.db.insert_trade(trade_data)

            if inserted:
                self.trades_recorded += 1

                # Periodic status updates
                if self.trades_recorded % 10 == 0:
                    elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
                    rate = self.trades_recorded / elapsed if elapsed > 0 else 0
                    print(f"  ✓ {self.trades_recorded} trades recorded "
                          f"({rate:.1f} trades/sec)")

        except Exception as e:
            print(f"  ⚠️  Error recording trade: {e}")

    def _on_error(self, error: Exception):
        """Callback for WebSocket errors."""
        print(f"WebSocket error: {error}")

    def start_recording(self):
        """Start recording trades from WebSocket."""
        if self.running:
            print("Recorder is already running")
            return

        self.running = True
        self.start_time = datetime.now(timezone.utc)

        print("="*70)
        print("Polymarket Tick Data Recorder")
        print("="*70)
        print(f"Database: {self.db_path}")
        print(f"Markets: {len(self.market_ids)}")
        print(f"Started: {self.start_time.isoformat()}")
        print("="*70)

        # Initialize database
        print("\nInitializing database...")
        self.db = TickDatabase(self.db_path)
        print("  ✓ Database ready")

        # Fetch market metadata
        self._fetch_market_metadata()

        if not self.token_map:
            print("\n❌ No valid markets found. Exiting.")
            return

        # Save metadata to database
        self._save_market_metadata()

        # Get all token IDs
        token_ids = list(self.token_map.keys())

        print(f"\nStarting WebSocket connection...")
        print(f"Monitoring {len(token_ids)} tokens across {len(self.market_ids)} markets")
        print("\nPress Ctrl+C to stop recording\n")
        print("-"*70)

        # Initialize WebSocket client
        self.ws_client = MarketWebSocketClient(
            asset_ids=token_ids,
            on_trade_callback=self._on_trade,
            on_error_callback=self._on_error
        )

        # Connect and start receiving trades
        try:
            self.ws_client.connect()

            # Keep running until stopped
            while self.running and self.ws_client.is_connected():
                time.sleep(1)

        except KeyboardInterrupt:
            print("\n\nRecording stopped by user")

        finally:
            self.stop_recording()

    def stop_recording(self):
        """Stop recording and cleanup."""
        if not self.running:
            return

        self.running = False

        print("\n" + "-"*70)
        print("Stopping recorder...")

        # Disconnect WebSocket
        if self.ws_client:
            print("  Disconnecting WebSocket...")
            self.ws_client.disconnect()

        # Close database
        if self.db:
            print("  Closing database...")
            self.db.close()

        # Print summary
        if self.start_time:
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()
            rate = self.trades_recorded / elapsed if elapsed > 0 else 0

            print("\n" + "="*70)
            print("RECORDING SUMMARY")
            print("="*70)
            print(f"  Duration: {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
            print(f"  Trades recorded: {self.trades_recorded}")
            print(f"  Average rate: {rate:.2f} trades/second")
            print(f"  Database: {self.db_path}")
            print("="*70)

    def get_stats(self) -> Dict:
        """Get current recording statistics."""
        elapsed = 0
        if self.start_time:
            elapsed = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        return {
            'running': self.running,
            'markets': len(self.market_ids),
            'tokens': len(self.token_map),
            'trades_recorded': self.trades_recorded,
            'elapsed_seconds': elapsed,
            'rate': self.trades_recorded / elapsed if elapsed > 0 else 0
        }


def main():
    """Example usage."""
    import argparse

    parser = argparse.ArgumentParser(description="Record Polymarket tick data")
    parser.add_argument('--market-ids', required=True, help='Comma-separated market IDs')
    parser.add_argument('--db-path', default=TICK_DB_PATH, help='Database path')

    args = parser.parse_args()

    market_ids = [m.strip() for m in args.market_ids.split(',')]

    recorder = TickRecorder(market_ids=market_ids, db_path=args.db_path)
    recorder.start_recording()


if __name__ == "__main__":
    main()
