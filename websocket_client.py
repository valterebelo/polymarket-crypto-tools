#!/usr/bin/env python3
"""
WebSocket Client for Polymarket CLOB Market Channel

Provides real-time orderbook updates, price changes, and trade events
via the public Market Channel (no authentication required).
"""
import json
import threading
import time
from typing import Callable, Dict, List, Optional
from collections import deque
from datetime import datetime, timezone

try:
    from websocket import WebSocketApp, WebSocketException
except ImportError:
    print("Error: websocket-client not installed. Run: pip install websocket-client")
    raise


# WebSocket endpoint
WSS_URL = "wss://ws-subscriptions-clob.polymarket.com"
MARKET_CHANNEL = "market"


class MarketWebSocketClient:
    """
    WebSocket client for Polymarket CLOB Market Channel.
    
    Receives real-time events:
    - book: Orderbook snapshots (on subscribe and after trades)
    - price_change: When orders are placed/cancelled
    - tick_size_change: When tick size changes
    - last_trade_price: When trades execute (THIS IS THE TRADE STREAM)
    """
    
    def __init__(
        self,
        asset_ids: List[str],
        on_book: Optional[Callable[[Dict], None]] = None,
        on_price_change: Optional[Callable[[Dict], None]] = None,
        on_trade: Optional[Callable[[Dict], None]] = None,
        on_tick_size_change: Optional[Callable[[Dict], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connected: Optional[Callable[[], None]] = None,
        on_disconnected: Optional[Callable[[], None]] = None,
        max_trades_history: int = 100,
        verbose: bool = False
    ):
        """
        Initialize WebSocket client.
        
        Args:
            asset_ids: List of token IDs (asset IDs) to subscribe to
            on_book: Callback for orderbook updates
            on_price_change: Callback for price change events
            on_trade: Callback for trade events (last_trade_price)
            on_tick_size_change: Callback for tick size changes
            on_error: Callback for errors
            on_connected: Callback when connected
            on_disconnected: Callback when disconnected
            max_trades_history: Max trades to keep in history
            verbose: Print debug messages
        """
        self.asset_ids = asset_ids
        self.on_book_callback = on_book
        self.on_price_change_callback = on_price_change
        self.on_trade_callback = on_trade
        self.on_tick_size_change_callback = on_tick_size_change
        self.on_error_callback = on_error
        self.on_connected_callback = on_connected
        self.on_disconnected_callback = on_disconnected
        self.verbose = verbose
        
        self.ws: Optional[WebSocketApp] = None
        self.ws_thread: Optional[threading.Thread] = None
        self.ping_thread: Optional[threading.Thread] = None
        self.running = False
        self.connected = False
        
        # Data storage
        self.orderbooks: Dict[str, Dict] = {}  # asset_id -> {bids, asks}
        self.trades_history: deque = deque(maxlen=max_trades_history)
        self.last_prices: Dict[str, Dict] = {}  # asset_id -> {price, side, size, timestamp}
        
        # Thread safety
        self._lock = threading.Lock()
    
    def _log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.verbose:
            timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S.%f')[:-3]
            print(f"[WSS {timestamp}] {message}")
    
    def _on_open(self, ws):
        """Handle WebSocket connection opened."""
        self._log("Connection opened, subscribing to assets...")
        
        # Subscribe to market channel with asset IDs
        subscribe_msg = {
            "assets_ids": self.asset_ids,
            "type": MARKET_CHANNEL
        }
        ws.send(json.dumps(subscribe_msg))
        self._log(f"Subscribed to {len(self.asset_ids)} asset(s)")
        
        self.connected = True
        
        # Start ping thread to keep connection alive
        self.ping_thread = threading.Thread(target=self._ping_loop, args=(ws,), daemon=True)
        self.ping_thread.start()
        
        if self.on_connected_callback:
            self.on_connected_callback()
    
    def _on_message(self, ws, message: str):
        """Handle incoming WebSocket message."""
        # Handle PONG responses
        if message == "PONG":
            self._log("Received PONG")
            return
        
        try:
            data = json.loads(message)
            event_type = data.get("event_type", "")
            
            # Don't log price_change events - too frequent
            if event_type != "price_change":
                self._log(f"Received event: {event_type}")
            
            if event_type == "book":
                self._handle_book_event(data)
            elif event_type == "price_change":
                self._handle_price_change_event(data)
            elif event_type == "last_trade_price":
                self._handle_trade_event(data)
            elif event_type == "tick_size_change":
                self._handle_tick_size_change_event(data)
            else:
                self._log(f"Unknown event type: {event_type}")
                
        except json.JSONDecodeError as e:
            self._log(f"Failed to parse message: {e}")
        except Exception as e:
            self._log(f"Error processing message: {e}")
            if self.on_error_callback:
                self.on_error_callback(e)
    
    def _handle_book_event(self, data: Dict):
        """Handle orderbook snapshot event."""
        asset_id = data.get("asset_id", "")
        
        with self._lock:
            self.orderbooks[asset_id] = {
                "bids": data.get("bids", []),
                "asks": data.get("asks", []),
                "timestamp": data.get("timestamp", ""),
                "hash": data.get("hash", "")
            }
        
        if self.on_book_callback:
            self.on_book_callback(data)
    
    def _handle_price_change_event(self, data: Dict):
        """Handle price change event."""
        if self.on_price_change_callback:
            self.on_price_change_callback(data)
    
    def _handle_trade_event(self, data: Dict):
        """Handle last_trade_price event (trade execution)."""
        asset_id = data.get("asset_id", "")
        
        trade_record = {
            "asset_id": asset_id,
            "price": data.get("price", "0"),
            "size": data.get("size", "0"),
            "side": data.get("side", ""),
            "fee_rate_bps": data.get("fee_rate_bps", "0"),
            "timestamp": data.get("timestamp", ""),
            "market": data.get("market", "")
        }
        
        with self._lock:
            self.trades_history.appendleft(trade_record)
            self.last_prices[asset_id] = trade_record
        
        if self.on_trade_callback:
            self.on_trade_callback(trade_record)
    
    def _handle_tick_size_change_event(self, data: Dict):
        """Handle tick size change event."""
        if self.on_tick_size_change_callback:
            self.on_tick_size_change_callback(data)
    
    def _on_error(self, ws, error):
        """Handle WebSocket error."""
        self._log(f"WebSocket error: {error}")
        if self.on_error_callback:
            self.on_error_callback(error)
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket connection closed."""
        self._log(f"Connection closed: {close_status_code} - {close_msg}")
        self.connected = False
        
        if self.on_disconnected_callback:
            self.on_disconnected_callback()
    
    def _ping_loop(self, ws):
        """Send periodic pings to keep connection alive."""
        while self.running and self.connected:
            try:
                ws.send("PING")
                self._log("Sent PING")
            except Exception as e:
                self._log(f"Ping failed: {e}")
                break
            time.sleep(10)  # Ping every 10 seconds
    
    def connect(self):
        """Connect to WebSocket server."""
        if self.running:
            self._log("Already running")
            return
        
        self.running = True
        url = f"{WSS_URL}/ws/{MARKET_CHANNEL}"
        
        self._log(f"Connecting to {url}")
        
        self.ws = WebSocketApp(
            url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close
        )
        
        # Run WebSocket in separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()
    
    def disconnect(self):
        """Disconnect from WebSocket server."""
        self._log("Disconnecting...")
        self.running = False
        
        if self.ws:
            self.ws.close()
        
        self.connected = False
    
    def get_orderbook(self, asset_id: str) -> Optional[Dict]:
        """Get current orderbook for an asset."""
        with self._lock:
            return self.orderbooks.get(asset_id)
    
    def get_recent_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades."""
        with self._lock:
            return list(self.trades_history)[:limit]
    
    def get_last_price(self, asset_id: str) -> Optional[Dict]:
        """Get last trade price for an asset."""
        with self._lock:
            return self.last_prices.get(asset_id)
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.connected


# Convenience function for quick testing
def test_connection(asset_ids: List[str], duration: int = 30):
    """
    Test WebSocket connection.
    
    Args:
        asset_ids: List of token IDs to subscribe to
        duration: How long to run test (seconds)
    """
    print(f"Testing WebSocket connection for {duration}s...")
    print(f"Subscribing to {len(asset_ids)} asset(s)")
    
    def on_trade(trade):
        print(f"\n🔔 TRADE: {trade['side']} {trade['size']} @ ${trade['price']}")
    
    def on_book(book):
        bids = book.get('bids', [])[:3]
        asks = book.get('asks', [])[:3]
        print(f"\n📖 BOOK UPDATE: {len(bids)} bids, {len(asks)} asks")
    
    def on_connected():
        print("✅ Connected!")
    
    def on_disconnected():
        print("❌ Disconnected!")
    
    client = MarketWebSocketClient(
        asset_ids=asset_ids,
        on_trade=on_trade,
        on_book=on_book,
        on_connected=on_connected,
        on_disconnected=on_disconnected,
        verbose=True
    )
    
    client.connect()
    
    try:
        time.sleep(duration)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        client.disconnect()
        print("Test complete")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python websocket_client.py <asset_id1> [asset_id2] ...")
        print("Example: python websocket_client.py 123456789...")
        sys.exit(1)
    
    test_connection(sys.argv[1:], duration=60)