#!/usr/bin/env python3
"""
Hibachi Exchange Paper Trading Bot
Uses real market data, simulates orders/positions locally.
No API keys needed - only public market data is used.

Usage:
    python paper_main.py
"""

import os
import sys
import time
from datetime import datetime
from paper_trading import PaperTradingAPI

# Configuration
PAPER_BALANCE = 10000       # Starting paper balance in USD
POSITION_SIZE_USD = 100     # Position size in USD (your margin)
LEVERAGE = 2                # Your desired leverage
TAKE_PROFIT = 2.0           # Take profit at 2% gain (on margin)
STOP_LOSS = -1.0            # Stop loss at 1% loss (on margin)
LOOP_SLEEP = 3              # Sleep between loops (seconds)
MAX_RETRIES = 60            # Max retries for orders
SYMBOL = os.environ.get('HIBACHI_SYMBOL', 'BTC/USDT-P')


class PaperTradingBot:
    def __init__(self):
        """Initialize the paper trading bot."""
        self.api = PaperTradingAPI(initial_balance=PAPER_BALANCE)
        self.symbol = SYMBOL

        print("=" * 60)
        print("  HIBACHI PAPER TRADING BOT")
        print("  Real market data | Simulated execution")
        print("=" * 60)
        print(f"  Symbol:     {self.symbol}")
        print(f"  Margin:     ${POSITION_SIZE_USD}")
        print(f"  Leverage:   {LEVERAGE}x (Position Value: ${POSITION_SIZE_USD * LEVERAGE})")
        print(f"  TP: {TAKE_PROFIT}% | SL: {STOP_LOSS}%")
        print(f"  Balance:    ${self.api.state.balance:.2f}")
        print("=" * 60)

        # Verify market data access
        bid, ask = self.api.get_bid_ask(self.symbol)
        if bid and ask:
            print(f"  Market:     Bid ${bid:.2f} | Ask ${ask:.2f}")
            print(f"  Spread:     ${ask - bid:.2f} ({(ask - bid) / bid * 100:.4f}%)")
        else:
            print("  WARNING: Cannot fetch market data. Check your connection.")
        print("=" * 60)

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
        """Close current position."""
        print("\n--- CLOSING POSITION ---")

        position = self.get_position_info()
        if not position['has_position']:
            print("No position to close")
            return False

        print(f"Closing {position['type'].upper()} position...")

        for retry in range(MAX_RETRIES):
            position = self.get_position_info()
            if not position['has_position']:
                print("Position closed successfully!")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"  Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            if position['type'] == 'long':
                price = bid * 0.995
                print(f"  Selling {position['size']:.8f} @ ${price:.2f} (bid: ${bid:.2f})")
                self.api.sell_limit(self.symbol, position['size'], price, LEVERAGE)
            else:
                price = ask * 1.005
                print(f"  Buying {position['size']:.8f} @ ${price:.2f} (ask: ${ask:.2f})")
                self.api.buy_limit(self.symbol, position['size'], price, LEVERAGE)

            # Check for fills
            self.api.check_and_fill_orders(self.symbol)

            time.sleep(LOOP_SLEEP)

        print("Failed to close position after max retries")
        return False

    def open_long(self):
        """Open long position."""
        print("\n--- OPENING LONG POSITION ---")

        position = self.get_position_info()
        if position['has_position']:
            print(f"Already have a {position['type']} position")
            return False

        target_value = POSITION_SIZE_USD * LEVERAGE
        print(f"Opening ${target_value:.2f} position with {LEVERAGE}x leverage (${POSITION_SIZE_USD} margin)")

        for retry in range(MAX_RETRIES):
            position = self.get_position_info()
            if position['has_position']:
                print(f"Long position opened at ${position['entry_price']:.2f}")
                print(f"  Size: {position['size']:.8f}")
                print(f"  Value: ${position['size'] * position['entry_price']:.2f}")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"  Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            size = self.api.usd_to_asset_size(self.symbol, target_value)
            price = bid * (1 + retry * 0.0001)

            print(f"  Buying {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")

            try:
                self.api.buy_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                print(f"  Order error: {e}")

            self.api.check_and_fill_orders(self.symbol)
            time.sleep(LOOP_SLEEP)

        print("Failed to open long position after max retries")
        return False

    def open_short(self):
        """Open short position."""
        print("\n--- OPENING SHORT POSITION ---")

        position = self.get_position_info()
        if position['has_position']:
            print(f"Already have a {position['type']} position")
            return False

        target_value = POSITION_SIZE_USD * LEVERAGE
        print(f"Opening ${target_value:.2f} position with {LEVERAGE}x leverage (${POSITION_SIZE_USD} margin)")

        for retry in range(MAX_RETRIES):
            position = self.get_position_info()
            if position['has_position']:
                print(f"Short position opened at ${position['entry_price']:.2f}")
                print(f"  Size: {position['size']:.8f}")
                print(f"  Value: ${position['size'] * position['entry_price']:.2f}")
                return True

            self.api.cancel_all_orders_market(self.symbol)

            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"  Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue

            size = self.api.usd_to_asset_size(self.symbol, target_value)
            price = ask * (1 - retry * 0.0001)

            print(f"  Selling {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")

            try:
                self.api.sell_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                print(f"  Order error: {e}")

            self.api.check_and_fill_orders(self.symbol)
            time.sleep(LOOP_SLEEP)

        print("Failed to open short position after max retries")
        return False

    def monitor_pnl(self):
        """Monitor P&L and auto-close at TP/SL."""
        print(f"\n--- P&L MONITOR ACTIVE ---")
        print(f"Take Profit: {TAKE_PROFIT}% | Stop Loss: {STOP_LOSS}%")
        print("Press Ctrl+C to stop monitoring\n")

        waiting_for_position = True

        while True:
            # Check limit order fills
            self.api.check_and_fill_orders(self.symbol)

            position = self.get_position_info()

            if not position['has_position']:
                if waiting_for_position:
                    print("\r  Waiting for position...", end="", flush=True)
                else:
                    print("\n  Position closed")
                    break
                time.sleep(LOOP_SLEEP)
                continue

            if waiting_for_position:
                print(f"\n  Position detected! Monitoring {position['type'].upper()} position")
                waiting_for_position = False

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
            print(f"\r  [{indicator}] {position['type'].upper()} | Entry: ${position['entry_price']:.2f} | Now: ${current_price:.2f} | P&L: ${pnl_usd:+.2f} ({pnl_percent:+.2f}% on ${margin} margin) | Bal: ${self.api.state.balance:.2f}", end="", flush=True)

            if pnl_percent >= TAKE_PROFIT:
                print(f"\n\n  TAKE PROFIT HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                waiting_for_position = True
                print("\n  Continuing to monitor for new positions...")
            elif pnl_percent <= STOP_LOSS:
                print(f"\n\n  STOP LOSS HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                waiting_for_position = True
                print("\n  Continuing to monitor for new positions...")

            time.sleep(LOOP_SLEEP)

    def show_performance(self):
        """Show trading performance summary."""
        perf = self.api.get_performance_summary()
        print("\n" + "=" * 60)
        print("  PERFORMANCE SUMMARY")
        print("=" * 60)
        print(f"  Initial Balance:  ${perf['initial_balance']:.2f}")
        print(f"  Current Balance:  ${perf['balance']:.2f}")
        print(f"  Return:           {perf['return_pct']:+.2f}%")
        print(f"  Total Trades:     {perf['total_trades']}")
        if perf['total_trades'] > 0:
            print(f"  Win Rate:         {perf['win_rate']:.1f}%")
            print(f"  Total P&L:        ${perf['total_pnl']:+.2f}")
            print(f"  Total Fees:       ${perf['total_fees']:.2f}")
            print(f"  Net P&L:          ${perf.get('net_pnl', 0):+.2f}")
        print("=" * 60)

        # Show recent trades
        trades = self.api.get_trade_history(10)
        if trades:
            print("\n  Recent Trades:")
            print(f"  {'Time':<20} {'Side':<5} {'Qty':<12} {'Price':<12} {'P&L':<10} {'Fee':<8}")
            print("  " + "-" * 67)
            for t in reversed(trades):
                ts = datetime.fromtimestamp(t['timestamp']).strftime('%Y-%m-%d %H:%M')
                print(f"  {ts:<20} {t['side'].upper():<5} {t['quantity']:<12.8f} ${t['price']:<11.2f} ${t.get('pnl', 0):+<9.4f} ${t.get('fee', 0):<7.4f}")
        print()

    def show_markets(self):
        """Show available markets."""
        markets = self.api.get_available_markets()
        if not markets:
            print("  Failed to fetch markets")
            return

        print("\n" + "=" * 60)
        print("  AVAILABLE MARKETS")
        print("=" * 60)
        print(f"  {'Symbol':<16} {'Max Lev':<10} {'Min Size':<12} {'Status':<8}")
        print("  " + "-" * 46)
        for m in markets:
            if m['status'] == 'LIVE':
                print(f"  {m['symbol']:<16} {m['max_leverage']}x{'':<7} {m['min_order_size']:<12} {m['status']:<8}")
        print()

    def run(self):
        """Main loop."""
        while True:
            position = self.get_position_info()

            print("\n" + "=" * 60)
            print("  [PAPER TRADING MODE]")

            if position['has_position']:
                bid, ask = self.api.get_bid_ask(self.symbol)
                if bid and ask:
                    current_price = (bid + ask) / 2
                    position_value = position['size'] * position['entry_price']
                    current_value = position['size'] * current_price

                    if position['type'] == 'long':
                        pnl_usd = current_value - position_value
                    else:
                        pnl_usd = position_value - current_value

                    margin = POSITION_SIZE_USD
                    pnl_percent = (pnl_usd / margin) * 100 if margin > 0 else 0

                    indicator = "+" if pnl_usd >= 0 else ""
                    print(f"  {position['type'].upper()} Position")
                    print(f"  Entry: ${position['entry_price']:.2f} | Current: ${current_price:.2f}")
                    print(f"  Value: ${position_value:.2f} (${margin} margin @ {LEVERAGE}x)")
                    print(f"  P&L: ${pnl_usd:+.2f} ({pnl_percent:+.2f}%)")
            else:
                print("  No Position")

            print(f"  Balance: ${self.api.state.balance:.2f}")
            print("-" * 60)
            print("  [0] Close Position" + (" *" if position['has_position'] else " (no position)"))
            print("  [1] Buy (Long)" + (" -- position exists" if position['has_position'] else ""))
            print("  [2] Sell (Short)" + (" -- position exists" if position['has_position'] else ""))
            print("  [3] P&L Monitor (Auto TP/SL)" + (" *" if position['has_position'] else " - monitors for entries too"))
            print("  [4] Performance Summary")
            print("  [5] Available Markets")
            print("  [6] Reset Paper Balance")
            print("  [Q] Quit")
            print("=" * 60)

            choice = input("  Choice: ").strip().upper()

            if choice == '0':
                if position['has_position']:
                    self.close_position()
                else:
                    print("  No position to close")
            elif choice == '1':
                if position['has_position']:
                    print("  Already have a position. Close it first.")
                else:
                    if self.open_long():
                        print("\n  Position opened! Starting P&L monitor...")
                        time.sleep(1)
                        try:
                            self.monitor_pnl()
                        except KeyboardInterrupt:
                            print("\n\n  Monitor stopped")
            elif choice == '2':
                if position['has_position']:
                    print("  Already have a position. Close it first.")
                else:
                    if self.open_short():
                        print("\n  Position opened! Starting P&L monitor...")
                        time.sleep(1)
                        try:
                            self.monitor_pnl()
                        except KeyboardInterrupt:
                            print("\n\n  Monitor stopped")
            elif choice == '3':
                try:
                    self.monitor_pnl()
                except KeyboardInterrupt:
                    print("\n\n  Monitor stopped")
            elif choice == '4':
                self.show_performance()
            elif choice == '5':
                self.show_markets()
            elif choice == '6':
                confirm = input(f"  Reset balance to ${PAPER_BALANCE}? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.api.reset_state(PAPER_BALANCE)
            elif choice == 'Q':
                if position['has_position']:
                    close = input("  Close position before exit? (y/n): ").strip().lower()
                    if close == 'y':
                        self.close_position()
                self.show_performance()
                print("  Goodbye!")
                break
            else:
                print("  Invalid choice")


if __name__ == "__main__":
    try:
        bot = PaperTradingBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n\n  Bot stopped")
    except Exception as e:
        print(f"\n  Error: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
