"""
Polymarket API client with rate limiting and retry logic
"""
import requests
import time
from typing import Dict, List, Optional
from config import (
    GAMMA_API_BASE, CLOB_API_BASE,
    RATE_LIMIT_DELAY, RATE_LIMIT_BACKOFF,
    MAX_RETRIES, TIMEOUT_SECONDS
)


class PolymarketAPIClient:
    """API client for Polymarket with automatic rate limiting and retries"""

    def __init__(self, auth_manager=None):
        """
        Initialize API client.

        Args:
            auth_manager: Optional AuthManager instance for authenticated requests
        """
        self.session = requests.Session()
        self.last_request_time = 0
        self.auth_manager = auth_manager

    def _rate_limit(self):
        """Enforce rate limiting between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < RATE_LIMIT_DELAY:
            time.sleep(RATE_LIMIT_DELAY - elapsed)
        self.last_request_time = time.time()

    def _request_with_retry(self, url: str, params: Dict = None, headers: Dict = None) -> Optional[Dict]:
        """
        Make HTTP request with retry logic.

        Args:
            url: Request URL
            params: Query parameters
            headers: HTTP headers (for authentication)

        Returns:
            Response JSON or None if failed
        """
        self._rate_limit()

        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=TIMEOUT_SECONDS
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    backoff = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                    print(f"Rate limited (429), waiting {backoff}s...")
                    time.sleep(backoff)
                    continue
                elif response.status_code >= 500:
                    backoff = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                    print(f"Server error {response.status_code}, retrying in {backoff}s...")
                    time.sleep(backoff)
                    continue
                else:
                    print(f"API error {response.status_code}: {response.text}")
                    return None

            except requests.exceptions.Timeout:
                backoff = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                print(f"Request timeout (attempt {attempt + 1}/{MAX_RETRIES}), retrying...")
                time.sleep(backoff)
            except requests.exceptions.RequestException as e:
                backoff = RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)]
                print(f"Network error: {e}, retrying...")
                time.sleep(backoff)

        return None

    # === Gamma API Methods ===

    def get_markets(self, limit: int = 1000, offset: int = 0,
                   closed: Optional[bool] = None, order: str = "createdAt",
                   ascending: bool = True) -> List[Dict]:
        """
        Fetch markets from Gamma API

        Args:
            limit: Number of markets to fetch
            offset: Offset for pagination
            closed: Filter by closed status (None for all)
            order: Order field (default: createdAt)
            ascending: Sort ascending (default: True)

        Returns:
            List of market dictionaries
        """
        url = f"{GAMMA_API_BASE}/markets"
        params = {
            "limit": limit,
            "offset": offset,
            "order": order,
            "ascending": str(ascending).lower()
        }
        if closed is not None:
            params["closed"] = str(closed).lower()

        data = self._request_with_retry(url, params)
        return data if isinstance(data, list) else []

    def get_market_by_id(self, market_id: str) -> Optional[Dict]:
        """
        Fetch a single market by ID from Gamma API

        Args:
            market_id: Market ID (e.g., "995839")

        Returns:
            Market dictionary or None if not found
        """
        url = f"{GAMMA_API_BASE}/markets"
        params = {"id": market_id}

        data = self._request_with_retry(url, params)

        # API returns a list with one item
        if isinstance(data, list) and len(data) > 0:
            return data[0]

        return None

    def get_events(self, closed: bool = False, limit: int = 100) -> List[Dict]:
        """
        Fetch events from Gamma API

        Args:
            closed: Whether to fetch closed events
            limit: Number of events to fetch

        Returns:
            List of event dictionaries
        """
        url = f"{GAMMA_API_BASE}/events"
        params = {"closed": str(closed).lower(), "limit": limit}

        data = self._request_with_retry(url, params)
        return data if isinstance(data, list) else []

    # === CLOB API Methods ===

    def get_price(self, token_id: str, side: str = "buy") -> Optional[Dict]:
        """
        Get current price for a token

        Args:
            token_id: Token ID to fetch price for
            side: Order side - "buy" or "sell" (default: "buy")

        Returns:
            Price dictionary or None if unavailable
        """
        url = f"{CLOB_API_BASE}/price"
        params = {"token_id": token_id, "side": side}

        return self._request_with_retry(url, params)

    def get_orderbook(self, token_id: str) -> Optional[Dict]:
        """
        Get orderbook for a token

        Args:
            token_id: Token ID to fetch orderbook for

        Returns:
            Orderbook dictionary with bids/asks or None if unavailable
        """
        url = f"{CLOB_API_BASE}/book"
        params = {"token_id": token_id}

        return self._request_with_retry(url, params)

    def get_trades(self, token_id: str, limit: int = 100) -> List[Dict]:
        """
        Get recent trades for a token.

        Note: This endpoint requires authentication. Returns empty list if:
        - No auth credentials configured
        - Authentication fails (401)
        - No trades available

        Args:
            token_id: Token ID to fetch trades for
            limit: Number of trades to fetch

        Returns:
            List of trade dictionaries
        """
        url = f"{CLOB_API_BASE}/trades"
        params = {"token_id": token_id, "limit": limit}

        # Add authentication headers if available
        headers = None
        if self.auth_manager and self.auth_manager.has_credentials():
            try:
                # Build request path with query params for signature
                request_path = f"/trades?token_id={token_id}&limit={limit}"
                headers = self.auth_manager.get_auth_headers("GET", request_path)
            except Exception as e:
                print(f"Warning: Failed to generate auth headers: {e}")

        data = self._request_with_retry(url, params, headers=headers)
        return data if isinstance(data, list) else []
