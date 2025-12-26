"""
Test script for authenticated historical trade fetching.

This script tests if API authentication is working and can fetch
historical trade data from the CLOB API.

Prerequisites:
- Set environment variables: POLYMARKET_API_KEY, POLYMARKET_SECRET,
  POLYMARKET_PASSPHRASE, POLYMARKET_ADDRESS

Usage:
    # Test with default token
    python test_authenticated_trades.py

    # Test with specific token
    python test_authenticated_trades.py --token-id <TOKEN_ID>

    # Test with more trades
    python test_authenticated_trades.py --limit 500
"""

import argparse
from datetime import datetime
from api_client import PolymarketAPIClient
from auth_manager import AuthManager


def test_authentication():
    """Test if authentication credentials are configured."""
    print("="*70)
    print("STEP 1: Testing Authentication Setup")
    print("="*70)

    auth = AuthManager()

    if not auth.has_credentials():
        print("❌ Authentication NOT configured")
        print("\nPlease set environment variables:")
        print("  export POLYMARKET_API_KEY='your-api-key'")
        print("  export POLYMARKET_SECRET='your-secret'")
        print("  export POLYMARKET_PASSPHRASE='your-passphrase'")
        print("  export POLYMARKET_ADDRESS='your-address'")
        print("\nSee AUTHENTICATION_SETUP.md for detailed instructions.")
        return False

    print("✅ Credentials found!")
    print(f"   API Key: {auth.api_key[:8]}...{auth.api_key[-8:]}")
    print(f"   Address: {auth.address}")

    # Test signature generation
    try:
        headers = auth.get_auth_headers("GET", "/test")
        print("✅ Signature generation working")
        return True
    except Exception as e:
        print(f"❌ Signature generation failed: {e}")
        return False


def test_trade_fetch(token_id: str, limit: int = 100):
    """Test fetching historical trades with authentication."""
    print("\n" + "="*70)
    print("STEP 2: Fetching Historical Trades")
    print("="*70)

    auth = AuthManager()
    client = PolymarketAPIClient(auth_manager=auth)

    print(f"Token ID: {token_id[:20]}...{token_id[-20:]}")
    print(f"Limit: {limit}")
    print("\nFetching trades...")

    try:
        trades = client.get_trades(token_id, limit=limit)

        if not trades:
            print("❌ No trades returned")
            print("\nPossible reasons:")
            print("  - Token has no trade history")
            print("  - Authentication failed (401)")
            print("  - API endpoint unavailable")
            print("\nTry with a different token ID from an active market.")
            return False

        print(f"✅ Success! Fetched {len(trades)} trades")

        # Display sample trades
        print("\n" + "-"*70)
        print("SAMPLE TRADES (first 10)")
        print("-"*70)
        print(f"{'Timestamp':<25} {'Price':<12} {'Size':<15} {'Side':<8}")
        print("-"*70)

        for trade in trades[:10]:
            timestamp = trade.get('timestamp', 'N/A')
            if isinstance(timestamp, (int, float)):
                # Convert unix timestamp to datetime
                dt = datetime.fromtimestamp(timestamp / 1000 if timestamp > 1e12 else timestamp)
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')

            price = trade.get('price', 0)
            size = trade.get('size', 0)
            side = trade.get('side', 'N/A')

            print(f"{timestamp:<25} {price:<12} {size:<15.2f} {side:<8}")

        if len(trades) > 10:
            print(f"... and {len(trades) - 10} more trades")

        # Show time range
        print("\n" + "-"*70)
        print("DATA SUMMARY")
        print("-"*70)

        timestamps = [t.get('timestamp') for t in trades if 'timestamp' in t]
        if timestamps:
            try:
                # Handle both unix timestamps and ISO strings
                def parse_ts(ts):
                    if isinstance(ts, (int, float)):
                        return datetime.fromtimestamp(ts / 1000 if ts > 1e12 else ts)
                    else:
                        return datetime.fromisoformat(ts.replace('Z', '+00:00'))

                dts = [parse_ts(ts) for ts in timestamps]
                oldest = min(dts)
                newest = max(dts)

                print(f"Oldest trade: {oldest.isoformat()}")
                print(f"Newest trade: {newest.isoformat()}")

                time_span = newest - oldest
                print(f"Time span: {time_span}")
            except Exception as e:
                print(f"Could not parse timestamps: {e}")

        # Show price range
        prices = [float(t.get('price', 0)) for t in trades if 'price' in t]
        if prices:
            print(f"\nPrice range: {min(prices):.4f} - {max(prices):.4f}")

        # Show volume
        volumes = [float(t.get('size', 0)) for t in trades if 'size' in t]
        if volumes:
            print(f"Total volume: {sum(volumes):.2f}")

        print("="*70)
        return True

    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main test runner."""
    parser = argparse.ArgumentParser(description="Test authenticated trade fetching")
    parser.add_argument('--token-id',
                       default="96335067832619596263476394965563507657401324223032703267023353422994551721776",
                       help='Token ID to test (default: Bitcoin Up token)')
    parser.add_argument('--limit', type=int, default=100,
                       help='Number of trades to fetch (default: 100)')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("POLYMARKET AUTHENTICATED TRADE FETCH TEST")
    print("="*70)
    print()

    # Test authentication
    auth_ok = test_authentication()

    if not auth_ok:
        print("\n❌ Authentication test failed. Fix credentials and try again.")
        return

    # Test trade fetch
    fetch_ok = test_trade_fetch(args.token_id, args.limit)

    # Final summary
    print("\n" + "="*70)
    if auth_ok and fetch_ok:
        print("✅ ALL TESTS PASSED!")
        print("\nYou can now:")
        print("  - Fetch historical trades via API")
        print("  - Use authenticated endpoints")
        print("  - Backfill tick data from recent history")
    else:
        print("❌ TESTS FAILED")
        print("\nCheck:")
        print("  - Credentials are correct")
        print("  - Token ID is valid")
        print("  - API endpoint is accessible")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
