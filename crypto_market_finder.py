#!/usr/bin/env python3
"""
Crypto Market Finder for Polymarket

Finds and displays crypto-related markets with filtering options.
"""
import argparse
import csv
from typing import List, Dict
from api_client import PolymarketAPIClient
from config import (
    CRYPTO_KEYWORDS, MARKET_FETCH_BATCH_SIZE,
    MAX_DISPLAY_RESOLVED, MAX_DISPLAY_UNRESOLVED,
    CACHE_FILE, DEFAULT_MAX_MARKETS
)


def is_crypto_market(question: str, keywords: List[str]) -> bool:
    """Check if a market question contains crypto keywords"""
    question_lower = question.lower()
    return any(keyword.lower() in question_lower for keyword in keywords)


def fetch_all_markets(client: PolymarketAPIClient, closed: bool = None,
                     max_markets: int = DEFAULT_MAX_MARKETS,
                     start_date: str = None, end_date: str = None,
                     newest_first: bool = True) -> List[Dict]:
    """
    Fetch markets with pagination and optional date filtering

    Args:
        client: API client
        closed: Filter by closed status (None for all)
        max_markets: Maximum number of markets to fetch
        start_date: Only include markets created on or after this date (YYYY-MM-DD)
        end_date: Only include markets created before this date (YYYY-MM-DD)
        newest_first: Fetch newest markets first (default: True)
    """
    all_markets = []
    offset = 0
    batch_size = MARKET_FETCH_BATCH_SIZE

    print(f"\nFetching markets from Polymarket...")
    if start_date:
        print(f"  Filtering markets created on or after: {start_date}")
    if end_date:
        print(f"  Filtering markets created before: {end_date}")

    # Convert dates to ISO format for comparison if provided
    from datetime import datetime
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    while len(all_markets) < max_markets:
        print(f"  Fetching batch at offset {offset}...")
        markets = client.get_markets(
            limit=batch_size,
            offset=offset,
            closed=closed,
            order="createdAt",
            ascending=not newest_first  # Invert for API (ascending=True means oldest first)
        )

        if not markets:
            break

        # Apply date filtering if specified
        filtered_markets = []
        for market in markets:
            created_at = market.get('createdAt', '')
            if not created_at:
                continue

            market_dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))

            # Check date bounds
            if start_dt and market_dt < start_dt:
                if newest_first:
                    # We've gone past the start date, stop fetching
                    print(f"  Reached markets before {start_date}, stopping...")
                    return all_markets
                else:
                    # Skip this market, continue to next
                    continue

            if end_dt and market_dt >= end_dt:
                if not newest_first:
                    # We've gone past the end date, stop fetching
                    print(f"  Reached markets after {end_date}, stopping...")
                    return all_markets
                else:
                    # Skip this market, continue to next
                    continue

            filtered_markets.append(market)

        all_markets.extend(filtered_markets)
        offset += len(markets)

        # Check if we've reached the end of available markets
        if len(markets) < batch_size:
            break  # Last page

    if len(all_markets) >= max_markets:
        print(f"  Reached maximum market limit ({max_markets})")
        all_markets = all_markets[:max_markets]

    print(f"✓ Fetched {len(all_markets)} total markets\n")
    return all_markets


def filter_crypto_markets(markets: List[Dict]) -> List[Dict]:
    """Filter markets for crypto keywords"""
    crypto_markets = []

    for market in markets:
        question = market.get('question', '') or market.get('title', '')
        if is_crypto_market(question, CRYPTO_KEYWORDS):
            crypto_markets.append(market)

    return crypto_markets


def separate_by_status(markets: List[Dict]) -> tuple:
    """Separate markets into resolved and unresolved"""
    resolved = []
    unresolved = []

    for market in markets:
        # Use 'closed' field if available, otherwise check closedTime
        is_closed = market.get('closed', False)
        if is_closed:
            resolved.append(market)
        else:
            unresolved.append(market)

    return resolved, unresolved


