"""
Lightweight Hibachi Market Data Client
Uses raw HTTP requests to Hibachi public API - no SDK dependency.
Works with Python 3.11+.
"""

import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

API_URL = "https://api.hibachi.xyz"
DATA_API_URL = "https://data-api.hibachi.xyz"


class HibachiMarketClient:
    """
    Lightweight client for Hibachi public market data endpoints.
    No authentication needed.
    """

    def __init__(self, api_url: str = API_URL, data_api_url: str = DATA_API_URL):
        self.api_url = api_url
        self.data_api_url = data_api_url
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def _get(self, url: str, params: Optional[Dict] = None) -> Any:
        """Make a GET request."""
        resp = self.session.get(url, params=params, timeout=10)
        resp.raise_for_status()
        if not resp.content:
            logger.warning(f"Empty response from {url}")
            return {}
        return resp.json()

    # =========================================================================
    # Exchange info
    # =========================================================================

    def get_exchange_info(self) -> Dict:
        """Get exchange information including fee config and contracts."""
        return self._get(f"{self.api_url}/exchange-info")

    def get_inventory(self) -> Dict:
        """Get full inventory with markets, fees, and trading tiers."""
        return self._get(f"{self.api_url}/inventory")

    # =========================================================================
    # Prices
    # =========================================================================

    def get_prices(self, symbol: str) -> Dict:
        """
        Get current prices for a symbol.
        Returns: {bidPrice, askPrice, markPrice, spotPrice, tradePrice, fundingRateEstimation}
        """
        return self._get(f"{self.data_api_url}/market/data/prices", params={"symbol": symbol})

    def get_bid_ask(self, symbol: str):
        """Get bid and ask prices. Returns (bid, ask) tuple."""
        try:
            data = self.get_prices(symbol)
            bid = float(data['bidPrice'])
            ask = float(data['askPrice'])
            return bid, ask
        except Exception as e:
            logger.error(f"Error getting bid/ask for {symbol}: {e}")
            return None, None

    # =========================================================================
    # Orderbook
    # =========================================================================

    def get_orderbook(self, symbol: str, depth: int = 5, granularity: str = '0.1') -> Dict:
        """
        Get orderbook for a symbol.
        Returns: {bid: [{price, quantity}, ...], ask: [{price, quantity}, ...]}
        """
        return self._get(f"{self.data_api_url}/market/data/orderbook", params={
            "symbol": symbol,
            "depth": depth,
            "granularity": granularity,
        })

    def get_orderbook_levels(self, symbol: str, levels: int = 5) -> Dict:
        """Get orderbook formatted as {bids: [[price, qty], ...], asks: [...]}."""
        try:
            data = self.get_orderbook(symbol, depth=levels)
            return {
                'bids': [[float(level['price']), float(level['quantity'])] for level in data.get('bid', [])],
                'asks': [[float(level['price']), float(level['quantity'])] for level in data.get('ask', [])],
            }
        except Exception as e:
            logger.error(f"Error getting orderbook for {symbol}: {e}")
            return {'bids': [], 'asks': []}

    # =========================================================================
    # Stats and history
    # =========================================================================

    def get_stats(self, symbol: str) -> Dict:
        """Get 24h stats: {high24h, low24h, symbol, volume24h}."""
        return self._get(f"{self.data_api_url}/market/data/stats", params={"symbol": symbol})

    def get_klines(self, symbol: str, interval: str = '1h', limit: int = 100) -> Dict:
        """
        Get candlestick data.
        Intervals: 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w
        """
        return self._get(f"{self.data_api_url}/market/data/klines", params={
            "symbol": symbol,
            "interval": interval,
            "limit": limit,
        })

    def get_trades(self, symbol: str) -> Dict:
        """Get recent trades."""
        return self._get(f"{self.data_api_url}/market/data/trades", params={"symbol": symbol})

    def get_open_interest(self, symbol: str) -> Dict:
        """Get open interest."""
        return self._get(f"{self.data_api_url}/market/data/open-interest", params={"symbol": symbol})

    # =========================================================================
    # Market info helpers
    # =========================================================================

    def get_available_markets(self) -> List[Dict]:
        """Get list of all available trading pairs with metadata."""
        try:
            data = self.get_inventory()
            markets = []
            for market in data.get('markets', []):
                contract = market.get('contract', {})
                info = market.get('info', {})
                initial_margin = float(contract.get('initialMarginRate', '1'))
                max_lev = int(1 / initial_margin) if initial_margin > 0 else 1
                markets.append({
                    'symbol': contract.get('symbol', ''),
                    'name': contract.get('displayName', ''),
                    'status': contract.get('status', ''),
                    'min_order_size': contract.get('minOrderSize', ''),
                    'step_size': contract.get('stepSize', ''),
                    'tick_size': contract.get('tickSize', ''),
                    'initial_margin_rate': contract.get('initialMarginRate', ''),
                    'max_leverage': max_lev,
                    'mark_price': info.get('markPrice', ''),
                })
            return markets
        except Exception as e:
            logger.error(f"Error getting markets: {e}")
            return []

    def get_fee_config(self) -> Dict:
        """Get fee configuration."""
        try:
            data = self.get_exchange_info()
            return data.get('feeConfig', {})
        except Exception as e:
            logger.error(f"Error getting fee config: {e}")
            return {}

    def get_market_leverage(self, symbol: str) -> int:
        """Get max leverage for a specific market."""
        markets = self.get_available_markets()
        for m in markets:
            if m['symbol'] == symbol:
                return m['max_leverage']
        return 1

    def get_step_size(self, symbol: str) -> float:
        """Get step size for order quantity rounding."""
        markets = self.get_available_markets()
        for m in markets:
            if m['symbol'] == symbol:
                return float(m['step_size'])
        return 0.00000001

    def round_to_step_size(self, symbol: str, quantity: float) -> float:
        """Round quantity to the correct step size."""
        step = self.get_step_size(symbol)
        if step > 0:
            precision = len(str(step).rstrip('0').split('.')[-1])
            return round(quantity - (quantity % step), precision)
        return quantity

    def usd_to_asset_size(self, symbol: str, usd_value: float) -> float:
        """Convert USD value to asset size using current ask price."""
        _, ask = self.get_bid_ask(symbol)
        if ask and ask > 0:
            raw = usd_value / ask
            return self.round_to_step_size(symbol, raw)
        return 0.0
