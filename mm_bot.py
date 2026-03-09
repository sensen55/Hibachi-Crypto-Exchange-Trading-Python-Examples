#!/usr/bin/env python3
"""
Hibachi Exchange - Market Making Bot (Paper Trading)

A basic market making bot that:
  - Places bid/ask limit orders on both sides of the spread
  - Earns the spread when both sides fill
  - Manages inventory risk by skewing quotes away from accumulated position
  - Cancels and re-quotes when the market moves

All configuration via environment variables for Docker compatibility.

Usage:
    python mm_bot.py
    MM_LEVELS=3 MM_SPREAD_BPS=5 python mm_bot.py
"""

import os
import sys
import signal
import time
import logging
from paper_trading import PaperTradingAPI

# ---------------------------------------------------------------------------
# Configuration (environment variables)
# ---------------------------------------------------------------------------
PAPER_BALANCE = float(os.environ.get('PAPER_BALANCE', '10000'))
SYMBOL = os.environ.get('HIBACHI_SYMBOL', 'BTC/USDT-P')
LEVERAGE = int(os.environ.get('LEVERAGE', '1'))

# Market making parameters
# Spread: half-spread offset from mid price in basis points (1 bps = 0.01%)
MM_SPREAD_BPS = float(os.environ.get('MM_SPREAD_BPS', '5'))
# Order size in USD per level
MM_ORDER_SIZE_USD = float(os.environ.get('MM_ORDER_SIZE_USD', '50'))
# Number of order levels on each side
MM_LEVELS = int(os.environ.get('MM_LEVELS', '1'))
# Spacing between levels in basis points
MM_LEVEL_SPACING_BPS = float(os.environ.get('MM_LEVEL_SPACING_BPS', '3'))
# Max inventory in USD (absolute notional). When exceeded, stop quoting that side.
MM_MAX_INVENTORY_USD = float(os.environ.get('MM_MAX_INVENTORY_USD', '500'))
# Inventory skew factor: shift mid price by this many bps per 1% of max inventory used
MM_SKEW_BPS_PER_PCT = float(os.environ.get('MM_SKEW_BPS_PER_PCT', '0.5'))
# Re-quote interval in seconds
MM_REQUOTE_INTERVAL = float(os.environ.get('MM_REQUOTE_INTERVAL', '5'))
# Stale order threshold: cancel and re-quote if price moved more than this (bps)
MM_STALE_THRESHOLD_BPS = float(os.environ.get('MM_STALE_THRESHOLD_BPS', '10'))

# Logging
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# Graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    global shutdown_requested
    logger.info("Shutdown signal received. Closing gracefully...")
    shutdown_requested = True


signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


