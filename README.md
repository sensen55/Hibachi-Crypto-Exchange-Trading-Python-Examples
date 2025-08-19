# Hibachi Exchange Trading Bot 🚀

**Built by MoonDev** | [YouTube Channel](https://www.youtube.com/@moondevonyt)

A professional cryptocurrency trading bot for Hibachi Exchange with real-time price feeds, limit order execution, and automated P&L management.

## Features 🌟

- **Real-time Price Feeds** - Lightning-fast price updates for optimal entry/exit
- **Interactive Menu System** - Simple number-based controls for all trading operations
- **Smart Order Management** - Limit orders with automatic fill checking and size adjustment
- **P&L Monitoring** - Automated take profit and stop loss with real-time tracking
- **Position Management** - Long and short positions with precise entry/exit loops
- **Automated Flow** - After opening a position, automatically starts P&L monitoring
- **Manual Trade Support** - P&L monitor works with positions opened manually too
- **Up to 15x Leverage** - Control leverage through position size (see leverage notes below)

## Menu Options 📊

- **[0] Close Position** - Exit current position using limit orders
- **[1] Open Long** - Buy at bid price (maker order)
- **[2] Open Short** - Sell at ask price (maker order)  
- **[3] P&L Monitor** - Auto-close at take profit/stop loss
- **[Q] Quit** - Exit the bot

## Installation 📦

1. Clone this repository:
```bash
git clone https://github.com/yourusername/Hibachi-Crypto-Exchange-Trading-Python-Examples.git
cd Hibachi-Crypto-Exchange-Trading-Python-Examples
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up your environment variables:
```bash
cp .env.example .env
```

4. Edit `.env` with your Hibachi Exchange credentials

## Configuration ⚙️

### Environment Variables (.env)

```env
# Required - Get these from Hibachi Exchange
HIBACHI_API_KEY=your_api_key_here
HIBACHI_ACCOUNT_ID=your_account_id_here
HIBACHI_PRIVATE_KEY=your_private_key_here

# Optional - Defaults shown
HIBACHI_SYMBOL=BTC/USDT-P
```

### Bot Settings

Edit these constants at the top of `trading_bot.py`:

```python
POSITION_SIZE_USD = 100  # Position size in USD (will be leveraged)
TAKE_PROFIT = 2.0        # Take profit at 2% gain
STOP_LOSS = -1.0         # Stop loss at 1% loss
LOOP_SLEEP = 2           # Sleep between loops (seconds)
```

## Usage 🎮

Run the bot:
```bash
python trading_bot.py
```

### Test Scripts

Run these scripts to test various functionalities:

1. **Test API connection**:
```bash
python 0_test_keys.py
```

2. **Check account balances**:
```bash
python 1_get_balances.py
```

3. **Get current prices**:
```bash
python 2_get_prices.py
```

4. **Place a test order**:
```bash
python 3_place_order.py
```

### Trading Flow - Perfect for Manual Traders Going Automated! 🎯

1. **Entry**: Choose [1] for Long or [2] for Short
   - Places limit orders at bid (long) or ask (short)
   - Loops until filled
   - **Automatically flows into P&L monitoring after entry!**

2. **Automated Risk Management**: After position opens
   - P&L monitor starts automatically
   - Continuously tracks your position
   - Auto-closes at take profit (2% default)
   - Auto-closes at stop loss (-1% default)
   - Shows real-time P&L updates

3. **Manual Trading Support**: 
   - Open positions manually on the exchange
   - Run option [3] to monitor and auto-close them
   - Perfect for traders transitioning to automation!

**The Flow:** Enter → Auto-Monitor → Auto-Close at TP/SL → Back to Menu

## Files 📁

- `trading_bot.py` - Main bot with interactive menu
- `nice_funks.py` - Hibachi Exchange API wrapper
- `0_test_keys.py` - Test API connection
- `1_get_balances.py` - Get account balances
- `2_get_prices.py` - Get current market prices
- `3_place_order.py` - Place and manage orders
- `.env.example` - Environment variable template
- `requirements.txt` - Python dependencies

## Safety Features 🛡️

- Limit orders only (no market slippage)
- Position size validation
- Automatic order cancellation on errors
- Real-time position tracking
- Partial fill handling

## Important: How Hibachi Leverage Works 📈

**Hibachi has a unique leverage system that's different from other exchanges:**

### The Quirk:
- **There's NO leverage slider or setting on Hibachi**
- Your account automatically has up to 15x leverage available on BTC
- You control leverage by the position size you enter

### Example:
If you have $100 in your account:
- You can trade up to $1,500 worth of BTC (15x max)
- To trade with 2x leverage: Enter a $200 position
- To trade with 5x leverage: Enter a $500 position  
- To trade with 10x leverage: Enter a $1,000 position

### How This Bot Handles It:
```python
# Configuration at top of main.py
POSITION_SIZE_USD = 100  # Your margin (your actual money)
LEVERAGE = 2             # Your desired leverage

# The bot calculates: $100 × 2 = $200 position
```

So if you want different leverage, just change the `LEVERAGE` value:
- `LEVERAGE = 1` → $100 position (no leverage, just your capital)
- `LEVERAGE = 2` → $200 position 
- `LEVERAGE = 5` → $500 position
- `LEVERAGE = 10` → $1,000 position
- `LEVERAGE = 15` → $1,500 position (max for BTC)

**Remember:** Hibachi doesn't have a leverage setting - you control it through position size!

## Support 💬

For tutorials and updates:
- 🎥 [MoonDev YouTube](https://www.youtube.com/@moondevonyt)
- 📺 Watch the build process and live trading sessions

## Known Issues 🔧

**Error: "Insufficient balance"**
- This means your Hibachi Exchange account has zero balance or insufficient funds
- Add USDT to your account to resolve this
- The bot code is working correctly - this is an account-level restriction

## Disclaimer ⚠️

This bot is for educational purposes. Trading cryptocurrency carries significant risk. Only trade with funds you can afford to lose. Always test on testnet first.

## License 📄

MIT License - See LICENSE file for details

---

**Built with 🌙 by MoonDev**