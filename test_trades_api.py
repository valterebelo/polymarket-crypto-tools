"""
Exploratory script to test Polymarket /trades API endpoint capabilities.

This script empirically determines:
1. Maximum limit parameter supported
2. Whether pagination (offset) is supported
3. Historical depth of trade data
4. Response format and data quality

Run this BEFORE implementing tick_fetcher.py to understand API limitations.
"""

import sys
from datetime import datetime, timezone
from api_client import PolymarketAPIClient
import time


def test_limit_parameter(client: PolymarketAPIClient, token_id: str):
    """Test different limit values to find maximum."""
    print("\n" + "="*70)
    print("TEST 1: Maximum Limit Parameter")
    print("="*70)

    test_limits = [100, 200, 500, 1000, 5000]

    results = []

    for limit in test_limits:
        print(f"\nRequesting limit={limit}...")
        try:
            trades = client.get_trades(token_id, limit=limit)

            if trades is None:
                print(f"  ❌ Failed: API returned None")
                results.append((limit, 0, "Failed"))
                continue

            count = len(trades) if isinstance(trades, list) else 0
            print(f"  ✓ Received {count} trades")

            if count > 0 and isinstance(trades, list):
                # Show timestamp range
                try:
                    timestamps = [t.get('timestamp') for t in trades if 'timestamp' in t]
                    if timestamps:
                        oldest = min(timestamps)
                        newest = max(timestamps)
                        print(f"    Oldest: {oldest}")
                        print(f"    Newest: {newest}")
                except Exception as e:
                    print(f"    Could not parse timestamps: {e}")

            results.append((limit, count, "Success" if count > 0 else "Empty"))

            time.sleep(0.5)  # Rate limiting

        except Exception as e:
            print(f"  ❌ Error: {e}")
            results.append((limit, 0, f"Error: {str(e)[:50]}"))

    # Summary
    print("\n" + "-"*70)
    print("SUMMARY - Limit Parameter Tests:")
    print("-"*70)
    for limit, count, status in results:
        print(f"  limit={limit:5d} → {count:5d} trades ({status})")

    # Determine effective max
    max_received = max([count for _, count, _ in results])
    print(f"\n📊 Maximum trades received: {max_received}")


def test_pagination(client: PolymarketAPIClient, token_id: str):
    """Test if offset parameter is supported for pagination."""
    print("\n" + "="*70)
    print("TEST 2: Pagination Support (offset parameter)")
    print("="*70)

    try:
        print("\nFetching batch 1 (offset=0, limit=100)...")
        batch1 = client.get_trades(token_id, limit=100)

        if not batch1 or not isinstance(batch1, list):
            print("❌ Failed to fetch first batch")
            return

        print(f"✓ Batch 1: {len(batch1)} trades")

        # Try to modify the API client call to test offset
        # Note: Current api_client.py doesn't support offset parameter
        print("\nTrying offset=100...")

        # Direct API test (bypassing current client)
        import requests
        from config import CLOB_API_BASE

        url = f"{CLOB_API_BASE}/trades"
        params = {"token_id": token_id, "limit": 100, "offset": 100}

        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            batch2 = response.json()
            if isinstance(batch2, list):
                print(f"✓ Batch 2: {len(batch2)} trades")

                # Check if different from batch 1
                if len(batch2) > 0:
                    b1_ids = set(str(t.get('id', '')) for t in batch1 if 'id' in t)
                    b2_ids = set(str(t.get('id', '')) for t in batch2 if 'id' in t)

                    overlap = len(b1_ids & b2_ids)
                    unique_b2 = len(b2_ids - b1_ids)

                    print(f"  Overlap: {overlap} trades")
                    print(f"  Unique in batch 2: {unique_b2} trades")

                    if unique_b2 > 0:
                        print("\n✅ PAGINATION SUPPORTED: offset parameter works!")
                    else:
                        print("\n⚠️  Offset returned same data - pagination may not work")
                else:
                    print("\n⚠️  Batch 2 empty - may have reached end of data")
            else:
                print(f"❌ Unexpected response format: {type(batch2)}")
        else:
            print(f"❌ HTTP {response.status_code}: {response.text[:100]}")
            print("⚠️  Offset parameter not supported or different API needed")

    except Exception as e:
        print(f"❌ Error testing pagination: {e}")
        print("⚠️  Pagination likely not supported")


