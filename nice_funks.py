import os
import time
import logging
from decimal import Decimal
from typing import Optional, Tuple, Dict, Any
from hibachi_xyz import HibachiApiClient, Side
from hibachi_xyz.types import OrderFlags
from dotenv import load_dotenv

load_dotenv()

class HibachiAPI:
    """
    Hibachi Exchange API wrapper providing simplified trading functions
    """
    
    def __init__(self):
        self.client = HibachiApiClient(
            api_key=os.environ.get('HIBACHI_API_KEY'),
            account_id=os.environ.get('HIBACHI_ACCOUNT_ID'),
            private_key=os.environ.get('HIBACHI_PRIVATE_KEY')
        )
        self.logger = logging.getLogger(__name__)
    
    def test_connection(self):
        """Test the API connection"""
        account_info = self.client.get_account_info()
        return account_info
    
    def get_balances(self):
        """Get account balances"""
        account_info = self.client.get_account_info()
        if hasattr(account_info, 'assets'):
            return account_info.assets
        return []
    
    def get_bid_ask(self, symbol: str):
        """Get current bid and ask prices"""
        prices = self.client.get_prices(symbol)
        if prices:
            bid = float(prices.bidPrice)
            ask = float(prices.askPrice)
            return bid, ask
        return None, None
    
    def get_orderbook_levels(self, symbol: str, levels: int = 5):
        """Get orderbook with specified depth"""
        orderbook = self.client.get_orderbook(symbol, depth=levels, granularity='0.1')
        if orderbook and hasattr(orderbook, 'bid') and hasattr(orderbook, 'ask'):
            formatted_orderbook = {
                'bids': [[level.price, level.quantity] for level in orderbook.bid] if orderbook.bid else [],
                'asks': [[level.price, level.quantity] for level in orderbook.ask] if orderbook.ask else []
            }
            return formatted_orderbook
        return {'bids': [], 'asks': []}
    
    def get_position(self, symbol: str):
        """Get position information for a symbol"""
        try:
            # Get account info which includes positions
            account_info = self.client.get_account_info()
            
            # Check if there are any positions
            if hasattr(account_info, 'positions') and account_info.positions:
                # Look for our symbol in the positions
                for pos in account_info.positions:
                    # The actual field names based on test output:
                    # 'direction', 'quantity', 'openPrice', 'symbol', 'unrealizedTradingPnl'
                    if hasattr(pos, 'symbol') and pos.symbol == symbol:
                        # Extract position details using CORRECT field names
                        size = float(pos.quantity) if hasattr(pos, 'quantity') else 0
                        entry_price = float(pos.openPrice) if hasattr(pos, 'openPrice') else 0
                        unrealized_pnl = float(pos.unrealizedTradingPnl) if hasattr(pos, 'unrealizedTradingPnl') else 0
                        
                        # Determine if long or short based on direction field
                        is_long = pos.direction == 'Long' if hasattr(pos, 'direction') else (size > 0)
                        in_position = abs(size) > 0
                        
                        # For shorts, size should be negative
                        if not is_long and size > 0:
                            size = -size
                        
                        return symbol, in_position, size, symbol, entry_price, unrealized_pnl, is_long
            
            # No position found
            return symbol, False, 0, "", 0, 0, False
                
        except Exception as e:
            print(f"Error getting position: {e}")
            return symbol, False, 0, "", 0, 0, False
    
    def buy_limit(self, symbol: str, quantity: float, price: float, leverage: int = 1):
        """Place a buy limit order"""
        # Keep quantity as a simple float - the API handles it correctly
        nonce, order_id = self.client.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=Side.BUY,
            max_fees_percent=0.1
        )
        
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id}
    
    def sell_limit(self, symbol: str, quantity: float, price: float, leverage: int = 1):
        """Place a sell limit order"""
        # Keep quantity as a simple float - the API handles it correctly
        nonce, order_id = self.client.place_limit_order(
            symbol=symbol,
            quantity=quantity,
            price=price,
            side=Side.SELL,
            max_fees_percent=0.1
        )
        
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id}
    
    def buy_market(self, symbol: str, quantity: float, leverage: int = 1):
        """Place a buy market order"""
        nonce, order_id = self.client.place_market_order(
            symbol=symbol,
            quantity=quantity,
            side=Side.BUY,
            max_fees_percent=0.1
        )
        
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id}
    
    def sell_market(self, symbol: str, quantity: float, leverage: int = 1):
        """Place a sell market order"""
        nonce, order_id = self.client.place_market_order(
            symbol=symbol,
            quantity=quantity,
            side=Side.SELL,
            max_fees_percent=0.1
        )
        
        return {'nonce': nonce, 'id': order_id, 'orderId': order_id}
    
    def cancel_order(self, symbol: str, order_id: str):
        """Cancel an order"""
        result = self.client.cancel_order(order_id)
        return result
    
    def cancel_all_orders_market(self, symbol: str):
        """Cancel all orders for a market"""
        self.client.cancel_all_orders()
        return True
    
    def get_open_orders(self, symbol: str = None):
        """Get open orders"""
        return self.client.get_pending_orders()
    
    def get_order_status(self, order_id: str):
        """Get order status"""
        order = self.client.get_order_details(order_id)
        return order
    
    def usd_to_asset_size(self, symbol: str, usd_value: float):
        """Convert USD value to asset size"""
        bid, ask = self.get_bid_ask(symbol)
        if ask:
            return usd_value / ask
        return 0

    def pnl_close(self, symbol: str, take_profit_pct: float, stop_loss_pct: float,
                  position_size_usd: float, leverage: int = 1):
        """
        Check P&L and close position if TP/SL hit.
        Returns (should_close, pnl_percent, pnl_usd) tuple.
        """
        _, in_pos, size, _, entry, unrealized_pnl, is_long = self.get_position(symbol)
        if not in_pos:
            return False, 0, 0

        bid, ask = self.get_bid_ask(symbol)
        if not bid or not ask:
            return False, 0, 0

        current_price = (bid + ask) / 2
        position_value = abs(size) * entry
        current_value = abs(size) * current_price

        if is_long:
            pnl_usd = current_value - position_value
        else:
            pnl_usd = position_value - current_value

        margin = position_size_usd
        pnl_percent = (pnl_usd / margin) * 100 if margin > 0 else 0

        if pnl_percent >= take_profit_pct or pnl_percent <= stop_loss_pct:
            # Close with market order
            try:
                if is_long:
                    self.sell_market(symbol, abs(size), leverage)
                else:
                    self.buy_market(symbol, abs(size), leverage)
                return True, pnl_percent, pnl_usd
            except Exception as e:
                print(f"Error closing position: {e}")

        return False, pnl_percent, pnl_usd

    def get_market_leverage(self, symbol: str):
        """Get maximum leverage for a market based on initial margin rate."""
        try:
            exch_info = self.client.get_exchange_info()
            if hasattr(exch_info, 'futureContracts'):
                for contract in exch_info.futureContracts:
                    if hasattr(contract, 'symbol') and contract.symbol == symbol:
                        margin_rate = float(contract.initialMarginRate)
                        if margin_rate > 0:
                            return int(1 / margin_rate)
            return 1
        except Exception as e:
            print(f"Error getting leverage: {e}")
            return 1

    def get_max_position_value(self, symbol: str):
        """Get maximum position value for the account based on balance and leverage."""
        try:
            account_info = self.client.get_account_info()
            balance = float(account_info.balance) if hasattr(account_info, 'balance') else 0
            max_leverage = self.get_market_leverage(symbol)
            return balance * max_leverage
        except Exception as e:
            print(f"Error getting max position value: {e}")
            return 0

    def get_account_info(self):
        """Get full account information."""
        return self.client.get_account_info()

    def get_exchange_info(self):
        """Get exchange information including fee config and contracts."""
        return self.client.get_exchange_info()

    def round_to_step_size(self, symbol: str, quantity: float):
        """Round quantity to the correct step size for a symbol."""
        try:
            exch_info = self.client.get_exchange_info()
            if hasattr(exch_info, 'futureContracts'):
                for contract in exch_info.futureContracts:
                    if hasattr(contract, 'symbol') and contract.symbol == symbol:
                        step_size = float(contract.stepSize)
                        if step_size > 0:
                            precision = len(str(step_size).rstrip('0').split('.')[-1])
                            return round(quantity - (quantity % step_size), precision)
            return quantity
        except Exception as e:
            print(f"Error rounding to step size: {e}")
            return quantity