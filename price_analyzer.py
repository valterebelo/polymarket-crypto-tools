#!/usr/bin/env python3
"""
Professional price data analysis and visualization for Polymarket markets.

Focused on data analysis, not terminal gimmicks.
"""

import argparse
import sys
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from typing import List, Dict, Optional
import csv

from price_history import fetch_price_history, get_market_tokens
from config import CACHE_FILE


def load_markets_cache() -> pd.DataFrame:
    """Load markets from cache into DataFrame."""
    return pd.read_csv(CACHE_FILE)


def fetch_market_price_data(market_id: str, interval: str = '1d', fidelity: int = None) -> Optional[pd.DataFrame]:
    """
    Fetch price data for a market and return as clean DataFrame.

    Returns DataFrame with columns: datetime, outcome, price
    """
    tokens = get_market_tokens(market_id)
    if not tokens:
        print(f"Error: Could not fetch token info for market {market_id}")
        return None

    # Fetch both outcomes
    history1 = fetch_price_history(tokens['token_up'], interval=interval, fidelity=fidelity)
    history2 = fetch_price_history(tokens['token_down'], interval=interval, fidelity=fidelity)

    if not history1 and not history2:
        print(f"Warning: No price data for market {market_id}")
        return None

    # Build DataFrame
    rows = []

    if history1:
        for point in history1:
            rows.append({
                'datetime': datetime.fromtimestamp(point['t']),
                'outcome': tokens['outcome_up'],
                'price': point['p']
            })

    if history2:
        for point in history2:
            rows.append({
                'datetime': datetime.fromtimestamp(point['t']),
                'outcome': tokens['outcome_down'],
                'price': point['p']
            })

    df = pd.DataFrame(rows)
    df['market_id'] = market_id
    df['question'] = tokens['question']

    return df


def plot_single_market(df: pd.DataFrame, market_id: str, output_file: str = None):
    """Create professional chart for a single market."""

    question = df['question'].iloc[0]

    fig, ax = plt.subplots(figsize=(14, 7))

    # Plot each outcome
    for outcome in df['outcome'].unique():
        data = df[df['outcome'] == outcome].sort_values('datetime')
        ax.plot(data['datetime'], data['price'],
                label=outcome, linewidth=2, marker='o', markersize=4)

    # Formatting
    ax.set_xlabel('Time', fontsize=12)
    ax.set_ylabel('Price (USD)', fontsize=12)
    ax.set_title(f'{question}\nMarket ID: {market_id}', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)

    # Date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Chart saved to: {output_file}")
    else:
        plt.show()

    plt.close()


def plot_multiple_markets(dataframes: List[pd.DataFrame], output_file: str = None):
    """Compare multiple markets on separate subplots."""

    n_markets = len(dataframes)
    fig, axes = plt.subplots(n_markets, 1, figsize=(14, 5 * n_markets))

    if n_markets == 1:
        axes = [axes]

    for idx, df in enumerate(dataframes):
        ax = axes[idx]
        question = df['question'].iloc[0]
        market_id = df['market_id'].iloc[0]

        for outcome in df['outcome'].unique():
            data = df[df['outcome'] == outcome].sort_values('datetime')
            ax.plot(data['datetime'], data['price'],
                   label=outcome, linewidth=2, marker='o', markersize=3)

        ax.set_ylabel('Price (USD)', fontsize=11)
        ax.set_title(f'{question}\n(ID: {market_id})', fontsize=12, fontweight='bold')
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    axes[-1].set_xlabel('Time', fontsize=12)

    plt.tight_layout()

    if output_file:
        plt.savefig(output_file, dpi=150, bbox_inches='tight')
        print(f"Comparison chart saved to: {output_file}")
    else:
        plt.show()

    plt.close()


def analyze_market(df: pd.DataFrame) -> Dict:
    """Generate summary statistics for a market."""

    stats = {
        'market_id': df['market_id'].iloc[0],
        'question': df['question'].iloc[0],
        'data_points': len(df),
        'time_range': {
            'start': df['datetime'].min(),
            'end': df['datetime'].max(),
            'duration_hours': (df['datetime'].max() - df['datetime'].min()).total_seconds() / 3600
        },
        'outcomes': {}
    }

    for outcome in df['outcome'].unique():
        data = df[df['outcome'] == outcome]['price']
        stats['outcomes'][outcome] = {
            'count': len(data),
            'min': data.min(),
            'max': data.max(),
            'mean': data.mean(),
            'std': data.std(),
            'final': data.iloc[-1] if len(data) > 0 else None,
            'change_pct': ((data.iloc[-1] - data.iloc[0]) / data.iloc[0] * 100) if len(data) > 0 and data.iloc[0] != 0 else 0
        }

    return stats


