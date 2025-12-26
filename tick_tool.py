"""
Command-line tool for Polymarket tick data management.

Commands:
- record: Start recording trades from WebSocket
- query: Query trades from database
- export: Export trades to CSV
- list: List markets in database
- summary: Show market summary statistics
"""

import argparse
import sys
import csv
from datetime import datetime
from pathlib import Path

from tick_database import TickDatabase
from tick_recorder import TickRecorder
from config import TICK_DB_PATH, CACHE_FILE


def cmd_record(args):
    """Start recording trades for specified markets."""
    market_ids = []

    if args.market_ids:
        # From command line
        market_ids = [m.strip() for m in args.market_ids.split(',')]

    elif args.from_cache:
        # Auto-discover from crypto_markets_cache.csv
        print(f"Loading markets from cache: {CACHE_FILE}")

        try:
            with open(CACHE_FILE) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Apply filters
                    if args.filter_unresolved and row.get('closed') == 'True':
                        continue

                    if args.min_volume:
                        volume = float(row.get('volume', 0))
                        if volume < args.min_volume:
                            continue

                    market_ids.append(row['id'])

            print(f"Found {len(market_ids)} markets matching filters")

        except FileNotFoundError:
            print(f"Error: Cache file not found: {CACHE_FILE}")
            print("Run crypto_market_finder.py first to generate cache")
            sys.exit(1)

    elif args.markets_file:
        # From file
        try:
            with open(args.markets_file) as f:
                market_ids = [line.strip() for line in f if line.strip()]
            print(f"Loaded {len(market_ids)} markets from {args.markets_file}")
        except FileNotFoundError:
            print(f"Error: File not found: {args.markets_file}")
            sys.exit(1)

    else:
        print("Error: Must specify --market-ids, --from-cache, or --markets-file")
        sys.exit(1)

    if not market_ids:
        print("Error: No markets to record")
        sys.exit(1)

    # Limit if specified
    if args.limit and args.limit < len(market_ids):
        market_ids = market_ids[:args.limit]
        print(f"Limited to first {args.limit} markets")

    # Start recording
    recorder = TickRecorder(market_ids=market_ids, db_path=args.db_path)
    recorder.start_recording()


def cmd_query(args):
    """Query trades from database."""
    db = TickDatabase(args.db_path)

    if args.market_id:
        # Query by market
        trades = db.get_trades_by_market(
            args.market_id,
            start_time=args.start_time,
            end_time=args.end_time,
            outcome=args.outcome
        )

        print(f"Found {len(trades)} trades for market {args.market_id}")

    elif args.token_id:
        # Query by token
        trades = db.get_trades_by_token(
            args.token_id,
            start_time=args.start_time,
            end_time=args.end_time
        )

        print(f"Found {len(trades)} trades for token {args.token_id[:20]}...")

    else:
        print("Error: Must specify --market-id or --token-id")
        db.close()
        sys.exit(1)

    if not trades:
        print("No trades found")
        db.close()
        return

    # Display trades
    if args.output:
        # Export to CSV
        count = _export_trades_to_csv(trades, args.output)
        print(f"Exported {count} trades to {args.output}")
    else:
        # Display to terminal
        print("\nRecent trades:")
        print("-" * 100)
        print(f"{'Timestamp':<25} {'Side':<6} {'Outcome':<10} {'Price':<10} {'Size':<12} {'Value':<10}")
        print("-" * 100)

        for trade in trades[:50]:  # Limit display to 50
            timestamp = trade.get('timestamp', '')[:19]  # Trim milliseconds
            side = trade.get('side', '')
            outcome = trade.get('outcome', '')
            price = trade.get('price', 0)
            size = trade.get('size', 0)
            value = price * size

            print(f"{timestamp:<25} {side:<6} {outcome:<10} {price:<10.4f} {size:<12.2f} {value:<10.2f}")

        if len(trades) > 50:
            print(f"... and {len(trades) - 50} more trades")

    db.close()


def cmd_export(args):
    """Export trades to CSV."""
    db = TickDatabase(args.db_path)

    if not args.market_id:
        print("Error: --market-id required for export")
        db.close()
        sys.exit(1)

    # Use database's built-in export
    count = db.export_to_csv(args.market_id, args.output)

    if count > 0:
        print(f"✓ Exported {count} trades to {args.output}")
    else:
        print(f"No trades found for market {args.market_id}")

    db.close()


