#!/usr/bin/env python3
"""
Hibachi Exchange Paper Trading Bot
Uses real market data, simulates orders/positions locally.
No API keys needed - only public market data is used.

Runs in headless auto-trading mode (Docker compatible).
All configuration via environment variables.

Usage:
    python paper_main.py              # auto-trade mode (default)
    BOT_MODE=monitor python paper_main.py  # monitor-only mode
"""

import os
import sys
import signal
import time
import logging
from datetime import datetime
from paper_trading import PaperTradingAPI

# ---------------------------------------------------------------------------
# Configuration (all via environment variables for Docker)
# ---------------------------------------------------------------------------
PAPER_BALANCE = float(os.environ.get('PAPER_BALANCE', '10000'))
POSITION_SIZE_USD = float(os.environ.get('POSITION_SIZE_USD', '100'))
LEVERAGE = int(os.environ.get('LEVERAGE', '2'))
TAKE_PROFIT = float(os.environ.get('TAKE_PROFIT', '2.0'))
STOP_LOSS = float(os.environ.get('STOP_LOSS', '-1.0'))
LOOP_SLEEP = int(os.environ.get('LOOP_SLEEP', '3'))
MAX_RETRIES = int(os.environ.get('MAX_RETRIES', '60'))
SYMBOL = os.environ.get('HIBACHI_SYMBOL', 'BTC/USDT-P')

# Bot mode: "long", "short", "monitor", "alternate"
#   long      - open long, monitor P&L, close at TP/SL, repeat
#   short     - open short, monitor P&L, close at TP/SL, repeat
#   monitor   - just monitor existing position (no new entries)
#   alternate - alternate long/short after each close
BOT_MODE = os.environ.get('BOT_MODE', 'long').lower()

# How long to wait between trade cycles (seconds)
CYCLE_COOLDOWN = int(os.environ.get('CYCLE_COOLDOWN', '10'))

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