def test_historical_depth(client: PolymarketAPIClient, token_id: str):
    """Determine how far back trade history goes."""
    print("\n" + "="*70)
    print("TEST 3: Historical Depth")
    print("="*70)

    try:
        print("\nFetching maximum available trades...")
        trades = client.get_trades(token_id, limit=1000)

        if not trades or not isinstance(trades, list):
            print("❌ Failed to fetch trades")
            return

        print(f"✓ Fetched {len(trades)} trades")

        if len(trades) == 0:
            print("⚠️  No trades available for this token")
            return

        # Parse timestamps
        timestamps = []
        for trade in trades:
            ts = trade.get('timestamp')
            if ts:
                try:
                    # Handle different timestamp formats
                    if isinstance(ts, (int, float)):
                        # Unix timestamp (ms or seconds)
                        if ts > 1e12:  # milliseconds
                            dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
                        else:  # seconds
                            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    elif isinstance(ts, str):
                        # ISO 8601 string
                        if 'Z' in ts or '+' in ts:
                            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(ts)
                    else:
                        continue

                    timestamps.append(dt)
                except Exception as e:
                    print(f"  Warning: Could not parse timestamp {ts}: {e}")

        if not timestamps:
            print("⚠️  Could not parse any timestamps")
            return

        oldest = min(timestamps)
        newest = max(timestamps)
        now = datetime.now(timezone.utc)

        time_span = newest - oldest
        age = now - oldest

        print(f"\n📅 Historical Depth:")
        print(f"  Oldest trade: {oldest.isoformat()}")
        print(f"  Newest trade: {newest.isoformat()}")
        print(f"  Time span: {time_span}")
        print(f"  Age of oldest trade: {age}")

        # Provide interpretation
        hours = age.total_seconds() / 3600
        if hours < 24:
            print(f"  → Approximately {hours:.1f} hours of history")
        elif hours < 168:  # 7 days
            print(f"  → Approximately {hours/24:.1f} days of history")
        else:
            print(f"  → Approximately {hours/(24*7):.1f} weeks of history")

    except Exception as e:
        print(f"❌ Error: {e}")


def test_data_format(client: PolymarketAPIClient, token_id: str):
    """Examine the structure of trade data returned."""
    print("\n" + "="*70)
    print("TEST 4: Data Format & Fields")
    print("="*70)

    try:
        trades = client.get_trades(token_id, limit=5)

        if not trades or not isinstance(trades, list):
            print("❌ Failed to fetch trades")
            return

        if len(trades) == 0:
            print("⚠️  No trades available")
            return

        print(f"\nExamining first trade (out of {len(trades)} total):")
        trade = trades[0]

        print("\nFields present:")
        for key, value in trade.items():
            value_str = str(value)
            if len(value_str) > 60:
                value_str = value_str[:60] + "..."
            print(f"  {key:20s}: {value_str}")

        # Check for required fields
        required = ['price', 'size', 'side', 'timestamp']
        missing = [f for f in required if f not in trade]

        if missing:
            print(f"\n⚠️  Missing required fields: {missing}")
        else:
            print(f"\n✅ All required fields present")

    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    """Run all API tests."""
    print("="*70)
    print("Polymarket /trades API Endpoint Testing")
    print("="*70)

    # Use Bitcoin market token from cache
    # Token ID from: Bitcoin Up or Down market
    token_id = "96335067832619596263476394965563507657401324223032703267023353422994551721776"
    market_id = "996577"

    print(f"\nTest Token ID: {token_id[:20]}...{token_id[-20:]}")
    print(f"Market: Bitcoin Up or Down")
    print(f"Market ID: {market_id}")

    client = PolymarketAPIClient()

    # Run tests
    test_data_format(client, token_id)
    test_limit_parameter(client, token_id)
    test_pagination(client, token_id)
    test_historical_depth(client, token_id)

    # Final summary
    print("\n" + "="*70)
    print("TESTING COMPLETE")
    print("="*70)
    print("\nNext Steps:")
    print("1. Review findings above")
    print("2. Update tick_fetcher.py design based on discovered limits")
    print("3. Document findings in CLAUDE.md")
    print("="*70)


if __name__ == "__main__":
    main()