def cmd_list(args):
    """List markets in database."""
    db = TickDatabase(args.db_path)

    markets = db.list_markets(closed=args.closed if args.filter_closed else None)

    if not markets:
        print("No markets found in database")
        db.close()
        return

    print(f"\nFound {len(markets)} markets:\n")
    print("-" * 100)
    print(f"{'Market ID':<10} {'Question':<50} {'Status':<10} {'Last Updated':<25}")
    print("-" * 100)

    for market in markets:
        market_id = market.get('market_id', '')
        question = market.get('question', '')[:47] + "..." if len(market.get('question', '')) > 50 else market.get('question', '')
        status = "Closed" if market.get('closed') else "Open"
        last_updated = market.get('last_updated', '')[:19]

        print(f"{market_id:<10} {question:<50} {status:<10} {last_updated:<25}")

    db.close()


def cmd_summary(args):
    """Show summary statistics for a market."""
    if not args.market_id:
        print("Error: --market-id required for summary")
        sys.exit(1)

    db = TickDatabase(args.db_path)

    # Get market metadata
    market = db.get_market(args.market_id)

    if not market:
        print(f"Market {args.market_id} not found in database")
        db.close()
        sys.exit(1)

    # Get trade summary
    summary = db.get_market_summary(args.market_id)

    # Display
    print("\n" + "="*70)
    print("MARKET SUMMARY")
    print("="*70)
    print(f"Market ID: {market['market_id']}")
    print(f"Question:  {market['question']}")
    print(f"Outcomes:  {market['outcome_up']} / {market['outcome_down']}")
    print(f"Status:    {'Closed' if market['closed'] else 'Open'}")

    if market['created_at']:
        print(f"Created:   {market['created_at']}")
    if market['closed_time']:
        print(f"Closed:    {market['closed_time']}")

    print("\n" + "-"*70)
    print("TRADE DATA")
    print("-"*70)
    print(f"Total trades:  {summary['total_trades']}")
    print(f"Total volume:  {summary['total_volume']:.2f}" if summary['total_volume'] else "Total volume:  0")

    if summary['oldest_trade']:
        print(f"Oldest trade:  {summary['oldest_trade']}")
    if summary['newest_trade']:
        print(f"Newest trade:  {summary['newest_trade']}")

    if summary.get('sources'):
        print("\nSources:")
        for source, count in summary['sources'].items():
            print(f"  {source}: {count} trades")

    print("="*70 + "\n")

    db.close()


def _export_trades_to_csv(trades, output_path):
    """Helper to export trades to CSV."""
    with open(output_path, 'w', newline='') as f:
        fieldnames = [
            'timestamp', 'market_id', 'asset_id', 'side', 'outcome',
            'price', 'size', 'value', 'fee_rate_bps', 'source'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
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


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Polymarket Tick Data Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--db-path', default=TICK_DB_PATH,
                       help=f'Database path (default: {TICK_DB_PATH})')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Record command
    record_parser = subparsers.add_parser('record', help='Start recording trades')
    record_parser.add_argument('--market-ids', help='Comma-separated market IDs')
    record_parser.add_argument('--from-cache', action='store_true',
                              help='Auto-discover from crypto_markets_cache.csv')
    record_parser.add_argument('--markets-file', help='Read market IDs from file')
    record_parser.add_argument('--filter-unresolved', action='store_true',
                              help='Only unresolved markets (with --from-cache)')
    record_parser.add_argument('--min-volume', type=float,
                              help='Minimum volume filter (with --from-cache)')
    record_parser.add_argument('--limit', type=int,
                              help='Limit number of markets to record')

    # Query command
    query_parser = subparsers.add_parser('query', help='Query trades from database')
    query_parser.add_argument('--market-id', help='Market ID to query')
    query_parser.add_argument('--token-id', help='Token ID to query')
    query_parser.add_argument('--start-time', help='Start time (ISO 8601)')
    query_parser.add_argument('--end-time', help='End time (ISO 8601)')
    query_parser.add_argument('--outcome', help='Filter by outcome (UP/DOWN)')
    query_parser.add_argument('--output', help='Export to CSV file')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export trades to CSV')
    export_parser.add_argument('--market-id', required=True, help='Market ID')
    export_parser.add_argument('--output', required=True, help='Output CSV file')

    # List command
    list_parser = subparsers.add_parser('list', help='List markets in database')
    list_parser.add_argument('--filter-closed', action='store_true',
                            help='Filter by closed status')
    list_parser.add_argument('--closed', type=lambda x: x.lower() == 'true',
                            help='Show only closed (true) or open (false) markets')

    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show market summary')
    summary_parser.add_argument('--market-id', required=True, help='Market ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch to command handler
    if args.command == 'record':
        cmd_record(args)
    elif args.command == 'query':
        cmd_query(args)
    elif args.command == 'export':
        cmd_export(args)
    elif args.command == 'list':
        cmd_list(args)
    elif args.command == 'summary':
        cmd_summary(args)


if __name__ == "__main__":
    main()