class PaperTradingBot:
    def __init__(self):
        """Initialize the paper trading bot."""
        self.api = PaperTradingAPI(initial_balance=PAPER_BALANCE)
        self.symbol = SYMBOL
        self.last_direction = None  # for alternate mode

        logger.info("=" * 60)
        logger.info("  HIBACHI PAPER TRADING BOT")
        logger.info("  Real market data | Simulated execution | Docker ready")
        logger.info("=" * 60)
        logger.info(f"  Symbol:     {self.symbol}")
        logger.info(f"  Mode:       {BOT_MODE}")
        logger.info(f"  Margin:     ${POSITION_SIZE_USD}")
        logger.info(f"  Leverage:   {LEVERAGE}x (Position Value: ${POSITION_SIZE_USD * LEVERAGE})")
        logger.info(f"  TP: {TAKE_PROFIT}% | SL: {STOP_LOSS}%")
        logger.info(f"  Balance:    ${self.api.state.balance:.2f}")
        logger.info("=" * 60)

        # Verify market data access
        bid, ask = self.api.get_bid_ask(self.symbol)
        if bid and ask:
            logger.info(f"  Market:     Bid ${bid:.2f} | Ask ${ask:.2f}")
            logger.info(f"  Spread:     ${ask - bid:.2f} ({(ask - bid) / bid * 100:.4f}%)")
        else:
            logger.warning("  Cannot fetch market data. Check your connection.")
        logger.info("=" * 60)

    def get_position_info(self):
        """Get current position information."""
        _, in_pos, size, _, entry, pnl, is_long = self.api.get_position(self.symbol)

        if in_pos and abs(size) > 0:
            return {
                'has_position': True,
                'type': 'long' if is_long else 'short',
                'size': abs(size),
                'entry_price': entry,
                'pnl': pnl
            }

        return {'has_position': False}

    def close_position(self):
        """Close current position using aggressive limit orders."""
        logger.info("CLOSING POSITION...")

        position = self.get_position_info()
        if not position['has_position']:
            logger.info("No position to close")
            return False

        logger.info(f"Closing {position['type'].upper()} | Size: {position['size']:.8f}")

        for retry in range(MAX_RETRIES):
            if shutdown_requested:
                return False

            position = self.get_position_info()
            if not position['has_position']:
                logger.info("Position closed successfully!")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                logger.warning(f"Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            if position['type'] == 'long':
                price = bid * 0.995
                logger.info(f"  Sell {position['size']:.8f} @ ${price:.2f} (bid: ${bid:.2f})")
                self.api.sell_limit(self.symbol, position['size'], price, LEVERAGE)
            else:
                price = ask * 1.005
                logger.info(f"  Buy {position['size']:.8f} @ ${price:.2f} (ask: ${ask:.2f})")
                self.api.buy_limit(self.symbol, position['size'], price, LEVERAGE)

            self.api.check_and_fill_orders(self.symbol)
            time.sleep(LOOP_SLEEP)

        logger.error("Failed to close position after max retries")
        return False

    def open_long(self):
        """Open long position using limit orders."""
        logger.info("OPENING LONG POSITION...")

        position = self.get_position_info()
        if position['has_position']:
            logger.warning(f"Already have a {position['type']} position")
            return False

        target_value = POSITION_SIZE_USD * LEVERAGE
        logger.info(f"Target: ${target_value:.2f} ({LEVERAGE}x on ${POSITION_SIZE_USD} margin)")

        for retry in range(MAX_RETRIES):
            if shutdown_requested:
                return False

            position = self.get_position_info()
            if position['has_position']:
                logger.info(f"Long opened @ ${position['entry_price']:.2f} | Size: {position['size']:.8f} | Value: ${position['size'] * position['entry_price']:.2f}")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                logger.warning(f"Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            size = self.api.usd_to_asset_size(self.symbol, target_value)
            price = bid * (1 + retry * 0.0001)

            logger.info(f"  Buy {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")

            try:
                self.api.buy_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                logger.error(f"  Order error: {e}")

            self.api.check_and_fill_orders(self.symbol)
            time.sleep(LOOP_SLEEP)

        logger.error("Failed to open long after max retries")
        return False

    def open_short(self):
        """Open short position using limit orders."""
        logger.info("OPENING SHORT POSITION...")

        position = self.get_position_info()
        if position['has_position']:
            logger.warning(f"Already have a {position['type']} position")
            return False

        target_value = POSITION_SIZE_USD * LEVERAGE
        logger.info(f"Target: ${target_value:.2f} ({LEVERAGE}x on ${POSITION_SIZE_USD} margin)")

        for retry in range(MAX_RETRIES):
            if shutdown_requested:
                return False

            position = self.get_position_info()
            if position['has_position']:
                logger.info(f"Short opened @ ${position['entry_price']:.2f} | Size: {position['size']:.8f} | Value: ${position['size'] * position['entry_price']:.2f}")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                logger.warning(f"Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            size = self.api.usd_to_asset_size(self.symbol, target_value)
            price = ask * (1 - retry * 0.0001)

            logger.info(f"  Sell {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")

            try:
                self.api.sell_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                logger.error(f"  Order error: {e}")

            self.api.check_and_fill_orders(self.symbol)
            time.sleep(LOOP_SLEEP)

        logger.error("Failed to open short after max retries")
        return False

    def monitor_pnl(self):
        """Monitor P&L and auto-close at TP/SL. Returns True if position was closed."""
        logger.info(f"P&L Monitor active | TP: {TAKE_PROFIT}% | SL: {STOP_LOSS}%")

        while not shutdown_requested:
            self.api.check_and_fill_orders(self.symbol)

            position = self.get_position_info()
            if not position['has_position']:
                logger.info("No position to monitor")
                return False

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                time.sleep(LOOP_SLEEP)
                continue

            current_price = (bid + ask) / 2
            position_value = position['size'] * position['entry_price']
            current_value = position['size'] * current_price

            if position['type'] == 'long':
                pnl_usd = current_value - position_value
            else:
                pnl_usd = position_value - current_value

            margin = POSITION_SIZE_USD
            pnl_percent = (pnl_usd / margin) * 100 if margin > 0 else 0

            indicator = "+" if pnl_usd >= 0 else "-"
            logger.info(
                f"[{indicator}] {position['type'].upper()} | "
                f"Entry: ${position['entry_price']:.2f} | Now: ${current_price:.2f} | "
                f"P&L: ${pnl_usd:+.2f} ({pnl_percent:+.2f}%) | "
                f"Bal: ${self.api.state.balance:.2f}"
            )

            if pnl_percent >= TAKE_PROFIT:
                logger.info(f"TAKE PROFIT HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                return True
            elif pnl_percent <= STOP_LOSS:
                logger.info(f"STOP LOSS HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                return True

            time.sleep(LOOP_SLEEP)

        return False

    def log_performance(self):
        """Log trading performance summary."""
        perf = self.api.get_performance_summary()
        logger.info("=" * 60)
        logger.info("PERFORMANCE SUMMARY")
        logger.info(f"  Initial:  ${perf['initial_balance']:.2f}")
        logger.info(f"  Current:  ${perf['balance']:.2f}")
        logger.info(f"  Return:   {perf['return_pct']:+.2f}%")
        logger.info(f"  Trades:   {perf['total_trades']}")
        if perf['total_trades'] > 0:
            logger.info(f"  Win Rate: {perf['win_rate']:.1f}%")
            logger.info(f"  P&L:      ${perf['total_pnl']:+.2f}")
            logger.info(f"  Fees:     ${perf['total_fees']:.2f}")
            logger.info(f"  Net:      ${perf.get('net_pnl', 0):+.2f}")
        logger.info("=" * 60)

    def _next_direction(self):
        """Determine the next trade direction based on BOT_MODE."""
        if BOT_MODE == 'long':
            return 'long'
        elif BOT_MODE == 'short':
            return 'short'
        elif BOT_MODE == 'alternate':
            if self.last_direction is None or self.last_direction == 'short':
                return 'long'
            return 'short'
        return None

    def run(self):
        """Main auto-trading loop (headless, Docker-friendly)."""
        cycle = 0

        while not shutdown_requested:
            cycle += 1
            logger.info(f"--- Cycle {cycle} ---")

            # Check existing position first
            position = self.get_position_info()

            if position['has_position']:
                logger.info(f"Existing {position['type'].upper()} position found. Monitoring...")
                closed = self.monitor_pnl()
                if closed:
                    self.log_performance()
                    if BOT_MODE == 'monitor':
                        logger.info("Monitor mode: exiting after close.")
                        break
                continue

            # No position - decide what to do
            if BOT_MODE == 'monitor':
                logger.info("Monitor mode: no position. Waiting...")
                time.sleep(LOOP_SLEEP * 3)
                continue

            direction = self._next_direction()
            if not direction:
                logger.warning(f"Unknown BOT_MODE: {BOT_MODE}")
                break

            # Open new position
            success = False
            if direction == 'long':
                success = self.open_long()
            elif direction == 'short':
                success = self.open_short()

            if success:
                self.last_direction = direction
                # Monitor the new position
                closed = self.monitor_pnl()
                if closed:
                    self.log_performance()
            else:
                logger.warning("Failed to open position. Cooling down...")

            if not shutdown_requested:
                logger.info(f"Cooldown: {CYCLE_COOLDOWN}s before next cycle")
                time.sleep(CYCLE_COOLDOWN)

        # Shutdown: close position if exists
        position = self.get_position_info()
        if position['has_position']:
            logger.info("Shutting down: closing open position...")
            self.close_position()

        self.log_performance()
        logger.info("Bot stopped.")


if __name__ == "__main__":
    try:
        bot = PaperTradingBot()
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
