#!/usr/bin/env python3
"""
Quick demo of the market chart explorer functionality.
Tests charting with the known working market ID 1013904.
"""

import sys
from datetime import datetime

# Import the explorer components
from market_chart_explorer import MarketExplorer
from price_history import fetch_price_history, get_market_tokens

def demo_chart():
    """Demonstrate charting functionality."""

    print("\n" + "="*80)
    print("MARKET CHART EXPLORER - DEMO")
    print("="*80)

    # Initialize explorer
    explorer = MarketExplorer()

    # Load markets from cache
    print("\n1. Loading markets from cache...")
    if not explorer.load_markets_from_cache():
        print("   ❌ Failed to load cache")
        return

    print(f"   ✓ Loaded {len(explorer.markets)} markets from cache")

    # Find the test market (1013904)
    print("\n2. Searching for market ID 1013904...")
    test_market = None
    for market in explorer.markets:
        if market.get('id') == '1013904':
            test_market = market
            break

    if not test_market:
        print("   ❌ Market 1013904 not found in cache")
        print("   Available markets (first 5):")
        for i, m in enumerate(explorer.markets[:5]):
            print(f"     {i+1}. ID: {m.get('id')}, Q: {m.get('question', 'N/A')[:60]}")
        return

    print(f"   ✓ Found market: {test_market.get('question', 'N/A')[:70]}")

    # Display market details
    print("\n3. Market Details:")
    print(f"   ID:       {test_market.get('id')}")
    print(f"   Question: {test_market.get('question')}")
    print(f"   Outcomes: {test_market.get('outcome1')} / {test_market.get('outcome2')}")
    print(f"   Volume:   ${float(test_market.get('volume', 0)):,.2f}")
    print(f"   Status:   {'Closed' if test_market.get('closed', '').lower() == 'true' else 'Open'}")

    # Get token info
    print("\n4. Fetching token information...")
    market_id = test_market.get('id')
    tokens = get_market_tokens(market_id)

    if not tokens:
        print("   ❌ Could not fetch token information")
        return

    print(f"   ✓ Token 1 ({tokens['outcome_up']}): {tokens['token_up'][:30]}...")
    print(f"   ✓ Token 2 ({tokens['outcome_down']}): {tokens['token_down'][:30]}...")

    # Fetch price history with different intervals
    print("\n5. Fetching price history (last 1 day, fidelity=60min)...")

    history1 = fetch_price_history(tokens['token_up'], interval='1d', fidelity=60)
    history2 = fetch_price_history(tokens['token_down'], interval='1d', fidelity=60)

    if history1:
        print(f"   ✓ {tokens['outcome_up']}: {len(history1)} data points")
        if history1:
            prices = [p['p'] for p in history1]
            print(f"     Range: ${min(prices):.4f} - ${max(prices):.4f}")
            print(f"     Latest: ${prices[-1]:.4f} at {datetime.fromtimestamp(history1[-1]['t']).isoformat()}")
    else:
        print(f"   ⚠️  {tokens['outcome_up']}: No data")

    if history2:
        print(f"   ✓ {tokens['outcome_down']}: {len(history2)} data points")
        if history2:
            prices = [p['p'] for p in history2]
            print(f"     Range: ${min(prices):.4f} - ${max(prices):.4f}")
            print(f"     Latest: ${prices[-1]:.4f} at {datetime.fromtimestamp(history2[-1]['t']).isoformat()}")
    else:
        print(f"   ⚠️  {tokens['outcome_down']}: No data")

    # Render chart if we have data
    if history1 or history2:
        print("\n6. Rendering price chart...")
        explorer.render_chart(
            history1, history2,
            tokens['outcome_up'], tokens['outcome_down'],
            test_market.get('question', 'Market'),
            '1d'
        )
        print("\n   ✓ Chart rendered successfully!")
    else:
        print("\n6. ⚠️  No price data available to chart")

    print("\n" + "="*80)
    print("DEMO COMPLETE")
    print("="*80)
    print("\nTo use the interactive explorer, run:")
    print("  uv run python market_chart_explorer.py")
    print()


if __name__ == "__main__":
    try:
        demo_chart()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error during demo: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
