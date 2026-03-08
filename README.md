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

### Option A: Docker (Recommended for VPS)

```bash
# 1. Clone and enter the repo
git clone https://github.com/sensen55/Hibachi-Crypto-Exchange-Trading-Python-Examples.git
cd Hibachi-Crypto-Exchange-Trading-Python-Examples

# 2. Copy and edit config
cp .env.example .env
# Edit .env if needed (paper trading does NOT require API keys)

# 3. Build and start
docker compose up -d --build

# 4. Watch logs
docker compose logs -f paper-btc-long

# 5. Stop (auto-closes open position)
docker compose down
```

#### Running Multiple Bots

Edit `docker-compose.yml` to uncomment additional services, then:

```bash
docker compose up -d --build
```

Each bot has its own data directory (`./data/btc-long/`, `./data/eth-short/`, etc.)
so they never interfere with each other.

#### Updating the Code

```bash
cd Hibachi-Crypto-Exchange-Trading-Python-Examples
git pull origin main
docker compose down
docker compose up -d --build
```

### Option B: Direct Python (without Docker)

```bash
# 1. Clone and enter the repo
git clone https://github.com/sensen55/Hibachi-Crypto-Exchange-Trading-Python-Examples.git
cd Hibachi-Crypto-Exchange-Trading-Python-Examples

# 2. Install dependencies (Python 3.11+)
pip install -r requirements.txt

# 3. Copy and edit config
cp .env.example .env

# 4. Run paper trading bot
PAPER_STATE_FILE=./paper_state.json python paper_main.py
```

## Configuration ⚙️

All settings are controlled via environment variables (`.env` file or `docker-compose.yml`).

### Trading Settings

| Variable | Description | Default |
|---|---|---|
| `HIBACHI_SYMBOL` | Trading pair | `BTC/USDT-P` |
| `POSITION_SIZE_USD` | Margin per trade (USD) | `100` |
| `LEVERAGE` | Leverage multiplier | `2` |
| `TAKE_PROFIT` | TP % on margin | `2.0` |
| `STOP_LOSS` | SL % on margin (negative) | `-1.0` |
| `LOOP_SLEEP` | Seconds between price checks | `3` |

### Paper Trading Settings

| Variable | Description | Default |
|---|---|---|
| `PAPER_BALANCE` | Starting virtual balance | `10000` |
| `BOT_MODE` | `long` / `short` / `monitor` / `alternate` | `long` |
| `CYCLE_COOLDOWN` | Seconds between trade cycles | `10` |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |
| `PAPER_STATE_FILE` | Path for state persistence | `/data/paper_state.json` |

### Live Trading Settings (requires API keys)

| Variable | Description |
|---|---|
| `HIBACHI_API_KEY` | API key from Hibachi console |
| `HIBACHI_ACCOUNT_ID` | Account ID |
| `HIBACHI_PRIVATE_KEY` | Private key for signing |

## Usage 🎮

### Paper Trading (Docker)
```bash
docker compose up -d --build
docker compose logs -f paper-btc-long
```

### Paper Trading (Direct)
```bash
PAPER_STATE_FILE=./paper_state.json python paper_main.py
```

### Live Trading (requires API keys + Python 3.13+)
```bash
python main.py
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

- `paper_main.py` - Paper trading bot (headless, Docker compatible)
- `paper_trading.py` - Paper trading engine (simulates orders/positions locally)
- `hibachi_market.py` - Lightweight market data client (no SDK dependency, Python 3.11+)
- `main.py` - Live trading bot with interactive menu (requires SDK + Python 3.13+)
- `nice_funks.py` - Hibachi Exchange API wrapper
- `Dockerfile` - Docker image definition
- `docker-compose.yml` - Multi-bot Docker configuration
- `.env.example` - Full configuration reference
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