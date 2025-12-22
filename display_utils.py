"""
Terminal display utilities for live monitoring
"""
import os
from typing import List, Dict
from config import USE_COLOR, BOX_WIDTH


class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')


def color_text(text: str, color: str) -> str:
    """Apply color to text if colors enabled"""
    if not USE_COLOR:
        return text
    return f"{color}{text}{Colors.END}"


def format_currency(amount: float) -> str:
    """Format number as currency"""
    if amount >= 1_000_000:
        return f"${amount/1_000_000:.2f}M"
    elif amount >= 1_000:
        return f"${amount/1_000:.1f}K"
    else:
        return f"${amount:,.2f}"


def format_percentage(value: float, show_sign: bool = True) -> str:
    """Format percentage with optional sign and color"""
    sign = "▲" if value >= 0 else "▼"
    color = Colors.GREEN if value >= 0 else Colors.RED

    if show_sign:
        return color_text(f"{sign} {value:+.2f}%", color)
    else:
        return color_text(f"{value:.2f}%", color)


def draw_header(title: str, subtitle: str = "") -> str:
    """Draw a header box"""
    width = BOX_WIDTH
    lines = []
    lines.append(f"╔{'═' * (width - 2)}╗")
    lines.append(f"║ {color_text(title, Colors.BOLD):<{width - 3}}║")
    if subtitle:
        lines.append(f"║ {subtitle:<{width - 3}}║")
    lines.append(f"╚{'═' * (width - 2)}╝")
    return "\n".join(lines)


def draw_box(title: str, content: List[str]) -> str:
    """Draw a box with title and content"""
    width = BOX_WIDTH
    top = f"┌{'─' * (width - 2)}┐"
    title_line = f"│ {color_text(title, Colors.CYAN):<{width - 3}}│"
    separator = f"├{'─' * (width - 2)}┤"
    bottom = f"└{'─' * (width - 2)}┘"

    # Strip ANSI codes for length calculation
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

    lines = [top, title_line, separator]
    for line in content:
        # Calculate visible length (without ANSI codes)
        visible_len = len(ansi_escape.sub('', line))
        padding = width - 3 - visible_len
        lines.append(f"│ {line}{' ' * padding}│")
    lines.append(bottom)

    return "\n".join(lines)


def format_price_panel(up_price: float, down_price: float,
                       up_change: float = None, down_change: float = None,
                       up_cap: float = None, down_cap: float = None) -> List[str]:
    """Format the price panel content"""
    content = []

    # UP price line
    up_line = f"UP:   ${up_price:.4f}"
    if up_change is not None:
        up_line += f" {format_percentage(up_change)}"
    if up_cap is not None:
        up_line += f"    Market Cap: {format_currency(up_cap)}"
    content.append(up_line)

    # DOWN price line
    down_line = f"DOWN: ${down_price:.4f}"
    if down_change is not None:
        down_line += f" {format_percentage(down_change)}"
    if down_cap is not None:
        down_line += f"    Market Cap: {format_currency(down_cap)}"
    content.append(down_line)

    # Spread
    spread = abs(up_price - down_price)
    spread_pct = (spread / ((up_price + down_price) / 2)) * 100
    content.append(f"Spread: ${spread:.4f} ({spread_pct:.2f}%)")

    return content


def format_orderbook(bids: List[Dict], asks: List[Dict], depth: int = 5) -> List[str]:
    """Format orderbook as a table"""
    content = []

    # Header
    header = f"{'BIDS (UP)':^30} │ {'ASKS (DOWN)':^30}"
    content.append(header)

    # Levels
    for i in range(min(depth, max(len(bids), len(asks)))):
        bid = bids[i] if i < len(bids) else {}
        ask = asks[i] if i < len(asks) else {}

        bid_str = ""
        if bid:
            price = bid.get('price', 0)
            size = bid.get('size', 0)
            bid_str = color_text(f"${price:.4f} x {size:>6,.0f}", Colors.GREEN)

        ask_str = ""
        if ask:
            price = ask.get('price', 0)
            size = ask.get('size', 0)
            ask_str = color_text(f"${price:.4f} x {size:>6,.0f}", Colors.RED)

        # Calculate padding for visible content
        import re
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        bid_visible = len(ansi_escape.sub('', bid_str))
        ask_visible = len(ansi_escape.sub('', ask_str))

        bid_padded = bid_str + ' ' * (30 - bid_visible)
        ask_padded = ask_str + ' ' * (30 - ask_visible)

        content.append(f"{bid_padded} │ {ask_padded}")

    # Total liquidity
    bid_total = sum(b.get('size', 0) * b.get('price', 0) for b in bids[:depth])
    ask_total = sum(a.get('size', 0) * a.get('price', 0) for a in asks[:depth])

    total_line = f"Total: {format_currency(bid_total):>20} │ Total: {format_currency(ask_total):>20}"
    content.append(total_line)

    return content


def format_trade(trade: Dict, show_outcome: bool = True) -> str:
    """Format a single trade"""
    timestamp = trade.get('timestamp', '')[:8]  # HH:MM:SS
    side = trade.get('side', 'N/A')
    color = Colors.GREEN if side == 'BUY' else Colors.RED
    outcome = trade.get('outcome', 'UP' if side == 'BUY' else 'DOWN')
    price = trade.get('price', 0)
    size = trade.get('size', 0)
    total = price * size

    side_colored = color_text(f"{side:4}", color)

    if show_outcome:
        return f"{timestamp}  {side_colored}  {outcome:4}  ${price:.4f} x {size:>6,.0f}   ({format_currency(total)})"
    else:
        return f"{timestamp}  {side_colored}  ${price:.4f} x {size:>6,.0f}   ({format_currency(total)})"


def format_volume_metrics(trades: List[Dict]) -> List[str]:
    """Format volume metrics from trades"""
    content = []

    if not trades:
        content.append("No trade data available")
        return content

    # Calculate metrics
    total_volume = sum(t.get('price', 0) * t.get('size', 0) for t in trades)
    total_trades = len(trades)
    avg_trade = total_volume / total_trades if total_trades > 0 else 0

    content.append(f"Recent Volume: {format_currency(total_volume)}  ({total_trades} trades)")
    content.append(f"Avg Trade Size: {format_currency(avg_trade)}")

    return content
