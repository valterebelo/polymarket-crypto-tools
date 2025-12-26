"""
SQLite database layer for storing and querying Polymarket tick data (trades).

This module provides persistent storage for:
- Individual trades (tick data) from WebSocket and REST API
- Market metadata for fast querying

Database Schema:
- trades: Individual trade records with deduplication
- markets: Market metadata cache
"""

import sqlite3
import csv
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import hashlib


class TickDatabase:
    """Manages SQLite database for tick data storage and retrieval."""

    def __init__(self, db_path: str = "data/ticks.db"):
        """
        Initialize database connection and create schema if needed.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable dict-like access

        self._create_schema()

    def _create_schema(self):
        """Create database tables and indices if they don't exist."""
        cursor = self.conn.cursor()

        # Markets table: Store market metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                market_id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                outcome_up TEXT,
                outcome_down TEXT,
                token_up TEXT NOT NULL,
                token_down TEXT NOT NULL,
                created_at TEXT,
                closed BOOLEAN DEFAULT 0,
                closed_time TEXT,
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL
            )
        """)

        # Trades table: Individual tick data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE NOT NULL,
                market_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
                outcome TEXT,
                price REAL NOT NULL,
                size REAL NOT NULL,
                fee_rate_bps INTEGER,
                timestamp TEXT NOT NULL,
                source TEXT NOT NULL CHECK (source IN ('websocket', 'rest_api')),
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (market_id) REFERENCES markets(market_id)
            )
        """)

        # Create indices for fast querying
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_market_id
            ON trades(market_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_asset_id
            ON trades(asset_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_timestamp
            ON trades(timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_trades_market_timestamp
            ON trades(market_id, timestamp)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_markets_closed
            ON markets(closed)
        """)

        self.conn.commit()

    def _generate_trade_id(self, asset_id: str, timestamp: str, price: float, size: float) -> str:
        """
        Generate unique trade ID from trade data.

        Uses composite key to prevent duplicates when WebSocket and REST API
        return the same trades.

        Args:
            asset_id: Token ID
            timestamp: ISO 8601 timestamp
            price: Trade price
            size: Trade size

        Returns:
            Unique trade ID string
        """
        # Create composite key
        key = f"{asset_id}_{timestamp}_{price:.6f}_{size:.6f}"

        # Hash for consistent length (optional, can use key directly)
        return hashlib.md5(key.encode()).hexdigest()

    def insert_market(self, market_data: Dict) -> bool:
        """
        Insert or update market metadata.

        Args:
            market_data: Dictionary with keys:
                - market_id: Market ID (required)
                - question: Market question (required)
                - outcome_up: Up/Yes outcome label
                - outcome_down: Down/No outcome label
                - token_up: Up/Yes token ID (required)
                - token_down: Down/No token ID (required)
                - created_at: ISO timestamp
                - closed: Boolean
                - closed_time: ISO timestamp

        Returns:
            True if successful
        """
        cursor = self.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()

        cursor.execute("""
            INSERT OR REPLACE INTO markets (
                market_id, question, outcome_up, outcome_down,
                token_up, token_down, created_at, closed, closed_time,
                first_seen, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?,
                COALESCE((SELECT first_seen FROM markets WHERE market_id = ?), ?),
                ?)
        """, (
            market_data['market_id'],
            market_data['question'],
            market_data.get('outcome_up'),
            market_data.get('outcome_down'),
            market_data['token_up'],
            market_data['token_down'],
            market_data.get('created_at'),
            market_data.get('closed', False),
            market_data.get('closed_time'),
            market_data['market_id'],  # For COALESCE subquery
            now,  # first_seen if new
            now   # last_updated
        ))

        self.conn.commit()
        return True

    def insert_trade(self, trade_data: Dict) -> bool:
        """
        Insert trade into database.

        Automatically generates trade_id and handles duplicates with
        INSERT OR IGNORE.

        Args:
            trade_data: Dictionary with keys:
                - market_id: Market ID (required)
                - asset_id: Token ID (required)
                - side: "BUY" or "SELL" (required)
                - outcome: "UP", "DOWN", etc. (optional)
                - price: Trade price (required)
                - size: Trade size (required)
                - fee_rate_bps: Fee rate in basis points (optional)
                - timestamp: ISO 8601 timestamp (required)
                - source: "websocket" or "rest_api" (required)

        Returns:
            True if inserted, False if duplicate
        """
        cursor = self.conn.cursor()

        # Generate unique trade ID
        trade_id = self._generate_trade_id(
            trade_data['asset_id'],
            trade_data['timestamp'],
            trade_data['price'],
            trade_data['size']
        )

        recorded_at = datetime.now(timezone.utc).isoformat()

        try:
            cursor.execute("""
                INSERT OR IGNORE INTO trades (
                    trade_id, market_id, asset_id, side, outcome,
                    price, size, fee_rate_bps, timestamp, source, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                trade_data['market_id'],
                trade_data['asset_id'],
                trade_data['side'],
                trade_data.get('outcome'),
                trade_data['price'],
                trade_data['size'],
                trade_data.get('fee_rate_bps'),
                trade_data['timestamp'],
                trade_data['source'],
                recorded_at
            ))

            self.conn.commit()

            # Check if row was inserted (rowcount > 0) or ignored (rowcount == 0)
            return cursor.rowcount > 0

        except sqlite3.IntegrityError:
            return False

    def insert_trades_batch(self, trades: List[Dict]) -> int:
        """
        Insert multiple trades in a single transaction.

        Args:
            trades: List of trade dictionaries

        Returns:
            Number of trades successfully inserted (excluding duplicates)
        """
        inserted_count = 0

        for trade in trades:
            if self.insert_trade(trade):
                inserted_count += 1

        return inserted_count

    def get_market(self, market_id: str) -> Optional[Dict]:
        """
        Get market metadata by ID.

        Args:
            market_id: Market ID

        Returns:
            Dictionary with market data or None if not found
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT * FROM markets WHERE market_id = ?
        """, (market_id,))

        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def get_trades_by_market(self, market_id: str,
                           start_time: Optional[str] = None,
                           end_time: Optional[str] = None,
                           outcome: Optional[str] = None) -> List[Dict]:
        """
        Query trades for a market with optional filtering.

        Args:
            market_id: Market ID
            start_time: ISO 8601 timestamp (inclusive)
            end_time: ISO 8601 timestamp (exclusive)
            outcome: Filter by outcome ("UP", "DOWN", etc.)

        Returns:
            List of trade dictionaries sorted by timestamp
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM trades WHERE market_id = ?"
        params = [market_id]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp < ?"
            params.append(end_time)

        if outcome:
            query += " AND outcome = ?"
            params.append(outcome)

        query += " ORDER BY timestamp ASC"

        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_trades_by_token(self, asset_id: str,
                           start_time: Optional[str] = None,
                           end_time: Optional[str] = None) -> List[Dict]:
        """
        Query trades for a specific token.

        Args:
            asset_id: Token ID
            start_time: ISO 8601 timestamp (inclusive)
            end_time: ISO 8601 timestamp (exclusive)

        Returns:
            List of trade dictionaries sorted by timestamp
        """
        cursor = self.conn.cursor()

        query = "SELECT * FROM trades WHERE asset_id = ?"
        params = [asset_id]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)

        if end_time:
            query += " AND timestamp < ?"
            params.append(end_time)

        query += " ORDER BY timestamp ASC"

        cursor.execute(query, params)

        return [dict(row) for row in cursor.fetchall()]

    def get_market_summary(self, market_id: str) -> Dict:
        """
        Get summary statistics for a market.

        Args:
            market_id: Market ID

        Returns:
            Dictionary with summary stats:
                - total_trades: Total number of trades
                - total_volume: Sum of trade sizes
                - oldest_trade: Earliest timestamp
                - newest_trade: Latest timestamp
                - sources: Dict of trade counts by source
        """
        cursor = self.conn.cursor()

        # Basic stats
        cursor.execute("""
            SELECT
                COUNT(*) as total_trades,
                SUM(size) as total_volume,
                MIN(timestamp) as oldest_trade,
                MAX(timestamp) as newest_trade
            FROM trades
            WHERE market_id = ?
        """, (market_id,))

        stats = dict(cursor.fetchone())

        # Count by source
        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM trades
            WHERE market_id = ?
            GROUP BY source
        """, (market_id,))

        stats['sources'] = {row['source']: row['count'] for row in cursor.fetchall()}

        return stats

    def list_markets(self, closed: Optional[bool] = None) -> List[Dict]:
        """
        List all markets in database.

        Args:
            closed: Filter by closed status (None = all markets)

        Returns:
            List of market dictionaries
        """
        cursor = self.conn.cursor()

        if closed is None:
            cursor.execute("SELECT * FROM markets ORDER BY last_updated DESC")
        else:
            cursor.execute("""
                SELECT * FROM markets
                WHERE closed = ?
                ORDER BY last_updated DESC
            """, (closed,))

        return [dict(row) for row in cursor.fetchall()]

    def export_to_csv(self, market_id: str, output_path: str) -> int:
        """
        Export trades for a market to CSV file.

        CSV format:
        timestamp,market_id,asset_id,side,outcome,price,size,value,fee_rate_bps,source

        Args:
            market_id: Market ID
            output_path: Path to output CSV file

        Returns:
            Number of trades exported
        """
        trades = self.get_trades_by_market(market_id)

        if not trades:
            return 0

        with open(output_path, 'w', newline='') as f:
            fieldnames = [
                'timestamp', 'market_id', 'asset_id', 'side', 'outcome',
                'price', 'size', 'value', 'fee_rate_bps', 'source'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for trade in trades:
                # Calculate trade value
                value = trade['price'] * trade['size']

                writer.writerow({
                    'timestamp': trade['timestamp'],
                    'market_id': trade['market_id'],
                    'asset_id': trade['asset_id'],
                    'side': trade['side'],
                    'outcome': trade.get('outcome', ''),
                    'price': trade['price'],
                    'size': trade['size'],
                    'value': f"{value:.4f}",
                    'fee_rate_bps': trade.get('fee_rate_bps', ''),
                    'source': trade['source']
                })

        return len(trades)

    def get_latest_trade_timestamp(self, asset_id: str) -> Optional[str]:
        """
        Get timestamp of most recent trade for a token.

        Useful for resuming fetches without duplicates.

        Args:
            asset_id: Token ID

        Returns:
            ISO 8601 timestamp or None if no trades found
        """
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT MAX(timestamp) as latest
            FROM trades
            WHERE asset_id = ?
        """, (asset_id,))

        row = cursor.fetchone()
        return row['latest'] if row['latest'] else None

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        """Context manager support."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