class MarketMakingBot:
    def __init__(self):
        self.api = PaperTradingAPI(initial_balance=PAPER_BALANCE)
        self.symbol = SYMBOL
        self.half_spread_bps = MM_SPREAD_BPS
        self.order_size_usd = MM_ORDER_SIZE_USD
        self.levels = MM_LEVELS
        self.level_spacing_bps = MM_LEVEL_SPACING_BPS
        self.max_inventory_usd = MM_MAX_INVENTORY_USD
        self.skew_bps_per_pct = MM_SKEW_BPS_PER_PCT
        self.requote_interval = MM_REQUOTE_INTERVAL
        self.stale_threshold_bps = MM_STALE_THRESHOLD_BPS

        # Track our placed orders: {order_id: {side, price, size, level}}
        self.active_orders = {}
        # Track the mid price when orders were last placed
        self.last_quoted_mid = None

        self._print_banner()

    def _print_banner(self):
        logger.info("=" * 60)
        logger.info("  HIBACHI MARKET MAKING BOT (Paper Trading)")
        logger.info("=" * 60)
        logger.info(f"  Symbol:         {self.symbol}")
        logger.info(f"  Balance:        ${self.api.state.balance:.2f}")
        logger.info(f"  Half-spread:    {self.half_spread_bps} bps")
        logger.info(f"  Order size:     ${self.order_size_usd} per level")
        logger.info(f"  Levels:         {self.levels} per side")
        if self.levels > 1:
            logger.info(f"  Level spacing:  {self.level_spacing_bps} bps")
        logger.info(f"  Max inventory:  ${self.max_inventory_usd}")
        logger.info(f"  Skew factor:    {self.skew_bps_per_pct} bps per 1% inventory")
        logger.info(f"  Re-quote every: {self.requote_interval}s")
        logger.info(f"  Stale threshold:{self.stale_threshold_bps} bps")
        logger.info(f"  Maker fee:      {self.api.maker_fee_rate * 100:.4f}%")
        logger.info(f"  Taker fee:      {self.api.taker_fee_rate * 100:.4f}%")

        bid, ask = self.api.get_bid_ask(self.symbol)
        if bid and ask:
            spread_bps = (ask - bid) / ((bid + ask) / 2) * 10000
            logger.info(f"  Market:         Bid ${bid:.2f} | Ask ${ask:.2f}")
            logger.info(f"  Market spread:  {spread_bps:.2f} bps")
        else:
            logger.warning("  Cannot fetch market data!")
        logger.info("=" * 60)

    # =========================================================================
    # Inventory management
    # =========================================================================

    def get_inventory(self):
        """
        Get current inventory (net position).
        Returns (direction, quantity, notional_usd, entry_price).
        direction: 'long', 'short', or 'flat'
        """
        _, in_pos, size, _, entry, pnl, is_long = self.api.get_position(self.symbol)
        if not in_pos or abs(size) == 0:
            return 'flat', 0.0, 0.0, 0.0

        qty = abs(size)
        notional = qty * entry
        direction = 'long' if is_long else 'short'
        return direction, qty, notional, entry

    def _inventory_skew_bps(self):
        """
        Calculate how much to shift the mid price based on inventory.
        When long: shift mid DOWN so sell orders are closer to market (easier to fill).
        When short: shift mid UP so buy orders are closer to market (easier to fill).
        """
        direction, _, notional, _ = self.get_inventory()
        if notional == 0:
            return 0.0

        # inventory_pct: how full is our inventory as % of max (capped at 100%)
        inventory_pct = min((notional / self.max_inventory_usd) * 100, 100.0)
        skew = inventory_pct * self.skew_bps_per_pct

        if direction == 'long':
            # We're long → shift mid DOWN to bring sell orders closer to market
            return -skew
        elif direction == 'short':
            # We're short → shift mid UP to bring buy orders closer to market
            return skew
        return 0.0

    def _should_quote_side(self, side):
        """Check if we should quote a given side based on inventory limits."""
        direction, _, notional, _ = self.get_inventory()

        if notional >= self.max_inventory_usd:
            # At max inventory - only allow reducing orders
            if direction == 'long' and side == 'buy':
                return False
            if direction == 'short' and side == 'sell':
                return False
        return True

    # =========================================================================
    # Order management
    # =========================================================================

    def cancel_all(self):
        """Cancel all our outstanding orders."""
        self.api.cancel_all_orders_market(self.symbol)
        self.active_orders.clear()

    def _is_stale(self, current_mid):
        """Check if our quotes are stale (market moved too far)."""
        if self.last_quoted_mid is None:
            return True
        move_bps = abs(current_mid - self.last_quoted_mid) / self.last_quoted_mid * 10000
        return move_bps >= self.stale_threshold_bps

    def place_quotes(self):
        """
        Place bid and ask limit orders around the mid price.
        Adjusts for inventory skew.
        """
        bid, ask = self.api.get_bid_ask(self.symbol)
        if not bid or not ask:
            logger.warning("Cannot get market prices, skipping quote cycle")
            return

        raw_mid = (bid + ask) / 2
        skew_bps = self._inventory_skew_bps()
        # Skewed mid: shift mid price based on inventory
        skewed_mid = raw_mid * (1 + skew_bps / 10000)

        # Cancel existing orders before placing new ones
        self.cancel_all()

        placed_count = 0

        for level in range(self.levels):
            # Offset for this level
            level_offset_bps = self.half_spread_bps + (level * self.level_spacing_bps)

            # Bid (buy) side
            if self._should_quote_side('buy'):
                bid_price = skewed_mid * (1 - level_offset_bps / 10000)
                bid_size = self.api.usd_to_asset_size(self.symbol, self.order_size_usd)
                if bid_size > 0:
                    result = self.api.buy_limit(self.symbol, bid_size, bid_price, LEVERAGE)
                    order_id = result.get('orderId')
                    if order_id:
                        self.active_orders[order_id] = {
                            'side': 'buy', 'price': bid_price,
                            'size': bid_size, 'level': level,
                        }
                        placed_count += 1

            # Ask (sell) side
            if self._should_quote_side('sell'):
                ask_price = skewed_mid * (1 + level_offset_bps / 10000)
                ask_size = self.api.usd_to_asset_size(self.symbol, self.order_size_usd)
                if ask_size > 0:
                    result = self.api.sell_limit(self.symbol, ask_size, ask_price, LEVERAGE)
                    order_id = result.get('orderId')
                    if order_id:
                        self.active_orders[order_id] = {
                            'side': 'sell', 'price': ask_price,
                            'size': ask_size, 'level': level,
                        }
                        placed_count += 1

        self.last_quoted_mid = raw_mid

        # Log summary
        direction, _, notional, _ = self.get_inventory()
        inv_str = f"{direction} ${notional:.2f}" if direction != 'flat' else "flat"
        skew_str = f"{skew_bps:+.2f} bps" if skew_bps != 0 else "none"

        logger.info(
            f"Quoted {placed_count} orders | "
            f"Mid: ${raw_mid:.2f} | Skew: {skew_str} | "
            f"Inventory: {inv_str}"
        )

    # =========================================================================
    # Main loop
    # =========================================================================

    def log_status(self):
        """Log current status."""
        direction, qty, notional, entry = self.get_inventory()
        bid, ask = self.api.get_bid_ask(self.symbol)
        balance = self.api.state.balance

        if direction != 'flat' and bid and ask:
            current_price = (bid + ask) / 2
            if direction == 'long':
                unrealized = (current_price - entry) * qty
            else:
                unrealized = (entry - current_price) * qty
            logger.info(
                f"[STATUS] Bal: ${balance:.2f} | "
                f"Pos: {direction} {qty:.8f} (${notional:.2f}) | "
                f"Entry: ${entry:.2f} | "
                f"uPnL: ${unrealized:+.2f} | "
                f"Orders: {len(self.active_orders)}"
            )
        else:
            logger.info(
                f"[STATUS] Bal: ${balance:.2f} | "
                f"Pos: flat | Orders: {len(self.active_orders)}"
            )

    def run(self):
        """Main market making loop."""
        logger.info("Starting market making loop...")
        cycle = 0

        while not shutdown_requested:
            cycle += 1

            try:
                # Check for fills on existing orders
                filled = self.api.check_and_fill_orders(self.symbol)
                if filled:
                    # Remove filled orders from our tracking
                    for oid in filled:
                        self.active_orders.pop(oid, None)
                    logger.info(f"Fills detected: {len(filled)} order(s) filled")

                # Get current market mid
                bid, ask = self.api.get_bid_ask(self.symbol)
                if not bid or not ask:
                    logger.warning("No market data, waiting...")
                    time.sleep(self.requote_interval)
                    continue

                current_mid = (bid + ask) / 2

                # Re-quote if stale or if fills occurred
                if self._is_stale(current_mid) or filled:
                    self.place_quotes()

                # Periodic status log (every 10 cycles)
                if cycle % 10 == 0:
                    self.log_status()

                # Performance summary every 100 cycles
                if cycle % 100 == 0:
                    self._log_performance()

            except Exception as e:
                logger.error(f"Error in MM loop: {e}")
                import traceback
                traceback.print_exc()
                # Cancel all orders on error to be safe
                self.cancel_all()

            time.sleep(self.requote_interval)

        # Shutdown
        logger.info("Shutting down market maker...")
        self.cancel_all()

        # Optionally close any remaining position
        direction, qty, notional, _ = self.get_inventory()
        if direction != 'flat':
            logger.info(f"Closing remaining {direction} position (${notional:.2f})...")
            if direction == 'long':
                self.api.sell_market(self.symbol, qty, LEVERAGE)
            else:
                self.api.buy_market(self.symbol, qty, LEVERAGE)

        self._log_performance()
        logger.info("Market maker stopped.")

    def _log_performance(self):
        """Log trading performance."""
        perf = self.api.get_performance_summary()
        logger.info("=" * 60)
        logger.info("  PERFORMANCE SUMMARY")
        logger.info(f"  Initial:   ${perf['initial_balance']:.2f}")
        logger.info(f"  Current:   ${perf['balance']:.2f}")
        logger.info(f"  Return:    {perf['return_pct']:+.2f}%")
        logger.info(f"  Trades:    {perf['total_trades']}")
        if perf['total_trades'] > 0:
            logger.info(f"  Win Rate:  {perf['win_rate']:.1f}%")
            logger.info(f"  Gross P&L: ${perf['total_pnl']:+.2f}")
            logger.info(f"  Fees:      ${perf['total_fees']:.2f}")
            logger.info(f"  Net P&L:   ${perf.get('net_pnl', 0):+.2f}")
        logger.info("=" * 60)


if __name__ == "__main__":
    try:
        bot = MarketMakingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
