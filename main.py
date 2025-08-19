#!/usr/bin/env python3
"""
Hibachi Exchange Trading Bot
Built by Moon Dev

Simple trading bot with:
0 - Close position
1 - Buy (Long)
2 - Sell (Short)  
3 - P&L Monitor (auto close at TP/SL)
"""

import os
import sys
import time
from datetime import datetime
from dotenv import load_dotenv
from nice_funks import HibachiAPI

load_dotenv()

# Configuration
POSITION_SIZE_USD = 100  # Position size in USD (your margin)
LEVERAGE = 2             # Your desired leverage (2x = $200 position with $100 margin)
TAKE_PROFIT = .001        # Take profit at 2% gain
STOP_LOSS = -.001        # Stop loss at 1% loss
LOOP_SLEEP = 2           # Sleep between loops (seconds)
MAX_RETRIES = 100        # Max retries for orders

class TradingBot:
    def __init__(self):
        """Initialize the bot"""
        self.api = HibachiAPI()
        self.symbol = os.environ.get('HIBACHI_SYMBOL', 'BTC/USDT-P')
        
        print("=" * 50)
        print("🚀 Hibachi Trading Bot - Moon Dev")
        print("=" * 50)
        print(f"Symbol: {self.symbol}")
        print(f"Margin: ${POSITION_SIZE_USD}")
        print(f"Leverage: {LEVERAGE}x (Position Value: ${POSITION_SIZE_USD * LEVERAGE})")
        print(f"TP: {TAKE_PROFIT}% | SL: {STOP_LOSS}%")
        print("=" * 50)
    
    def get_position_info(self):
        """Get current position information"""
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
        """Close current position - keep looping until closed"""
        print("\n🔄 CLOSING POSITION...")
        
        position = self.get_position_info()
        if not position['has_position']:
            print("❌ No position to close")
            return False
        
        print(f"Closing {position['type'].upper()} position...")
        
        for retry in range(MAX_RETRIES):
            # Check if position still exists
            position = self.get_position_info()
            if not position['has_position']:
                print("✅ Position closed successfully!")
                return True
            
            # Cancel all existing orders
            self.api.cancel_all_orders_market(self.symbol)
            
            # Get current prices
            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"⚠️ Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue
            
            # Place aggressive closing order
            if position['type'] == 'long':
                # Sell to close - hit the bid aggressively
                price = bid * 0.995
                print(f"📉 Selling {position['size']:.8f} @ ${price:.2f} (bid: ${bid:.2f})")
                self.api.sell_limit(self.symbol, position['size'], price, LEVERAGE)
            else:
                # Buy to close - hit the ask aggressively
                price = ask * 1.005
                print(f"📈 Buying {position['size']:.8f} @ ${price:.2f} (ask: ${ask:.2f})")
                self.api.buy_limit(self.symbol, position['size'], price, LEVERAGE)
            
            print(f"⏳ Retry {retry + 1}/{MAX_RETRIES}: Waiting for close...")
            time.sleep(LOOP_SLEEP)
        
        print("❌ Failed to close position after max retries")
        return False
    
    def open_long(self):
        """Open long position - keep looping until filled"""
        print("\n📈 OPENING LONG POSITION...")
        
        # Check if we already have a position
        position = self.get_position_info()
        if position['has_position']:
            print(f"❌ Already have a {position['type']} position")
            return False
        
        # Calculate position size with YOUR leverage
        target_value = POSITION_SIZE_USD * LEVERAGE  # e.g., $100 * 2 = $200 position
        print(f"💰 Opening ${target_value:.2f} position with {LEVERAGE}x leverage (${POSITION_SIZE_USD} margin)")
        
        for retry in range(MAX_RETRIES):
            # IMPORTANT: Check position FIRST before placing orders
            position = self.get_position_info()
            if position['has_position']:
                print(f"✅ Long position opened at ${position['entry_price']:.2f}")
                print(f"   Size: {position['size']:.8f} BTC")
                print(f"   Value: ${position['size'] * position['entry_price']:.2f}")
                return True
            
            # Cancel all existing orders
            self.api.cancel_all_orders_market(self.symbol)
            
            # Get current prices
            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"⚠️ Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue
            
            # Calculate size based on target value
            size = self.api.usd_to_asset_size(self.symbol, target_value)
            
            # Place order at bid (maker) but move up if needed
            price = bid * (1 + retry * 0.0001)  # Increase price slightly each retry
            
            print(f"📊 Buying {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")
            
            try:
                self.api.buy_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                if "Invalid signature" in str(e):
                    print(f"⚠️ Signature error, retrying...")
                    time.sleep(1)
                    continue
                else:
                    print(f"⚠️ Order error: {e}")
            
            print(f"⏳ Retry {retry + 1}/{MAX_RETRIES}: Waiting for fill...")
            time.sleep(LOOP_SLEEP)
        
        print("❌ Failed to open long position after max retries")
        return False
    
    def open_short(self):
        """Open short position - keep looping until filled"""
        print("\n📉 OPENING SHORT POSITION...")
        
        # Check if we already have a position
        position = self.get_position_info()
        if position['has_position']:
            print(f"❌ Already have a {position['type']} position")
            return False
        
        # Calculate position size with YOUR leverage
        target_value = POSITION_SIZE_USD * LEVERAGE  # e.g., $100 * 2 = $200 position
        print(f"💰 Opening ${target_value:.2f} position with {LEVERAGE}x leverage (${POSITION_SIZE_USD} margin)")
        
        for retry in range(MAX_RETRIES):
            # IMPORTANT: Check position FIRST before placing orders
            position = self.get_position_info()
            if position['has_position']:
                print(f"✅ Short position opened at ${position['entry_price']:.2f}")
                print(f"   Size: {position['size']:.8f} BTC")
                print(f"   Value: ${abs(position['size']) * position['entry_price']:.2f}")
                return True
            
            # Cancel all existing orders
            self.api.cancel_all_orders_market(self.symbol)
            
            # Get current prices
            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                print(f"⚠️ Retry {retry + 1}: Failed to get prices")
                time.sleep(LOOP_SLEEP)
                continue
            
            # Calculate size based on target value
            size = self.api.usd_to_asset_size(self.symbol, target_value)
            
            # Place order at ask (maker) but move down if needed
            price = ask * (1 - retry * 0.0001)  # Decrease price slightly each retry
            
            print(f"📊 Selling {size:.8f} @ ${price:.2f} (bid: ${bid:.2f}, ask: ${ask:.2f})")
            
            try:
                self.api.sell_limit(self.symbol, size, price, LEVERAGE)
            except Exception as e:
                if "Invalid signature" in str(e):
                    print(f"⚠️ Signature error, retrying...")
                    time.sleep(1)
                    continue
                else:
                    print(f"⚠️ Order error: {e}")
            
            print(f"⏳ Retry {retry + 1}/{MAX_RETRIES}: Waiting for fill...")
            time.sleep(LOOP_SLEEP)
        
        print("❌ Failed to open short position after max retries")
        return False
    
    def monitor_pnl(self):
        """Monitor P&L and auto-close at TP/SL - keep looping"""
        print("\n📊 P&L MONITOR ACTIVE")
        print(f"Take Profit: {TAKE_PROFIT}% | Stop Loss: {STOP_LOSS}%")
        print("Press Ctrl+C to stop monitoring\n")
        
        # Track if we've seen a position yet
        waiting_for_position = True
        
        while True:
            position = self.get_position_info()
            
            if not position['has_position']:
                if waiting_for_position:
                    print("\r⏳ Waiting for position... (monitoring for manual entries)", end="", flush=True)
                else:
                    # We had a position but it's gone now (was closed)
                    print("\n✅ Position closed")
                    break
                time.sleep(LOOP_SLEEP)
                continue
            
            # We have a position now
            if waiting_for_position:
                print(f"\n🎯 Position detected! Monitoring {position['type'].upper()} position")
                waiting_for_position = False
            
            # Get current price
            bid, ask = self.api.get_bid_ask(self.symbol)
            if not bid or not ask:
                time.sleep(LOOP_SLEEP)
                continue
            
            current_price = (bid + ask) / 2
            
            # Calculate P&L in USD and percentage
            position_value = position['size'] * position['entry_price']
            current_value = position['size'] * current_price
            
            if position['type'] == 'long':
                pnl_usd = current_value - position_value
                price_move_percent = ((current_price - position['entry_price']) / position['entry_price']) * 100
            else:
                pnl_usd = position_value - current_value
                price_move_percent = ((position['entry_price'] - current_price) / position['entry_price']) * 100
            
            # P&L percentage on margin (what you actually care about)
            margin = POSITION_SIZE_USD  # Your actual money at risk
            pnl_percent = (pnl_usd / margin) * 100 if margin > 0 else 0
            
            # Display status with both USD and percentage
            emoji = "🟢" if pnl_usd >= 0 else "🔴"
            print(f"\r{emoji} {position['type'].upper()} | Entry: ${position['entry_price']:.2f} | Current: ${current_price:.2f} | P&L: ${pnl_usd:+.2f} ({pnl_percent:+.2f}% on ${margin} margin)", end="", flush=True)
            
            # Check TP/SL
            if pnl_percent >= TAKE_PROFIT:
                print(f"\n\n💰 TAKE PROFIT HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                # Continue monitoring in case user opens another position
                waiting_for_position = True
                print("\n⏳ Continuing to monitor for new positions...")
            elif pnl_percent <= STOP_LOSS:
                print(f"\n\n🛑 STOP LOSS HIT! ({pnl_percent:.2f}%)")
                self.close_position()
                # Continue monitoring in case user opens another position
                waiting_for_position = True
                print("\n⏳ Continuing to monitor for new positions...")
            
            time.sleep(LOOP_SLEEP)
    
    def run(self):
        """Main loop"""
        while True:
            # Get current position
            position = self.get_position_info()
            
            print("\n" + "=" * 50)
            if position['has_position']:
                # Get current P&L
                bid, ask = self.api.get_bid_ask(self.symbol)
                if bid and ask:
                    current_price = (bid + ask) / 2
                    position_value = position['size'] * position['entry_price']
                    current_value = position['size'] * current_price
                    
                    if position['type'] == 'long':
                        pnl_usd = current_value - position_value
                    else:
                        pnl_usd = position_value - current_value
                    
                    # P&L percentage on your margin
                    margin = POSITION_SIZE_USD
                    pnl_percent = (pnl_usd / margin) * 100 if margin > 0 else 0
                    
                    emoji = "🟢" if pnl_usd >= 0 else "🔴"
                    print(f"{emoji} {position['type'].upper()} Position")
                    print(f"Entry: ${position['entry_price']:.2f} | Current: ${current_price:.2f}")
                    print(f"Position Value: ${position_value:.2f} (${margin} margin @ {LEVERAGE}x)")
                    print(f"P&L: ${pnl_usd:+.2f} ({pnl_percent:+.2f}%)")
            else:
                print("📊 No Position")
            
            print("-" * 50)
            print("[0] Close Position" + (" ✅" if position['has_position'] else " (no position)"))
            print("[1] Buy (Long)" + (" ⚠️ position exists" if position['has_position'] else ""))
            print("[2] Sell (Short)" + (" ⚠️ position exists" if position['has_position'] else ""))
            print("[3] P&L Monitor (Auto TP/SL)" + (" ✅" if position['has_position'] else " - monitors manual entries too"))
            print("[Q] Quit")
            print("=" * 50)
            
            choice = input("Choice: ").strip().upper()
            
            if choice == '0':
                if position['has_position']:
                    self.close_position()
                else:
                    print("❌ No position to close")
            elif choice == '1':
                if position['has_position']:
                    print("⚠️ Already have a position. Close it first.")
                else:
                    if self.open_long():
                        # Automatically start P&L monitoring after successful entry
                        print("\n🎯 Position opened! Starting P&L monitor...")
                        time.sleep(1)
                        try:
                            self.monitor_pnl()
                        except KeyboardInterrupt:
                            print("\n\nMonitor stopped")
            elif choice == '2':
                if position['has_position']:
                    print("⚠️ Already have a position. Close it first.")
                else:
                    if self.open_short():
                        # Automatically start P&L monitoring after successful entry
                        print("\n🎯 Position opened! Starting P&L monitor...")
                        time.sleep(1)
                        try:
                            self.monitor_pnl()
                        except KeyboardInterrupt:
                            print("\n\nMonitor stopped")
            elif choice == '3':
                # P&L Monitor can always run - it will check for positions
                try:
                    self.monitor_pnl()
                except KeyboardInterrupt:
                    print("\n\nMonitor stopped")
            elif choice == 'Q':
                # Close any open position before quitting
                if position['has_position']:
                    print("\nClosing position before exit...")
                    self.close_position()
                print("\n👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice")

if __name__ == "__main__":
    try:
        bot = TradingBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Bot stopped")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        sys.exit(1)