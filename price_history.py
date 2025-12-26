"""
Fetch historical price data from Polymarket CLOB API.

Uses the /prices-history endpoint to get token price timeseries.

This is the SIMPLE way to get historical prices - no authentication needed!

Usage:
    # Get price history for a token
    python price_history.py --token-id <TOKEN_ID> --interval 1h

    # Get price history for a market
    python price_history.py --market-id <MARKET_ID> --interval 1d

    # Specific time range
    python price_history.py --token-id <TOKEN_ID> --start 2025-12-20 --end 2025-12-25

    # Export to CSV
    python price_history.py --market-id <MARKET_ID> --interval 1h --output prices.csv
"""

import argparse
import sys
import csv
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional
import requests

from api_client import PolymarketAPIClient
from config import CLOB_API_BASE


def fetch_price_history(
    token_id: str,
    start_ts: Optional[int] = None,
    end_ts: Optional[int] = None,
    interval: Optional[str] = None,
    fidelity: Optional[int] = None
) -> List[Dict]:
    """
    Fetch historical price data for a token.

    Args:
        token_id: CLOB token ID
        start_ts: Start Unix timestamp (seconds)
        end_ts: End Unix timestamp (seconds)
        interval: Duration string (1m, 1h, 6h, 1d, 1w, max) - mutually exclusive with start/end
        fidelity: Resolution in minutes

    Returns:
        List of price points: [{"t": timestamp, "p": price}, ...]
    """
    url = f"{CLOB_API_BASE}/prices-history"

    params = {"market": token_id}

    # Add time parameters (interval OR start/end, not both)
    if interval:
        params["interval"] = interval
    else:
        if start_ts:
            params["startTs"] = start_ts
        if end_ts:
            params["endTs"] = end_ts

    if fidelity:
        params["fidelity"] = fidelity

    print(f"Fetching price history from: {url}")
    print(f"Parameters: {params}")

    try:
        response = requests.get(url, params=params, timeout=30)

        if response.status_code == 200:
            data = response.json()
            history = data.get("history", [])
            return history
        else:
            print(f"Error {response.status_code}: {response.text}")
            return []

    except Exception as e:
        print(f"Request failed: {e}")
        return []


def get_market_tokens(market_id: str) -> Optional[Dict]:
    """Get token IDs for a market."""
    client = PolymarketAPIClient()
    market = client.get_market_by_id(market_id)

    if not market:
        return None

    # Parse tokens and outcomes
    import json as json_lib

    clob_tokens = market.get('clobTokenIds', [])
    if isinstance(clob_tokens, str):
        clob_tokens = json_lib.loads(clob_tokens)

    outcomes = market.get('outcomes', [])
    if isinstance(outcomes, str):
        outcomes = json_lib.loads(outcomes)

    if len(clob_tokens) != 2 or len(outcomes) != 2:
        return None

    return {
        'market_id': market_id,
        'question': market.get('question', ''),
        'token_up': clob_tokens[0],
        'token_down': clob_tokens[1],
        'outcome_up': outcomes[0],
        'outcome_down': outcomes[1]
    }


