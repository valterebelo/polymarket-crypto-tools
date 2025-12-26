#!/usr/bin/env python3
"""
Crypto Market Finder for Polymarket

Finds and displays crypto-related markets with filtering options.
"""
import argparse
from typing import List, Dict
from api_client import PolymarketAPIClient
from config import (
    CRYPTO_KEYWORDS, MARKET_FETCH_BATCH_SIZE,
    MAX_DISPLAY_RESOLVED, MAX_DISPLAY_UNRESOLVED,
    CACHE_FILE, DEFAULT_MAX_MARKETS
)
from any_market_finder import (
    fetch_all_markets,
    separate_by_status,
    format_market_display,
    save_to_csv,
    text_matches_any_keyword,
)


def filter_crypto_markets(markets: List[Dict]) -> List[Dict]:
    """Filter markets for crypto keywords"""
    crypto_markets = []

    for market in markets:
        question = market.get('question', '') or market.get('title', '')
        if text_matches_any_keyword(question, CRYPTO_KEYWORDS):
            crypto_markets.append(market)

    return crypto_markets


def main():
    parser = argparse.ArgumentParser(
        description='Find crypto markets on Polymarket',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--resolved', action='store_true',
                       help='Show only resolved markets')
    parser.add_argument('--unresolved', action='store_true',
                       help='Show only unresolved markets')
    parser.add_argument('--all', action='store_true',
                       help='Show all markets (default)')
    parser.add_argument('--min-volume', type=float, default=0,
                       help='Minimum volume filter (default: 0)')
    parser.add_argument('--output', type=str, default=CACHE_FILE,
                       help=f'Output CSV file (default: {CACHE_FILE})')
    parser.add_argument('--short-term', action='store_true',
                       help='Show only short-term markets (Up or Down, hourly, etc.)')
    parser.add_argument('--start-date', type=str, default=None,
                       help='Only include markets created on or after this date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, default=None,
                       help='Only include markets created before this date (YYYY-MM-DD)')
    parser.add_argument('--max-markets', type=int, default=DEFAULT_MAX_MARKETS,
                       help=f'Maximum number of markets to fetch (default: {DEFAULT_MAX_MARKETS})')
    parser.add_argument('--oldest-first', action='store_true',
                       help='Fetch oldest markets first (default: newest first)')

    args = parser.parse_args()

    # Default to --all if no filter specified
    if not (args.resolved or args.unresolved):
        args.all = True

    print("=" * 65)
    print("CRYPTO MARKET FINDER")
    print("=" * 65)

    # Create API client
    client = PolymarketAPIClient()

    # Fetch markets based on user filter
    all_markets = []
    newest_first = not args.oldest_first

    if args.resolved or args.all:
        print("Fetching CLOSED markets...")
        closed_markets = fetch_all_markets(
            client,
            closed=True,
            max_markets=args.max_markets,
            start_date=args.start_date,
            end_date=args.end_date,
            newest_first=newest_first
        )
        all_markets.extend(closed_markets)

    if args.unresolved or args.all:
        print("Fetching OPEN markets...")
        open_markets = fetch_all_markets(
            client,
            closed=False,
            max_markets=args.max_markets,
            start_date=args.start_date,
            end_date=args.end_date,
            newest_first=newest_first
        )
        all_markets.extend(open_markets)

    print(f"\n✓ Total markets fetched: {len(all_markets)}")

    # Filter for crypto
    print(f"Filtering for crypto keywords...")
    crypto_markets = filter_crypto_markets(all_markets)
    print(f"✓ Found {len(crypto_markets)} crypto markets\n")

    # Apply volume filter
    if args.min_volume > 0:
        crypto_markets = [m for m in crypto_markets if float(m.get('volume', 0)) >= args.min_volume]
        print(f"✓ After volume filter (>=${args.min_volume:,.0f}): {len(crypto_markets)} markets\n")

    # Apply short-term filter (look for Up or Down markets, hourly markets, etc.)
    if args.short_term:
        def is_short_term(market):
            question = market.get('question', '').lower()
            slug = market.get('slug', '').lower()
            # Look for patterns indicating short-term markets
            return ('up or down' in question or 'updown' in slug or
                    '15m' in slug or '1h' in slug or '4h' in slug or
                    '15 min' in question or '1 hour' in question or '4 hour' in question)

        crypto_markets = [m for m in crypto_markets if is_short_term(m)]
        print(f"✓ After short-term filter: {len(crypto_markets)} markets\n")

    # Separate by status
    resolved, unresolved = separate_by_status(crypto_markets)

    # Sort by volume
    resolved.sort(key=lambda m: float(m.get('volume', 0)), reverse=True)
    unresolved.sort(key=lambda m: float(m.get('volume', 0)), reverse=True)

    # Calculate statistics
    total_volume = sum(float(m.get('volume', 0)) for m in crypto_markets)

    # Display summary
    print("=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"Total crypto markets: {len(crypto_markets)}")
    print(f"  Resolved: {len(resolved)} ({len(resolved)/len(crypto_markets)*100:.1f}%)" if crypto_markets else "  Resolved: 0")
    print(f"  Unresolved: {len(unresolved)} ({len(unresolved)/len(crypto_markets)*100:.1f}%)" if crypto_markets else "  Unresolved: 0")
    print(f"Total volume: ${total_volume:,.0f}")
    print()

    # Display resolved markets
    if (args.resolved or args.all) and resolved:
        print("=" * 65)
        print(f"RESOLVED MARKETS (Top {MAX_DISPLAY_RESOLVED} by volume)")
        print("=" * 65)
        for i, market in enumerate(resolved[:MAX_DISPLAY_RESOLVED], 1):
            print(format_market_display(market, i, show_resolution=True))
            print()

    # Display unresolved markets
    if (args.unresolved or args.all) and unresolved:
        print("=" * 65)
        print(f"UNRESOLVED MARKETS (Top {MAX_DISPLAY_UNRESOLVED} by volume)")
        print("=" * 65)
        for i, market in enumerate(unresolved[:MAX_DISPLAY_UNRESOLVED], 1):
            print(format_market_display(market, i, show_resolution=False))
            print()

    # Save to CSV
    print("=" * 65)
    save_to_csv(crypto_markets, args.output)

    # Show usage tip
    print()
    print("💡 To monitor a market live, use the Market ID:")
    print("   python live_monitor.py --market-id <MARKET_ID>")
    print()
    print("   Or copy the token IDs:")
    print("   python live_monitor.py --token-up <TOKEN1> --token-down <TOKEN2>")
    print("=" * 65)


if __name__ == "__main__":
    main()
