"""
Paper Trading Engine for Hibachi Exchange
Uses real market data from Hibachi public API, simulates orders/positions locally.
Built to have the same interface as HibachiAPI so bots can switch between paper and live.
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Optional, Tuple, Dict, Any, List
from dataclasses import dataclass, field, asdict
from hibachi_market import HibachiMarketClient
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

STATE_FILE = os.environ.get("PAPER_STATE_FILE", "/data/paper_state.json")


@dataclass
class PaperPosition:
    symbol: str
    direction: str  # "Long" or "Short"
    quantity: float
    open_price: float
    unrealized_pnl: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class PaperOrder:
    order_id: int
    symbol: str
    side: str  # "buy" or "sell"
    order_type: str  # "limit" or "market"
    quantity: float
    price: float
    status: str = "open"  # "open", "filled", "cancelled"
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class PaperTrade:
    symbol: str
    side: str
    quantity: float
    price: float
    pnl: float = 0.0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()


@dataclass
class PaperState:
    balance: float = 10000.0
    initial_balance: float = 10000.0
    positions: List[Dict] = field(default_factory=list)
    open_orders: List[Dict] = field(default_factory=list)
    trade_history: List[Dict] = field(default_factory=list)
    next_order_id: int = 1


class PaperTradingAPI:
    """
    Paper trading API wrapper that mirrors HibachiAPI interface.
    Uses real market data from Hibachi public endpoints (no auth needed).
    Simulates order fills, positions, and P&L locally.
    """

    def __init__(self, initial_balance: float = 10000.0):
        # Public API client - no auth needed for market data
        self.market_client = HibachiMarketClient()
        self.logger = logging.getLogger(__name__)

        # Load or initialize state
        self.state = self._load_state(initial_balance)

        # Taker fee rate (default Hibachi taker fee)
        self.taker_fee_rate = 0.00045
        self.maker_fee_rate = 0.00015

        # Try to get actual fee rates from exchange
        try:
            fee_config = self.market_client.get_fee_config()
            if fee_config:
                self.taker_fee_rate = float(fee_config.get('tradeTakerFeeRate', self.taker_fee_rate))
                self.maker_fee_rate = float(fee_config.get('tradeMakerFeeRate', self.maker_fee_rate))
        except Exception:
            pass

        print(f"[PAPER] Initialized with ${self.state.balance:.2f} balance")
        print(f"[PAPER] Maker fee: {self.maker_fee_rate*100:.4f}% | Taker fee: {self.taker_fee_rate*100:.4f}%")

    # =========================================================================
    # State persistence
    # =========================================================================

    def _load_state(self, initial_balance: float) -> PaperState:
        """Load state from file or create new state."""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    data = json.load(f)
                state = PaperState(
                    balance=data.get('balance', initial_balance),
                    initial_balance=data.get('initial_balance', initial_balance),
                    positions=data.get('positions', []),
                    open_orders=data.get('open_orders', []),
                    trade_history=data.get('trade_history', []),
                    next_order_id=data.get('next_order_id', 1),
                )
                print(f"[PAPER] Loaded saved state from {STATE_FILE}")
                return state
            except Exception as e:
                print(f"[PAPER] Failed to load state: {e}, starting fresh")

        return PaperState(balance=initial_balance, initial_balance=initial_balance)

    def _save_state(self):
        """Persist state to file."""
        data = {
            'balance': self.state.balance,
            'initial_balance': self.state.initial_balance,
            'positions': self.state.positions,
            'open_orders': self.state.open_orders,
            'trade_history': self.state.trade_history,
            'next_order_id': self.state.next_order_id,
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    def reset_state(self, initial_balance: float = 10000.0):
        """Reset paper trading state."""
        self.state = PaperState(balance=initial_balance, initial_balance=initial_balance)
        self._save_state()
        print(f"[PAPER] State reset. Balance: ${initial_balance:.2f}")

    # =========================================================================
    # Market data (real data from Hibachi public API)
    # =========================================================================

    def test_connection(self):
        """Test the public API connection."""
        try:
            prices = self.market_client.get_prices("BTC/USDT-P")
            return {"status": "ok", "mode": "paper", "btc_price": prices.markPrice}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def get_balances(self):
        """Get paper trading balance."""
        return [{"symbol": "USDT", "quantity": str(self.state.balance)}]

    def get_bid_ask(self, symbol: str):
        """Get current bid and ask prices (real data)."""
        return self.market_client.get_bid_ask(symbol)

    def get_orderbook_levels(self, symbol: str, levels: int = 5):
        """Get orderbook with specified depth (real data)."""
        return self.market_client.get_orderbook_levels(symbol, levels)

    # =========================================================================
    # Position management (simulated)
    # =========================================================================

    def get_position(self, symbol: str):
        """Get position information for a symbol (simulated)."""
        for pos in self.state.positions:
            if pos['symbol'] == symbol:
                size = pos['quantity']
                entry_price = pos['open_price']
                is_long = pos['direction'] == 'Long'

                # Calculate unrealized P&L with real prices
                bid, ask = self.get_bid_ask(symbol)
                if bid and ask:
                    current_price = (bid + ask) / 2
                    if is_long:
                        unrealized_pnl = (current_price - entry_price) * abs(size)
                    else:
                        unrealized_pnl = (entry_price - current_price) * abs(size)
                else:
                    unrealized_pnl = 0.0

                display_size = abs(size) if is_long else -abs(size)
                return symbol, True, display_size, symbol, entry_price, unrealized_pnl, is_long

        return symbol, False, 0, "", 0, 0, False

    def _find_position(self, symbol: str) -> Optional[Dict]:
        """Find a position by symbol."""
        for pos in self.state.positions:
            if pos['symbol'] == symbol:
                return pos
        return None

    def _remove_position(self, symbol: str):
        """Remove a position by symbol."""
        self.state.positions = [p for p in self.state.positions if p['symbol'] != symbol]

    # =========================================================================
    # Order execution (simulated)
    # =========================================================================

    def _generate_order_id(self) -> int:
        order_id = self.state.next_order_id
        self.state.next_order_id += 1
        return order_id

    def _execute_fill(self, symbol: str, side: str, quantity: float, fill_price: float, is_maker: bool = True):
        """Execute a fill: update position and balance."""
        fee_rate = self.maker_fee_rate if is_maker else self.taker_fee_rate
        notional = quantity * fill_price
        fee = notional * fee_rate

        existing = self._find_position(symbol)

        if existing:
            existing_is_long = existing['direction'] == 'Long'
            existing_qty = existing['quantity']

            # Same direction → add to position
            if (side == 'buy' and existing_is_long) or (side == 'sell' and not existing_is_long):
                new_qty = existing_qty + quantity
                # Weighted average entry price
                existing['open_price'] = (
                    (existing['open_price'] * existing_qty + fill_price * quantity) / new_qty
                )
                existing['quantity'] = new_qty
                realized_pnl = 0.0

            # Opposite direction → reduce or flip
            else:
                if quantity >= existing_qty:
                    # Close (and possibly flip)
                    if existing_is_long:
                        realized_pnl = (fill_price - existing['open_price']) * existing_qty
                    else:
                        realized_pnl = (existing['open_price'] - fill_price) * existing_qty

                    remaining = quantity - existing_qty
                    self._remove_position(symbol)

                    # Flip to opposite direction
                    if remaining > 0:
                        new_direction = 'Long' if side == 'buy' else 'Short'
                        self.state.positions.append({
                            'symbol': symbol,
                            'direction': new_direction,
                            'quantity': remaining,
                            'open_price': fill_price,
                            'timestamp': time.time(),
                        })
                else:
                    # Partial close
                    if existing_is_long:
                        realized_pnl = (fill_price - existing['open_price']) * quantity
                    else:
                        realized_pnl = (existing['open_price'] - fill_price) * quantity

                    existing['quantity'] = existing_qty - quantity
        else:
            # New position
            direction = 'Long' if side == 'buy' else 'Short'
            self.state.positions.append({
                'symbol': symbol,
                'direction': direction,
                'quantity': quantity,
                'open_price': fill_price,
                'timestamp': time.time(),
            })
            realized_pnl = 0.0

        # Update balance
        self.state.balance += realized_pnl - fee

        # Record trade
        self.state.trade_history.append({
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': fill_price,
            'fee': fee,
            'pnl': realized_pnl,
            'balance_after': self.state.balance,
            'timestamp': time.time(),
        })

        self._save_state()

        fee_type = "maker" if is_maker else "taker"
        print(f"[PAPER] {'BUY' if side == 'buy' else 'SELL'} {quantity:.8f} {symbol} @ ${fill_price:.2f} | Fee: ${fee:.4f} ({fee_type}) | P&L: ${realized_pnl:+.4f}")

        return realized_pnl

    def _check_limit_orders(self, symbol: str = None):
        """Check if any limit orders should be filled based on current prices."""
        filled_orders = []
        for order in self.state.open_orders:
            if order['status'] != 'open':
                continue
            if symbol and order['symbol'] != symbol:
                continue

            bid, ask = self.get_bid_ask(order['symbol'])
            if not bid or not ask:
                continue

            # Resting limit orders fill when the opposite side reaches
            # the order price.  These are always maker fills because
            # spread-crossing was already handled at placement time
            # (see buy_limit / sell_limit).
            should_fill = False
            if order['side'] == 'buy' and order['price'] >= ask:
                should_fill = True
            elif order['side'] == 'sell' and order['price'] <= bid:
                should_fill = True

            if should_fill:
                self._execute_fill(
                    order['symbol'], order['side'], order['quantity'],
                    order['price'], is_maker=True
                )
                order['status'] = 'filled'
                filled_orders.append(order['order_id'])

        # Clean up filled orders
        self.state.open_orders = [o for o in self.state.open_orders if o['status'] == 'open']
        self._save_state()

        return filled_orders

    # =========================================================================
    # Trading functions (same interface as HibachiAPI)
    # =========================================================================

    def buy_limit(self, symbol: str, quantity: float, price: float, leverage: int = 1):
        """Place a buy limit order (simulated)."""
        order_id = self._generate_order_id()
        nonce = int(time.time() * 1000)

        # Check if order crosses the spread (immediate fill)
        bid, ask = self.get_bid_ask(symbol)
        if ask and price >= ask:
            # Taker fill - crosses the spread
            self._execute_fill(symbol, 'buy', quantity, price, is_maker=False)
            return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'filled'}

        # Otherwise, resting limit order
        self.state.open_orders.append({
            'order_id': order_id,
            'symbol': symbol,
            'side': 'buy',
            'order_type': 'limit',
            'quantity': quantity,
            'price': price,
            'status': 'open',
            'timestamp': time.time(),
        })
        self._save_state()
        print(f"[PAPER] Limit BUY order placed: {quantity:.8f} {symbol} @ ${price:.2f}")
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'open'}

    def sell_limit(self, symbol: str, quantity: float, price: float, leverage: int = 1):
        """Place a sell limit order (simulated)."""
        order_id = self._generate_order_id()
        nonce = int(time.time() * 1000)

        # Check if order crosses the spread (immediate fill)
        bid, ask = self.get_bid_ask(symbol)
        if bid and price <= bid:
            # Taker fill
            self._execute_fill(symbol, 'sell', quantity, price, is_maker=False)
            return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'filled'}

        # Resting limit order
        self.state.open_orders.append({
            'order_id': order_id,
            'symbol': symbol,
            'side': 'sell',
            'order_type': 'limit',
            'quantity': quantity,
            'price': price,
            'status': 'open',
            'timestamp': time.time(),
        })
        self._save_state()
        print(f"[PAPER] Limit SELL order placed: {quantity:.8f} {symbol} @ ${price:.2f}")
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'open'}

    def buy_market(self, symbol: str, quantity: float, leverage: int = 1):
        """Place a buy market order (simulated) - fills at ask."""
        order_id = self._generate_order_id()
        nonce = int(time.time() * 1000)

        bid, ask = self.get_bid_ask(symbol)
        if not ask:
            raise Exception(f"Cannot get ask price for {symbol}")

        self._execute_fill(symbol, 'buy', quantity, ask, is_maker=False)
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'filled'}

    def sell_market(self, symbol: str, quantity: float, leverage: int = 1):
        """Place a sell market order (simulated) - fills at bid."""
        order_id = self._generate_order_id()
        nonce = int(time.time() * 1000)

        bid, ask = self.get_bid_ask(symbol)
        if not bid:
            raise Exception(f"Cannot get bid price for {symbol}")

        self._execute_fill(symbol, 'sell', quantity, bid, is_maker=False)
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id, 'status': 'filled'}

    def cancel_order(self, symbol: str, order_id: str):
        """Cancel an order."""
        order_id_int = int(order_id)
        for order in self.state.open_orders:
            if order['order_id'] == order_id_int:
                order['status'] = 'cancelled'
                print(f"[PAPER] Order {order_id} cancelled")
                break
        self.state.open_orders = [o for o in self.state.open_orders if o['status'] == 'open']
        self._save_state()
        return True

    def cancel_all_orders_market(self, symbol: str):
        """Cancel all orders for a market."""
        count = len([o for o in self.state.open_orders if o['symbol'] == symbol])
        self.state.open_orders = [o for o in self.state.open_orders if o['symbol'] != symbol]
        self._save_state()
        if count > 0:
            print(f"[PAPER] Cancelled {count} orders for {symbol}")
        return True

    def get_open_orders(self, symbol: str = None):
        """Get open orders."""
        if symbol:
            return [o for o in self.state.open_orders if o['symbol'] == symbol and o['status'] == 'open']
        return [o for o in self.state.open_orders if o['status'] == 'open']

    def get_order_status(self, order_id: str):
        """Get order status."""
        order_id_int = int(order_id)
        for order in self.state.open_orders:
            if order['order_id'] == order_id_int:
                return order
        # Check trade history
        for trade in self.state.trade_history:
            if trade.get('order_id') == order_id_int:
                return {'status': 'filled', **trade}
        return {'status': 'not_found'}

    def usd_to_asset_size(self, symbol: str, usd_value: float):
        """Convert USD value to asset size using real prices."""
        return self.market_client.usd_to_asset_size(symbol, usd_value)

    # =========================================================================
    # Additional functions (from Moon Dev video)
    # =========================================================================

    def get_account_info(self):
        """Get paper trading account info."""
        # Update unrealized P&L for all positions
        total_unrealized = 0.0
        total_notional = 0.0
        for pos in self.state.positions:
            bid, ask = self.get_bid_ask(pos['symbol'])
            if bid and ask:
                current_price = (bid + ask) / 2
                qty = pos['quantity']
                if pos['direction'] == 'Long':
                    pos_pnl = (current_price - pos['open_price']) * qty
                else:
                    pos_pnl = (pos['open_price'] - current_price) * qty
                total_unrealized += pos_pnl
                total_notional += current_price * qty

        return {
            'mode': 'paper',
            'balance': self.state.balance,
            'initial_balance': self.state.initial_balance,
            'total_pnl': self.state.balance - self.state.initial_balance + total_unrealized,
            'unrealized_pnl': total_unrealized,
            'realized_pnl': self.state.balance - self.state.initial_balance,
            'total_position_notional': total_notional,
            'positions': self.state.positions,
            'num_trades': len(self.state.trade_history),
        }

    def get_market_leverage(self, symbol: str):
        """Get max leverage for a market from exchange info."""
        return self.market_client.get_market_leverage(symbol)

    def get_exchange_info(self):
        """Get exchange info (real data)."""
        return self.market_client.get_exchange_info()

    def get_prices(self, symbol: str):
        """Get full price info (real data)."""
        return self.market_client.get_prices(symbol)

    def get_klines(self, symbol: str, interval: str = '1h'):
        """Get candlestick data (real data)."""
        return self.market_client.get_klines(symbol, interval)

    def get_stats(self, symbol: str):
        """Get 24h stats (real data)."""
        return self.market_client.get_stats(symbol)

    def get_available_markets(self):
        """Get list of all available trading pairs."""
        return self.market_client.get_available_markets()

    def get_trade_history(self, limit: int = 50):
        """Get paper trade history."""
        return self.state.trade_history[-limit:]

    def get_performance_summary(self):
        """Get performance summary of paper trading."""
        trades = self.state.trade_history
        if not trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'total_fees': 0,
                'balance': self.state.balance,
                'initial_balance': self.state.initial_balance,
                'return_pct': 0,
            }

        winning = [t for t in trades if t.get('pnl', 0) > 0]
        losing = [t for t in trades if t.get('pnl', 0) < 0]
        total_pnl = sum(t.get('pnl', 0) for t in trades)
        total_fees = sum(t.get('fee', 0) for t in trades)

        return {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'win_rate': len(winning) / len(trades) * 100 if trades else 0,
            'total_pnl': total_pnl,
            'total_fees': total_fees,
            'net_pnl': total_pnl - total_fees,
            'balance': self.state.balance,
            'initial_balance': self.state.initial_balance,
            'return_pct': ((self.state.balance - self.state.initial_balance) / self.state.initial_balance) * 100,
        }

    def check_and_fill_orders(self, symbol: str = None):
        """Check if any pending limit orders should be filled. Call this in your bot loop."""
        return self._check_limit_orders(symbol)