def parse_date(date_str: str) -> int:
    """Convert date string to Unix timestamp."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return int(dt.timestamp())
    except:
        # Try parsing as just date
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())


def format_timestamp(ts: int) -> str:
    """Convert Unix timestamp to ISO datetime."""
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    return dt.isoformat()


def cmd_fetch(args):
    """Fetch and display price history."""

    # Get token ID(s)
    if args.market_id:
        market_info = get_market_tokens(args.market_id)

        if not market_info:
            print(f"Error: Market {args.market_id} not found or invalid")
            sys.exit(1)

        print("="*70)
        print("MARKET INFORMATION")
        print("="*70)
        print(f"Question: {market_info['question']}")
        print(f"Outcomes: {market_info['outcome_up']} / {market_info['outcome_down']}")
        print()

        tokens = [
            (market_info['token_up'], market_info['outcome_up']),
            (market_info['token_down'], market_info['outcome_down'])
        ]

    elif args.token_id:
        tokens = [(args.token_id, "Token")]

    else:
        print("Error: Must specify --market-id or --token-id")
        sys.exit(1)

    # Parse time range
    start_ts = None
    end_ts = None

    if args.start:
        start_ts = parse_date(args.start)
        print(f"Start: {format_timestamp(start_ts)}")

    if args.end:
        end_ts = parse_date(args.end)
        print(f"End: {format_timestamp(end_ts)}")

    if args.interval:
        print(f"Interval: {args.interval}")

    if args.fidelity:
        print(f"Fidelity: {args.fidelity} minutes")

    print("="*70)
    print()

    # Fetch history for each token
    all_data = []

    for token_id, outcome in tokens:
        print(f"Fetching {outcome} price history...")

        history = fetch_price_history(
            token_id,
            start_ts=start_ts,
            end_ts=end_ts,
            interval=args.interval,
            fidelity=args.fidelity
        )

        if not history:
            print(f"  No data returned for {outcome}")
            continue

        print(f"  ✓ Got {len(history)} price points")

        # Add to combined data
        for point in history:
            all_data.append({
                'timestamp': point['t'],
                'datetime': format_timestamp(point['t']),
                'outcome': outcome,
                'price': point['p'],
                'token_id': token_id
            })

        # Show sample
        if history:
            print(f"  Sample (first 5):")
            for point in history[:5]:
                dt = format_timestamp(point['t'])
                print(f"    {dt}: {point['p']:.4f}")

        print()

    if not all_data:
        print("No price data retrieved.")
        return

    # Summary
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total data points: {len(all_data)}")

    timestamps = [d['timestamp'] for d in all_data]
    if timestamps:
        print(f"Time range: {format_timestamp(min(timestamps))} to {format_timestamp(max(timestamps))}")
        time_span = max(timestamps) - min(timestamps)
        print(f"Duration: {time_span / 3600:.1f} hours ({time_span / 86400:.1f} days)")

    prices = [d['price'] for d in all_data]
    if prices:
        print(f"Price range: {min(prices):.4f} - {max(prices):.4f}")

    print("="*70)

    # Export if requested
    if args.output:
        export_to_csv(all_data, args.output, args.market_id)
        print(f"\n✓ Exported to {args.output}")

    # Export JSON if requested
    if args.json:
        with open(args.json, 'w') as f:
            json.dump(all_data, f, indent=2)
        print(f"✓ Exported to {args.json}")


def export_to_csv(data: List[Dict], output_path: str, market_id: str = None):
    """Export price history to CSV."""
    with open(output_path, 'w', newline='') as f:
        fieldnames = ['datetime', 'timestamp', 'outcome', 'price', 'token_id']
        if market_id:
            fieldnames.insert(0, 'market_id')

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in sorted(data, key=lambda x: x['timestamp']):
            out_row = {
                'datetime': row['datetime'],
                'timestamp': row['timestamp'],
                'outcome': row['outcome'],
                'price': row['price'],
                'token_id': row['token_id']
            }
            if market_id:
                out_row['market_id'] = market_id

            writer.writerow(out_row)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch historical price data from Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Get last 1 hour of prices
  python price_history.py --token-id 123456... --interval 1h

  # Get last day at hourly resolution
  python price_history.py --market-id 996577 --interval 1d --fidelity 60

  # Specific date range
  python price_history.py --market-id 996577 --start 2025-12-20 --end 2025-12-25

  # Export to CSV
  python price_history.py --market-id 996577 --interval 1w --output prices.csv

Interval options: 1m, 1h, 6h, 1d, 1w, max
        """
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument('--market-id', help='Market ID (fetches both tokens)')
    input_group.add_argument('--token-id', help='Single token ID')

    # Time range options
    time_group = parser.add_mutually_exclusive_group()
    time_group.add_argument('--interval',
                           choices=['1m', '1h', '6h', '1d', '1w', 'max'],
                           help='Time interval (mutually exclusive with --start/--end)')

    parser.add_argument('--start', help='Start date/time (YYYY-MM-DD or ISO format)')
    parser.add_argument('--end', help='End date/time (YYYY-MM-DD or ISO format)')

    # Resolution
    parser.add_argument('--fidelity', type=int, help='Resolution in minutes')

    # Output
    parser.add_argument('--output', help='Export to CSV file')
    parser.add_argument('--json', help='Export to JSON file')

    args = parser.parse_args()

    # Validate: interval OR start/end, not both
    if args.interval and (args.start or args.end):
        parser.error("Cannot use --interval with --start/--end")

    cmd_fetch(args)


if __name__ == "__main__":
    main()