def print_analysis(stats: Dict):
    """Print analysis results."""
    print("\n" + "="*80)
    print(f"MARKET ANALYSIS")
    print("="*80)
    print(f"Question: {stats['question']}")
    print(f"Market ID: {stats['market_id']}")
    print(f"\nTime Range:")
    print(f"  Start: {stats['time_range']['start']}")
    print(f"  End: {stats['time_range']['end']}")
    print(f"  Duration: {stats['time_range']['duration_hours']:.1f} hours")
    print(f"  Total data points: {stats['data_points']}")

    for outcome, data in stats['outcomes'].items():
        print(f"\n{outcome}:")
        print(f"  Data points: {data['count']}")
        print(f"  Range: ${data['min']:.4f} - ${data['max']:.4f}")
        print(f"  Mean: ${data['mean']:.4f} ± ${data['std']:.4f}")
        print(f"  Final: ${data['final']:.4f}")
        print(f"  Change: {data['change_pct']:+.2f}%")

    print("="*80)


def export_analysis(stats: Dict, output_file: str):
    """Export analysis to CSV."""
    rows = []
    for outcome, data in stats['outcomes'].items():
        rows.append({
            'market_id': stats['market_id'],
            'question': stats['question'],
            'outcome': outcome,
            'data_points': data['count'],
            'price_min': data['min'],
            'price_max': data['max'],
            'price_mean': data['mean'],
            'price_std': data['std'],
            'price_final': data['final'],
            'change_pct': data['change_pct'],
            'time_start': stats['time_range']['start'],
            'time_end': stats['time_range']['end'],
            'duration_hours': stats['time_range']['duration_hours']
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)
    print(f"Analysis exported to: {output_file}")


def cmd_chart(args):
    """Chart a single market."""
    print(f"Fetching price data for market {args.market_id}...")

    df = fetch_market_price_data(args.market_id, interval=args.interval, fidelity=args.fidelity)

    if df is None or len(df) == 0:
        print("No data to chart.")
        sys.exit(1)

    # Analysis
    if args.stats or args.export:
        stats = analyze_market(df)
        print_analysis(stats)

        if args.export:
            export_analysis(stats, args.export)

    # Chart
    if not args.no_chart:
        plot_single_market(df, args.market_id, output_file=args.output)


def cmd_compare(args):
    """Compare multiple markets."""
    market_ids = args.market_ids.split(',')

    print(f"Fetching price data for {len(market_ids)} markets...")

    dataframes = []
    for market_id in market_ids:
        df = fetch_market_price_data(market_id.strip(), interval=args.interval, fidelity=args.fidelity)
        if df is not None and len(df) > 0:
            dataframes.append(df)
        else:
            print(f"Warning: No data for market {market_id}")

    if not dataframes:
        print("No data to chart.")
        sys.exit(1)

    print(f"Plotting {len(dataframes)} markets...")
    plot_multiple_markets(dataframes, output_file=args.output)


def cmd_search(args):
    """Search markets and show top results."""
    markets_df = load_markets_cache()

    # Filter by keyword
    if args.keyword:
        mask = markets_df['question'].str.contains(args.keyword, case=False, na=False)
        markets_df = markets_df[mask]

    # Filter by status
    if args.status == 'open':
        markets_df = markets_df[markets_df['closed'].str.lower() == 'false']
    elif args.status == 'closed':
        markets_df = markets_df[markets_df['closed'].str.lower() == 'true']

    # Sort by volume
    markets_df['volume_float'] = pd.to_numeric(markets_df['volume'], errors='coerce')
    markets_df = markets_df.sort_values('volume_float', ascending=False)

    # Limit results
    results = markets_df.head(args.limit)

    print(f"\nFound {len(markets_df)} markets, showing top {len(results)}:\n")

    for idx, row in results.iterrows():
        print(f"{idx+1}. [{row['id']}] {row['question']}")
        print(f"   Volume: ${float(row['volume']):,.2f} | Status: {'Closed' if row['closed'].lower() == 'true' else 'Open'}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Professional price analysis and visualization for Polymarket",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Chart command
    chart_parser = subparsers.add_parser('chart', help='Chart a single market')
    chart_parser.add_argument('market_id', help='Market ID')
    chart_parser.add_argument('--interval', default='1d', choices=['1h', '6h', '1d', '1w', 'max'])
    chart_parser.add_argument('--fidelity', type=int, help='Resolution in minutes')
    chart_parser.add_argument('--output', help='Save chart to file (e.g., chart.png)')
    chart_parser.add_argument('--stats', action='store_true', help='Show statistics')
    chart_parser.add_argument('--export', help='Export analysis to CSV')
    chart_parser.add_argument('--no-chart', action='store_true', help='Skip chart display')

    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare multiple markets')
    compare_parser.add_argument('market_ids', help='Comma-separated market IDs')
    compare_parser.add_argument('--interval', default='1d', choices=['1h', '6h', '1d', '1w', 'max'])
    compare_parser.add_argument('--fidelity', type=int, help='Resolution in minutes')
    compare_parser.add_argument('--output', help='Save chart to file (e.g., comparison.png)')

    # Search command
    search_parser = subparsers.add_parser('search', help='Search markets')
    search_parser.add_argument('keyword', nargs='?', help='Search keyword')
    search_parser.add_argument('--status', choices=['all', 'open', 'closed'], default='all')
    search_parser.add_argument('--limit', type=int, default=20, help='Number of results')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == 'chart':
        cmd_chart(args)
    elif args.command == 'compare':
        cmd_compare(args)
    elif args.command == 'search':
        cmd_search(args)


if __name__ == '__main__':
    main()
