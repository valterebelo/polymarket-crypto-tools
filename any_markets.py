#!/usr/bin/env python3
"""
Any Market Finder for Polymarket

Alternative to `crypto_market_finder.py`:
- Same fetching/display/caching flow
- Prompts at runtime for keywords to filter markets
- Defaults to caching into `data/any_markets_cache.csv`
"""

import argparse
from typing import List, Dict

from api_client import PolymarketAPIClient
from config import (
    MAX_DISPLAY_RESOLVED,
    MAX_DISPLAY_UNRESOLVED,
    DATA_DIR,
    DEFAULT_MAX_MARKETS,
)
from any_market_finder import (
    fetch_all_markets,
    separate_by_status,
    format_market_display,
    save_to_csv,
    market_matches_any_keywords,
)


DEFAULT_ANY_CACHE_FILE = f"{DATA_DIR}/any_markets_cache.csv"


def _prompt_keywords() -> List[str]:
    ans = input("Do you want to add words to filter markets? [y/N]: ").strip().lower()
    if ans not in {"y", "yes"}:
        return []

    raw = input("Enter words (comma-separated). Example: bitcoin, etf, election\n> ").strip()
    if not raw:
        return []

    parts = [p.strip() for p in raw.split(",")]
    keywords = [p for p in parts if p]
    return keywords


def main():
    parser = argparse.ArgumentParser(
        description="Find markets on Polymarket, optionally filtered by interactive keywords",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--resolved", action="store_true", help="Show only resolved markets")
    parser.add_argument("--unresolved", action="store_true", help="Show only unresolved markets")
    parser.add_argument("--all", action="store_true", help="Show all markets (default)")
    parser.add_argument("--min-volume", type=float, default=0, help="Minimum volume filter (default: 0)")
    parser.add_argument("--output", type=str, default=DEFAULT_ANY_CACHE_FILE, help=f"Output CSV file (default: {DEFAULT_ANY_CACHE_FILE})")
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Only include markets created on or after this date (YYYY-MM-DD)",
    )
    parser.add_argument("--end-date", type=str, default=None, help="Only include markets created before this date (YYYY-MM-DD)")
    parser.add_argument(
        "--max-markets",
        type=int,
        default=DEFAULT_MAX_MARKETS,
        help=f"Maximum number of markets to fetch (default: {DEFAULT_MAX_MARKETS})",
    )
    parser.add_argument("--oldest-first", action="store_true", help="Fetch oldest markets first (default: newest first)")

    args = parser.parse_args()

    # Default to --all if no filter specified
    if not (args.resolved or args.unresolved):
        args.all = True

    print("=" * 65)
    print("ANY MARKET FINDER")
    print("=" * 65)

    keywords = _prompt_keywords()
    if keywords:
        print(f"\nKeyword filter enabled ({len(keywords)}): {', '.join(keywords)}\n")
    else:
        print("\nNo keyword filter enabled (will include all markets in date range).\n")

    client = PolymarketAPIClient()

    all_markets: List[Dict] = []
    newest_first = not args.oldest_first

    if args.resolved or args.all:
        print("Fetching CLOSED markets...")
        closed_markets = fetch_all_markets(
            client,
            closed=True,
            max_markets=args.max_markets,
            start_date=args.start_date,
            end_date=args.end_date,
            newest_first=newest_first,
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
            newest_first=newest_first,
        )
        all_markets.extend(open_markets)

    print(f"\n✓ Total markets fetched: {len(all_markets)}")

    # Keyword filter
    if keywords:
        print("Filtering by keywords...")
        filtered_markets = [m for m in all_markets if market_matches_any_keywords(m, keywords)]
        print(f"✓ After keyword filter: {len(filtered_markets)} markets\n")
    else:
        filtered_markets = all_markets

    # Volume filter
    if args.min_volume > 0:
        filtered_markets = [m for m in filtered_markets if float(m.get("volume", 0) or 0) >= args.min_volume]
        print(f"✓ After volume filter (>=${args.min_volume:,.0f}): {len(filtered_markets)} markets\n")

    resolved, unresolved = separate_by_status(filtered_markets)
    resolved.sort(key=lambda m: float(m.get("volume", 0) or 0), reverse=True)
    unresolved.sort(key=lambda m: float(m.get("volume", 0) or 0), reverse=True)

    total_volume = sum(float(m.get("volume", 0) or 0) for m in filtered_markets)

    print("=" * 65)
    print("SUMMARY")
    print("=" * 65)
    print(f"Total markets: {len(filtered_markets)}")
    print(f"  Resolved: {len(resolved)} ({len(resolved)/len(filtered_markets)*100:.1f}%)" if filtered_markets else "  Resolved: 0")
    print(f"  Unresolved: {len(unresolved)} ({len(unresolved)/len(filtered_markets)*100:.1f}%)" if filtered_markets else "  Unresolved: 0")
    print(f"Total volume: ${total_volume:,.0f}")
    print()

    if (args.resolved or args.all) and resolved:
        print("=" * 65)
        print(f"RESOLVED MARKETS (Top {MAX_DISPLAY_RESOLVED} by volume)")
        print("=" * 65)
        for i, market in enumerate(resolved[:MAX_DISPLAY_RESOLVED], 1):
            print(format_market_display(market, i, show_resolution=True))
            print()

    if (args.unresolved or args.all) and unresolved:
        print("=" * 65)
        print(f"UNRESOLVED MARKETS (Top {MAX_DISPLAY_UNRESOLVED} by volume)")
        print("=" * 65)
        for i, market in enumerate(unresolved[:MAX_DISPLAY_UNRESOLVED], 1):
            print(format_market_display(market, i, show_resolution=False))
            print()

    print("=" * 65)
    save_to_csv(filtered_markets, args.output)
    print("=" * 65)


if __name__ == "__main__":
    main()


