#!/usr/bin/env python3
"""
Rich Terminal UI for Polymarket Monitor

Beautiful, live-updating terminal interface using the Rich library.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import deque

try:
    from rich.console import Console, Group
    from rich.live import Live
    from rich.table import Table
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.style import Style
    from rich.bar import Bar
    from rich.align import Align
    from rich import box
except ImportError:
    print("Error: rich not installed. Run: pip install rich")
    raise


# Color scheme
COLORS = {
    'up': 'green',
    'down': 'red', 
    'neutral': 'white',
    'muted': 'dim white',
    'accent': 'cyan',
    'warning': 'yellow',
    'header': 'bold white on blue',
    'buy': 'green',
    'sell': 'red',
}


class TerminalUI:
    """Rich-based terminal UI for market monitoring"""
    
    def __init__(self, market_name: str = "Market Monitor", max_trades: int = 10):
        self.console = Console()
        self.market_name = market_name
        self.max_trades = max_trades
        self.live: Optional[Live] = None
        
        # Data state
        self.up_price: float = 0.0
        self.down_price: float = 0.0
        self.up_change: Optional[float] = None
        self.down_change: Optional[float] = None
        self.spread: float = 0.0
        
        self.orderbook_up: Dict = {'bids': [], 'asks': []}
        self.orderbook_down: Dict = {'bids': [], 'asks': []}
        
        self.trades: deque = deque(maxlen=max_trades)
        self.trade_count: int = 0
        self.total_volume: float = 0.0
        
        self.ws_connected: bool = False
        self.last_update: Optional[datetime] = None
        self.events_received: int = 0
    
    def start(self):
        """Start the live display"""
        self.live = Live(
            self._build_layout(),
            console=self.console,
            refresh_per_second=4,
            screen=True,  # Use alternate screen buffer
            transient=False
        )
        self.live.start()
    
    def stop(self):
        """Stop the live display"""
        if self.live:
            self.live.stop()
    
    def update_prices(self, up_price: float, down_price: float, 
                      up_change: Optional[float] = None, 
                      down_change: Optional[float] = None):
        """Update price data"""
        self.up_price = up_price
        self.down_price = down_price
        self.up_change = up_change
        self.down_change = down_change
        self.spread = abs(up_price - down_price)
        self.last_update = datetime.now(timezone.utc)
        self._refresh()
    
    def update_orderbook(self, token: str, bids: List[Dict], asks: List[Dict]):
        """Update orderbook data"""
        if token == 'up':
            self.orderbook_up = {'bids': bids, 'asks': asks}
        else:
            self.orderbook_down = {'bids': bids, 'asks': asks}
        self._refresh()
    
    def add_trade(self, trade: Dict):
        """Add a new trade"""
        self.trades.appendleft(trade)
        self.trade_count += 1
        price = float(trade.get('price', 0))
        size = float(trade.get('size', 0))
        self.total_volume += price * size
        self._refresh()
    
    def set_ws_status(self, connected: bool):
        """Update WebSocket connection status"""
        self.ws_connected = connected
        self._refresh()
    
    def increment_events(self):
        """Increment event counter (for stats)"""
        self.events_received += 1
    
    def _refresh(self):
        """Refresh the display"""
        if self.live:
            self.live.update(self._build_layout())
    
    def _build_layout(self) -> Layout:
        """Build the full layout"""
        layout = Layout()
        
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="right", ratio=1)
        )
        
        layout["left"].split_column(
            Layout(name="prices", size=12),
            Layout(name="orderbook")
        )
        
        layout["right"].split_column(
            Layout(name="visual", size=8),
            Layout(name="trades")
        )
        
        # Populate sections
        layout["header"].update(self._build_header())
        layout["prices"].update(self._build_prices_panel())
        layout["orderbook"].update(self._build_orderbook_panel())
        layout["visual"].update(self._build_visual_panel())
        layout["trades"].update(self._build_trades_panel())
        layout["footer"].update(self._build_footer())
        
        return layout
    
    def _build_header(self) -> Panel:
        """Build header panel"""
        ws_status = "[green]● LIVE[/]" if self.ws_connected else "[red]● OFFLINE[/]"
        
        time_str = ""
        if self.last_update:
            time_str = self.last_update.strftime('%H:%M:%S UTC')
        
        header_text = Text()
        header_text.append(f"  {self.market_name}", style="bold white")
        header_text.append(f"  │  {ws_status}", style="white")
        header_text.append(f"  │  {time_str}", style="dim white")
        
        return Panel(
            Align.left(header_text),
            style="on dark_blue",
            box=box.HEAVY
        )
    
    def _build_prices_panel(self) -> Panel:
        """Build prices panel with visual indicators"""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Label", style="bold")
        table.add_column("Price", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Bar", width=20)
        
        # UP price row
        up_change_str = ""
        up_style = "green"
        if self.up_change is not None:
            if self.up_change > 0:
                up_change_str = f"▲ +{self.up_change:.2f}%"
                up_style = "green"
            elif self.up_change < 0:
                up_change_str = f"▼ {self.up_change:.2f}%"
                up_style = "red"
            else:
                up_change_str = "─ 0.00%"
                up_style = "dim"
        
        up_bar = self._make_price_bar(self.up_price, "green")
        
        table.add_row(
            Text("UP", style="bold green"),
            Text(f"${self.up_price:.4f}", style="bold white"),
            Text(up_change_str, style=up_style),
            up_bar
        )
        
        # DOWN price row
        down_change_str = ""
        down_style = "red"
        if self.down_change is not None:
            if self.down_change > 0:
                down_change_str = f"▲ +{self.down_change:.2f}%"
                down_style = "green"
            elif self.down_change < 0:
                down_change_str = f"▼ {self.down_change:.2f}%"
                down_style = "red"
            else:
                down_change_str = "─ 0.00%"
                down_style = "dim"
        
        down_bar = self._make_price_bar(self.down_price, "red")
        
        table.add_row(
            Text("DOWN", style="bold red"),
            Text(f"${self.down_price:.4f}", style="bold white"),
            Text(down_change_str, style=down_style),
            down_bar
        )
        
        # Spread row
        spread_pct = (self.spread / self.up_price * 100) if self.up_price > 0 else 0
        table.add_row(
            Text("SPREAD", style="dim"),
            Text(f"${self.spread:.4f}", style="dim"),
            Text(f"({spread_pct:.1f}%)", style="dim"),
            Text("")
        )
        
        return Panel(
            table,
            title="[bold]PRICES[/]",
            border_style="cyan",
            box=box.ROUNDED
        )
    
    def _make_price_bar(self, price: float, color: str) -> Text:
        """Create a visual price bar"""
        bar_width = 18
        filled = int(price * bar_width)
        empty = bar_width - filled
        
        bar_text = Text()
        bar_text.append("█" * filled, style=color)
        bar_text.append("░" * empty, style="dim")
        return bar_text
    
    def _build_visual_panel(self) -> Panel:
        """Build visual representation panel"""
        # Create a visual comparison bar
        total = self.up_price + self.down_price
        if total > 0:
            up_pct = (self.up_price / total) * 100
            down_pct = (self.down_price / total) * 100
        else:
            up_pct = down_pct = 50
        
        bar_width = 40
        up_width = int((up_pct / 100) * bar_width)
        down_width = bar_width - up_width
        
        visual = Text()
        visual.append("\n")
        visual.append(f"  UP {up_pct:.1f}%".ljust(12), style="bold green")
        visual.append(" " * 16)
        visual.append(f"{down_pct:.1f}% DOWN".rjust(12), style="bold red")
        visual.append("\n\n")
        visual.append("  ")
        visual.append("█" * up_width, style="green")
        visual.append("█" * down_width, style="red")
        visual.append("\n")
        
        # Add implied probability interpretation
        visual.append("\n")
        if self.up_price > self.down_price:
            leader = "UP"
            confidence = up_pct
            style = "green"
        elif self.down_price > self.up_price:
            leader = "DOWN"
            confidence = down_pct
            style = "red"
        else:
            leader = "TIED"
            confidence = 50
            style = "yellow"
        
        visual.append(f"  Market favors: ", style="dim")
        visual.append(f"{leader}", style=f"bold {style}")
        visual.append(f" ({confidence:.1f}% implied probability)", style="dim")
        
        return Panel(
            visual,
            title="[bold]PROBABILITY[/]",
            border_style="magenta",
            box=box.ROUNDED
        )
    
    def _build_orderbook_panel(self) -> Panel:
        """Build orderbook panel"""
        table = Table(show_header=True, box=box.SIMPLE, padding=(0, 1))
        table.add_column("Price", justify="right", style="green")
        table.add_column("Size", justify="right")
        table.add_column("│", justify="center", style="dim")
        table.add_column("Price", justify="right", style="red")
        table.add_column("Size", justify="right")
        
        bids = self.orderbook_up.get('bids', [])[:5]
        asks = self.orderbook_down.get('asks', [])[:5]
        
        max_rows = max(len(bids), len(asks), 1)
        
        for i in range(max_rows):
            bid_price = ""
            bid_size = ""
            ask_price = ""
            ask_size = ""
            
            if i < len(bids):
                bid_price = f"${bids[i].get('price', 0):.4f}"
                bid_size = f"{bids[i].get('size', 0):,.0f}"
            
            if i < len(asks):
                ask_price = f"${asks[i].get('price', 0):.4f}"
                ask_size = f"{asks[i].get('size', 0):,.0f}"
            
            table.add_row(bid_price, bid_size, "│", ask_price, ask_size)
        
        # Calculate totals
        bid_total = sum(b.get('price', 0) * b.get('size', 0) for b in bids)
        ask_total = sum(a.get('price', 0) * a.get('size', 0) for a in asks)
        
        table.add_row("", "", "", "", "", style="dim")
        table.add_row(
            "[dim]Total:[/]", f"[dim]${bid_total:,.0f}[/]",
            "",
            "[dim]Total:[/]", f"[dim]${ask_total:,.0f}[/]"
        )
        
        return Panel(
            table,
            title="[bold]ORDER BOOK[/] [dim](UP Bids │ DOWN Asks)[/]",
            border_style="blue",
            box=box.ROUNDED
        )
    
    def _build_trades_panel(self) -> Panel:
        """Build recent trades panel"""
        if not self.trades:
            content = Text("\n  Waiting for trades...\n", style="dim italic")
            return Panel(
                content,
                title="[bold]RECENT TRADES[/]",
                border_style="yellow",
                box=box.ROUNDED
            )
        
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Time", style="dim", width=8)
        table.add_column("Side", width=4)
        table.add_column("Token", width=5)
        table.add_column("Price", justify="right", width=8)
        table.add_column("Size", justify="right", width=8)
        table.add_column("Value", justify="right", width=10)
        
        for trade in list(self.trades)[:self.max_trades]:
            # Parse timestamp
            ts = trade.get('timestamp', '')
            if ts:
                try:
                    dt = datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
                    time_str = dt.strftime('%H:%M:%S')
                except:
                    time_str = "?"
            else:
                time_str = "?"
            
            side = trade.get('side', '?')
            side_style = "green" if side == "BUY" else "red"
            
            outcome = trade.get('outcome', '?')
            outcome_style = "green" if outcome == "UP" else "red"
            
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))
            value = price * size
            
            table.add_row(
                time_str,
                Text(side[:1], style=f"bold {side_style}"),
                Text(outcome, style=outcome_style),
                f"${price:.4f}",
                f"{size:,.1f}",
                f"${value:,.2f}"
            )
        
        return Panel(
            table,
            title=f"[bold]TRADES[/] [dim]({self.trade_count} total, ${self.total_volume:,.2f} volume)[/]",
            border_style="yellow",
            box=box.ROUNDED
        )
    
    def _build_footer(self) -> Panel:
        """Build footer panel"""
        footer = Text()
        footer.append("  [Ctrl+C] Exit", style="dim")
        footer.append("  │  ", style="dim")
        footer.append(f"Events: {self.events_received}", style="dim")
        footer.append("  │  ", style="dim")
        footer.append(f"Trades: {self.trade_count}", style="dim")
        footer.append("  │  ", style="dim")
        
        if self.ws_connected:
            footer.append("WebSocket: ", style="dim")
            footer.append("Connected", style="green")
        else:
            footer.append("WebSocket: ", style="dim")
            footer.append("Disconnected", style="red")
        
        return Panel(footer, box=box.SIMPLE)


def demo():
    """Demo the UI with fake data"""
    import time
    import random
    
    ui = TerminalUI(market_name="BTC Up or Down - Demo")
    ui.start()
    
    try:
        up_price = 0.55
        down_price = 0.45
        
        for i in range(100):
            # Simulate price changes
            up_price += random.uniform(-0.02, 0.02)
            up_price = max(0.01, min(0.99, up_price))
            down_price = 1 - up_price + random.uniform(-0.05, 0.05)
            down_price = max(0.01, min(0.99, down_price))
            
            up_change = random.uniform(-2, 2)
            down_change = random.uniform(-2, 2)
            
            ui.update_prices(up_price, down_price, up_change, down_change)
            ui.set_ws_status(True)
            
            # Simulate orderbook
            ui.update_orderbook('up', [
                {'price': 0.01, 'size': random.randint(1000, 10000)},
                {'price': 0.02, 'size': random.randint(1000, 5000)},
                {'price': 0.03, 'size': random.randint(500, 3000)},
            ], [])
            
            ui.update_orderbook('down', [], [
                {'price': 0.99, 'size': random.randint(1000, 10000)},
                {'price': 0.98, 'size': random.randint(1000, 5000)},
                {'price': 0.97, 'size': random.randint(500, 3000)},
            ])
            
            # Simulate trades occasionally
            if random.random() > 0.7:
                ui.add_trade({
                    'timestamp': str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                    'side': random.choice(['BUY', 'SELL']),
                    'outcome': random.choice(['UP', 'DOWN']),
                    'price': random.uniform(0.3, 0.7),
                    'size': random.randint(1, 100)
                })
            
            ui.increment_events()
            time.sleep(0.5)
            
    except KeyboardInterrupt:
        pass
    finally:
        ui.stop()


if __name__ == "__main__":
    demo()