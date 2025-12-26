"""
Interactive market explorer with price charting.

Browse markets and visualize historical price data in the terminal.

Usage:
    python market_chart_explorer.py
"""

import sys
import csv
from datetime import datetime
from typing import List, Dict, Optional

# Chart rendering
import plotext as plt

from api_client import PolymarketAPIClient
from price_history import fetch_price_history, get_market_tokens
from config import CACHE_FILE


class MarketExplorer:
    """Interactive market browser with charting."""

    def __init__(self):
        self.client = PolymarketAPIClient()
        self.markets = []
        self.selected_market = None

    def load_markets_from_cache(self) -> bool:
        """Load markets from CSV cache."""
        try:
            with open(CACHE_FILE) as f:
                reader = csv.DictReader(f)
                self.markets = list(reader)
            return len(self.markets) > 0
        except FileNotFoundError:
            return False

    def filter_markets(self, keyword: str = None, status: str = 'all', limit: int = None) -> List[Dict]:
        """Filter markets by criteria."""
        filtered = []

        for market in self.markets:
            # Status filter
            is_closed = market.get('closed', '').lower() == 'true'
            if status == 'open' and is_closed:
                continue
            if status == 'closed' and not is_closed:
                continue

            # Keyword filter
            if keyword:
                question = market.get('question', '').lower()
                if keyword.lower() not in question:
                    continue

            filtered.append(market)

            if limit and len(filtered) >= limit:
                break

        return filtered

    def display_markets(self, markets: List[Dict], page: int = 0, page_size: int = 50):
        """Display market list in a table with pagination."""
        if not markets:
            print("\n❌ No markets found.")
            return []

        total_pages = (len(markets) - 1) // page_size + 1
        start_idx = page * page_size
        end_idx = min(start_idx + page_size, len(markets))
        page_markets = markets[start_idx:end_idx]

        print("\n" + "="*100)
        print(f"Showing {start_idx + 1}-{end_idx} of {len(markets)} markets (Page {page + 1}/{total_pages})")
        print("="*100)
        print(f"{'#':<4} {'ID':<10} {'Question':<50} {'Volume':<12} {'Status':<8}")
        print("-"*100)

        for i, market in enumerate(page_markets, 1):
            market_id = market.get('id', 'N/A')
            question = market.get('question', 'N/A')
            if len(question) > 47:
                question = question[:47] + "..."

            volume = market.get('volume', '0')
            try:
                vol_float = float(volume)
                if vol_float >= 1000000:
                    vol_str = f"${vol_float/1000000:.1f}M"
                elif vol_float >= 1000:
                    vol_str = f"${vol_float/1000:.1f}K"
                else:
                    vol_str = f"${vol_float:.0f}"
            except:
                vol_str = "$0"

            status = "Closed" if market.get('closed', '').lower() == 'true' else "Open"

            print(f"{i:<4} {market_id:<10} {question:<50} {vol_str:<12} {status:<8}")

        print("="*100)
        if total_pages > 1:
            print(f"Navigation: [N]ext page | [P]revious page | [S]elect market | [B]ack")

        return page_markets

    def select_market(self, markets: List[Dict]) -> Optional[Dict]:
        """Prompt user to select a market."""
        while True:
            try:
                choice = input(f"\nSelect market (1-{len(markets)}, or 0 to go back): ").strip()

                if choice == '0':
                    return None

                index = int(choice) - 1
                if 0 <= index < len(markets):
                    return markets[index]
                else:
                    print(f"❌ Invalid choice. Enter a number between 1 and {len(markets)}")
            except ValueError:
                print("❌ Invalid input. Enter a number.")
            except KeyboardInterrupt:
                return None

    def display_market_details(self, market: Dict):
        """Display detailed market information."""
        print("\n" + "="*80)
        print("MARKET DETAILS")
        print("="*80)
        print(f"ID:       {market.get('id', 'N/A')}")
        print(f"Question: {market.get('question', 'N/A')}")
        print(f"Outcomes: {market.get('outcome1', 'N/A')} / {market.get('outcome2', 'N/A')}")
        print(f"Volume:   ${float(market.get('volume', 0)):,.2f}")
        print(f"Status:   {'Closed' if market.get('closed', '').lower() == 'true' else 'Open'}")
        print(f"Created:  {market.get('createdAt', 'N/A')}")

        if market.get('closedTime'):
            print(f"Closed:   {market.get('closedTime')}")

        print(f"\nToken 1 ({market.get('outcome1', 'N/A')}): {market.get('token1', 'N/A')[:30]}...")
        print(f"Token 2 ({market.get('outcome2', 'N/A')}): {market.get('token2', 'N/A')[:30]}...")
        print("="*80)

    def chart_price_history(self, market: Dict):
        """Fetch and chart price history for a market."""
        market_id = market.get('id')
        question = market.get('question', 'Market')

        print(f"\n📊 Fetching price history for market {market_id}...")

        # Get token info
        tokens = get_market_tokens(market_id)
        if not tokens:
            print("❌ Could not fetch market token information")
            return

        # Let user choose time range
        print("\nSelect time range:")
        print("  1) Last hour (1h)")
        print("  2) Last 6 hours (6h)")
        print("  3) Last day (1d)")
        print("  4) Last week (1w)")
        print("  5) All available data (max)")

        while True:
            try:
                choice = input("\nChoice (1-5): ").strip()
                intervals = {'1': '1h', '2': '6h', '3': '1d', '4': '1w', '5': 'max'}
                if choice in intervals:
                    interval = intervals[choice]
                    break
                print("❌ Invalid choice")
            except KeyboardInterrupt:
                return

        # Fetch data for both tokens
        print(f"\nFetching data (interval: {interval})...")

        outcome1 = tokens.get('outcome_up', 'Outcome 1')
        outcome2 = tokens.get('outcome_down', 'Outcome 2')

        history1 = fetch_price_history(tokens['token_up'], interval=interval, fidelity=1)
        history2 = fetch_price_history(tokens['token_down'], interval=interval, fidelity=1)

        if not history1 and not history2:
            print("\n❌ No price data available for this market")
            print("   This could mean:")
            print("   - Market is very new (no data accumulated)")
            print("   - Market is very old (data purged)")
            print("   - Low trading activity")
            return

        # Render chart
        self.render_chart(history1, history2, outcome1, outcome2, question, interval)

    def render_chart(self, history1: List[Dict], history2: List[Dict],
                    outcome1: str, outcome2: str, title: str, interval: str):
        """Render terminal chart using plotext with improved visualization."""
        plt.clear_figure()

        # Set larger terminal size for better detail
        try:
            import shutil
            width, height = shutil.get_terminal_size()
            # Use more of the terminal space
            plt.plot_size(width - 5, max(height - 10, 30))
        except:
            plt.plot_size(120, 35)

        has_data = False

        # Plot outcome 1 - Use solid line with markers
        if history1:
            # Convert timestamps to datetime strings for plotext
            times1 = [datetime.fromtimestamp(p['t']).strftime('%Y-%m-%d %H:%M:%S') for p in history1]
            prices1 = [p['p'] for p in history1]

            plt.date_form('Y-m-d H:M:S')
            # Use solid line with small markers for better visibility
            plt.plot(times1, prices1, label=outcome1, color='bright-green', marker='small')
            has_data = True

            print(f"\n{outcome1}: {len(history1)} data points")
            if prices1:
                print(f"  Range: ${min(prices1):.4f} - ${max(prices1):.4f}")
                print(f"  Last: ${prices1[-1]:.4f}")
                change = ((prices1[-1] - prices1[0]) / prices1[0] * 100) if prices1[0] != 0 else 0
                print(f"  Change: {change:+.2f}%")

        # Plot outcome 2 - Use dashed line with different markers
        if history2:
            times2 = [datetime.fromtimestamp(p['t']).strftime('%Y-%m-%d %H:%M:%S') for p in history2]
            prices2 = [p['p'] for p in history2]

            if not has_data:  # Only set date_form once
                plt.date_form('Y-m-d H:M:S')
            # Use contrasting color and markers
            plt.plot(times2, prices2, label=outcome2, color='bright-red', marker='small')
            has_data = True

            print(f"\n{outcome2}: {len(history2)} data points")
            if prices2:
                print(f"  Range: ${min(prices2):.4f} - ${max(prices2):.4f}")
                print(f"  Last: ${prices2[-1]:.4f}")
                change = ((prices2[-1] - prices2[0]) / prices2[0] * 100) if prices2[0] != 0 else 0
                print(f"  Change: {change:+.2f}%")

        if not has_data:
            print("\n❌ No data to plot")
            return

        # Add grid for better readability
        plt.grid(True, True)

        # Configure chart with better labels
        plt.xlabel('Time')
        plt.ylabel('Price (USD)')

        # Truncate title if too long
        display_title = title if len(title) <= 80 else title[:77] + "..."
        plt.title(f"{display_title} ({interval})")

        # Show the chart
        print("\n" + "="*120)
        plt.show()
        print("="*120)

    def market_actions_menu(self, market: Dict):
        """Show actions menu for selected market."""
        while True:
            print("\n" + "-"*80)
            print("ACTIONS:")
            print("  1) View price chart")
            print("  2) Export market info")
            print("  0) Back to market list")
            print("-"*80)

            try:
                choice = input("\nChoice: ").strip()

                if choice == '0':
                    break
                elif choice == '1':
                    self.chart_price_history(market)
                elif choice == '2':
                    self.export_market_info(market)
                else:
                    print("❌ Invalid choice")
            except KeyboardInterrupt:
                break

    def browse_markets_with_pagination(self, markets: List[Dict]):
        """Browse markets with pagination and selection."""
        page = 0
        total_pages = (len(markets) - 1) // 50 + 1

        while True:
            page_markets = self.display_markets(markets, page=page, page_size=50)

            if total_pages == 1:
                # No pagination needed, just select
                market = self.select_market(page_markets)
                if market:
                    self.display_market_details(market)
                    self.market_actions_menu(market)
                break
            else:
                # Show pagination navigation
                choice = input("\nChoice ([1-50] select, [N]ext, [P]rev, [B]ack): ").strip().lower()

                if choice == 'b' or choice == '0':
                    break
                elif choice == 'n' and page < total_pages - 1:
                    page += 1
                elif choice == 'p' and page > 0:
                    page -= 1
                elif choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(page_markets):
                        market = page_markets[idx]
                        self.display_market_details(market)
                        self.market_actions_menu(market)
                    else:
                        print(f"❌ Invalid choice. Enter 1-{len(page_markets)}")
                else:
                    print("❌ Invalid choice")

    def export_market_info(self, market: Dict):
        """Export market information to file."""
        market_id = market.get('id')
        filename = f"market_{market_id}_info.txt"

        try:
            with open(filename, 'w') as f:
                f.write("POLYMARKET MARKET INFORMATION\n")
                f.write("="*80 + "\n\n")
                f.write(f"Market ID: {market.get('id', 'N/A')}\n")
                f.write(f"Question:  {market.get('question', 'N/A')}\n")
                f.write(f"Outcome 1: {market.get('outcome1', 'N/A')}\n")
                f.write(f"Outcome 2: {market.get('outcome2', 'N/A')}\n")
                f.write(f"Volume:    ${float(market.get('volume', 0)):,.2f}\n")
                f.write(f"Status:    {'Closed' if market.get('closed', '').lower() == 'true' else 'Open'}\n")
                f.write(f"Created:   {market.get('createdAt', 'N/A')}\n")
                if market.get('closedTime'):
                    f.write(f"Closed:    {market.get('closedTime')}\n")
                f.write(f"\nToken 1: {market.get('token1', 'N/A')}\n")
                f.write(f"Token 2: {market.get('token2', 'N/A')}\n")

            print(f"\n✓ Exported to {filename}")
        except Exception as e:
            print(f"\n❌ Export failed: {e}")

    def run(self):
        """Main interactive loop."""
        print("\n" + "="*100)
        print("POLYMARKET EXPLORER - Interactive Market Browser & Chart Viewer")
        print("="*100)

        # Load markets
        print("\n📂 Loading markets from cache...")
        if not self.load_markets_from_cache():
            print("❌ Could not load markets from cache.")
            print(f"   Run: python crypto_market_finder.py --all")
            return

        print(f"✓ Loaded {len(self.markets)} markets")

        while True:
            print("\n" + "="*100)
            print("MAIN MENU")
            print("="*100)
            print("  1) Browse all markets")
            print("  2) Search by keyword")
            print("  3) Filter by status (open/closed)")
            print("  0) Exit")
            print("="*100)

            try:
                choice = input("\nChoice: ").strip()

                if choice == '0':
                    print("\n👋 Goodbye!")
                    break

                elif choice == '1':
                    markets = self.filter_markets()
                    self.browse_markets_with_pagination(markets)

                elif choice == '2':
                    keyword = input("\nEnter search keyword: ").strip()
                    if keyword:
                        markets = self.filter_markets(keyword=keyword)
                        self.browse_markets_with_pagination(markets)

                elif choice == '3':
                    print("\n  1) Open markets only")
                    print("  2) Closed markets only")
                    status_choice = input("\nChoice: ").strip()

                    status = 'open' if status_choice == '1' else 'closed' if status_choice == '2' else 'all'
                    markets = self.filter_markets(status=status)
                    self.browse_markets_with_pagination(markets)

                else:
                    print("❌ Invalid choice")

            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break


def main():
    """Entry point."""
    explorer = MarketExplorer()
    explorer.run()


if __name__ == "__main__":
    main()