def format_market_display(market: Dict, index: int, show_resolution: bool = False) -> str:
    """Format a market for display"""
    question = market.get('question', '') or market.get('title', '')
    volume = float(market.get('volume', 0))
    market_id = market.get('id', '')

    # Get appropriate time field based on market status
    is_closed = market.get('closed', False)
    closed_time = market.get('closedTime', '')
    end_date = market.get('endDate', '')

    # Get token IDs
    clob_tokens = market.get('clobTokenIds', '[]')
    if isinstance(clob_tokens, str):
        import json
        try:
            clob_tokens = json.loads(clob_tokens)
        except:
            clob_tokens = []

    token1 = clob_tokens[0] if len(clob_tokens) > 0 else 'N/A'
    token2 = clob_tokens[1] if len(clob_tokens) > 1 else 'N/A'

    # Get outcomes
    outcomes = market.get('outcomes', '[]')
    if isinstance(outcomes, str):
        import json
        try:
            outcomes = json.loads(outcomes)
        except:
            outcomes = []

    outcome1 = outcomes[0] if len(outcomes) > 0 else 'YES'
    outcome2 = outcomes[1] if len(outcomes) > 1 else 'NO'

    # Build display string
    lines = []
    resolution = ""
    if show_resolution and closed_time:
        resolution = " (RESOLVED)"

    lines.append(f"[{index}] {question}{resolution}")
    lines.append(f"    Volume: ${volume:,.0f} | Market ID: {market_id[:10]}...")

    if is_closed and closed_time:
        lines.append(f"    Closed: {closed_time[:10]}")
    elif end_date:
        lines.append(f"    Expires: {end_date[:10]} | Status: OPEN")
    else:
        lines.append(f"    Status: OPEN")

    # Show token IDs
    if token1 != 'N/A' and token2 != 'N/A':
        token1_short = token1[:10] + "..." if len(token1) > 10 else token1
        token2_short = token2[:10] + "..." if len(token2) > 10 else token2
        lines.append(f"    Tokens: {outcome1}={token1_short}, {outcome2}={token2_short}")

    return "\n".join(lines)


def save_to_csv(markets: List[Dict], filename: str):
    """Save markets to CSV file"""
    if not markets:
        print(f"No markets to save to {filename}")
        return

    headers = ['id', 'question', 'outcome1', 'outcome2', 'token1', 'token2',
               'volume', 'closed', 'closedTime', 'createdAt']

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for market in markets:
            # Parse tokens
            clob_tokens = market.get('clobTokenIds', '[]')
            if isinstance(clob_tokens, str):
                import json
                try:
                    clob_tokens = json.loads(clob_tokens)
                except:
                    clob_tokens = []

            token1 = clob_tokens[0] if len(clob_tokens) > 0 else ''
            token2 = clob_tokens[1] if len(clob_tokens) > 1 else ''

            # Parse outcomes
            outcomes = market.get('outcomes', '[]')
            if isinstance(outcomes, str):
                import json
                try:
                    outcomes = json.loads(outcomes)
                except:
                    outcomes = []

            outcome1 = outcomes[0] if len(outcomes) > 0 else 'YES'
            outcome2 = outcomes[1] if len(outcomes) > 1 else 'NO'

            writer.writerow({
                'id': market.get('id', ''),
                'question': market.get('question', '') or market.get('title', ''),
                'outcome1': outcome1,
                'outcome2': outcome2,
                'token1': token1,
                'token2': token2,
                'volume': market.get('volume', 0),
                'closed': market.get('closed', False),
                'closedTime': market.get('closedTime', ''),
                'createdAt': market.get('createdAt', '')
            })

    print(f"✓ Saved {len(markets)} markets to {filename}")


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
    print("💡 To monitor a market live, copy the token IDs and run:")
    print("   python live_monitor.py --token-up <TOKEN1> --token-down <TOKEN2>")
    print("=" * 65)


if __name__ == "__main__":
    main()
