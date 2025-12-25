"""
Shared utilities for Polymarket market-finder scripts.

This module is extracted from `crypto_market_finder.py` so multiple scripts can
reuse fetching, date filtering, display formatting, and CSV caching.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from api_client import PolymarketAPIClient
from config import DEFAULT_MAX_MARKETS, MARKET_FETCH_BATCH_SIZE


def _parse_created_at(created_at: str) -> Optional[datetime]:
    """
    Parse Polymarket `createdAt` which is typically ISO with `Z`.
    Returns an aware datetime in UTC.
    """
    if not created_at:
        return None
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def _parse_date_bound(date_str: Optional[str]) -> Optional[datetime]:
    """
    Parse CLI date bounds.

    Accepts:
    - YYYY-MM-DD (interpreted as midnight UTC)
    - full ISO timestamp (timezone-aware preferred; naive treated as UTC)
    Returns an aware datetime in UTC.
    """
    if not date_str:
        return None
    s = date_str.strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Try YYYY-MM-DD explicitly
        try:
            dt = datetime.strptime(s, "%Y-%m-%d")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def text_matches_any_keyword(text: str, keywords: Sequence[str]) -> bool:
    """Case-insensitive 'any keyword is a substring' match."""
    if not text or not keywords:
        return False
    t = text.lower()
    return any(k.lower() in t for k in keywords if k)


def market_matches_any_keywords(market: Dict, keywords: Sequence[str]) -> bool:
    """
    Match keywords against common market text fields.
    We prioritize `question`/`title`, but also include `description` and `slug`.
    """
    if not keywords:
        return True
    fields = [
        market.get("question", "") or "",
        market.get("title", "") or "",
        market.get("description", "") or "",
        market.get("slug", "") or "",
    ]
    combined = " ".join(f for f in fields if f)
    return text_matches_any_keyword(combined, keywords)


def fetch_all_markets(
    client: PolymarketAPIClient,
    closed: Optional[bool] = None,
    max_markets: int = DEFAULT_MAX_MARKETS,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    newest_first: bool = True,
) -> List[Dict]:
    """
    Fetch markets with pagination and optional date filtering.

    Date filtering is applied to `createdAt` (UTC). `start_date` is inclusive,
    `end_date` is exclusive.
    """
    all_markets: List[Dict] = []
    offset = 0
    batch_size = MARKET_FETCH_BATCH_SIZE

    print("\nFetching markets from Polymarket...")
    if start_date:
        print(f"  Filtering markets created on or after: {start_date}")
    if end_date:
        print(f"  Filtering markets created before: {end_date}")

    start_dt = _parse_date_bound(start_date)
    end_dt = _parse_date_bound(end_date)

    while len(all_markets) < max_markets:
        print(f"  Fetching batch at offset {offset}...")
        markets = client.get_markets(
            limit=batch_size,
            offset=offset,
            closed=closed,
            order="createdAt",
            ascending=not newest_first,  # API: ascending=True means oldest first
        )

        if not markets:
            break

        filtered_markets: List[Dict] = []
        for market in markets:
            created_at = market.get("createdAt", "") or ""
            market_dt = _parse_created_at(created_at)
            if market_dt is None:
                continue

            if start_dt and market_dt < start_dt:
                if newest_first:
                    print(f"  Reached markets before {start_date}, stopping...")
                    return all_markets
                continue

            if end_dt and market_dt >= end_dt:
                if not newest_first:
                    print(f"  Reached markets after {end_date}, stopping...")
                    return all_markets
                continue

            filtered_markets.append(market)

        all_markets.extend(filtered_markets)
        offset += len(markets)

        if len(markets) < batch_size:
            break

    if len(all_markets) >= max_markets:
        print(f"  Reached maximum market limit ({max_markets})")
        all_markets = all_markets[:max_markets]

    print(f"✓ Fetched {len(all_markets)} total markets\n")
    return all_markets


def separate_by_status(markets: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Separate markets into resolved (closed) and unresolved (open)."""
    resolved: List[Dict] = []
    unresolved: List[Dict] = []
    for market in markets:
        if market.get("closed", False):
            resolved.append(market)
        else:
            unresolved.append(market)
    return resolved, unresolved


@dataclass(frozen=True)
class MarketParsed:
    token1: str
    token2: str
    outcome1: str
    outcome2: str


def _parse_tokens_and_outcomes(market: Dict) -> MarketParsed:
    clob_tokens = market.get("clobTokenIds", [])
    if isinstance(clob_tokens, str):
        try:
            clob_tokens = json.loads(clob_tokens)
        except Exception:
            clob_tokens = []

    outcomes = market.get("outcomes", [])
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = []

    token1 = clob_tokens[0] if len(clob_tokens) > 0 else ""
    token2 = clob_tokens[1] if len(clob_tokens) > 1 else ""
    outcome1 = outcomes[0] if len(outcomes) > 0 else "YES"
    outcome2 = outcomes[1] if len(outcomes) > 1 else "NO"

    return MarketParsed(token1=token1, token2=token2, outcome1=outcome1, outcome2=outcome2)


def format_market_display(market: Dict, index: int, show_resolution: bool = False) -> str:
    """Format a market for terminal display."""
    question = market.get("question", "") or market.get("title", "")
    volume = float(market.get("volume", 0) or 0)
    market_id = market.get("id", "") or ""

    is_closed = market.get("closed", False)
    closed_time = market.get("closedTime", "") or ""
    end_date = market.get("endDate", "") or ""

    parsed = _parse_tokens_and_outcomes(market)
    token1 = parsed.token1 or "N/A"
    token2 = parsed.token2 or "N/A"

    lines: List[str] = []
    resolution = ""
    if show_resolution and closed_time:
        resolution = " (RESOLVED)"

    lines.append(f"[{index}] {question}{resolution}")
    lines.append(f"    Volume: ${volume:,.0f} | Market ID: {str(market_id)[:10]}...")

    if is_closed and closed_time:
        lines.append(f"    Closed: {closed_time[:10]}")
    elif end_date:
        lines.append(f"    Expires: {end_date[:10]} | Status: OPEN")
    else:
        lines.append("    Status: OPEN")

    if token1 != "N/A" and token2 != "N/A":
        token1_short = token1[:10] + "..." if len(token1) > 10 else token1
        token2_short = token2[:10] + "..." if len(token2) > 10 else token2
        lines.append(
            f"    Tokens: {parsed.outcome1}={token1_short}, {parsed.outcome2}={token2_short}"
        )

    return "\n".join(lines)


def save_to_csv(markets: List[Dict], filename: str):
    """Save markets to CSV file (creates parent directory if needed)."""
    if not markets:
        print(f"No markets to save to {filename}")
        return

    parent = os.path.dirname(filename)
    if parent:
        os.makedirs(parent, exist_ok=True)

    headers = [
        "id",
        "question",
        "outcome1",
        "outcome2",
        "token1",
        "token2",
        "volume",
        "closed",
        "closedTime",
        "createdAt",
    ]

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()

        for market in markets:
            parsed = _parse_tokens_and_outcomes(market)
            writer.writerow(
                {
                    "id": market.get("id", ""),
                    "question": market.get("question", "") or market.get("title", ""),
                    "outcome1": parsed.outcome1,
                    "outcome2": parsed.outcome2,
                    "token1": parsed.token1,
                    "token2": parsed.token2,
                    "volume": market.get("volume", 0),
                    "closed": market.get("closed", False),
                    "closedTime": market.get("closedTime", ""),
                    "createdAt": market.get("createdAt", ""),
                }
            )

    print(f"✓ Saved {len(markets)} markets to {filename}")


