#!/usr/bin/env python3
"""Analyze paper trading results from paper_state.json."""
import json
import sys
from datetime import datetime, timezone
from collections import defaultdict

STATE_FILE = sys.argv[1] if len(sys.argv) > 1 else "./data/mm-btc/paper_state.json"

with open(STATE_FILE) as f:
    state = json.load(f)

trades = state.get("trade_history", [])
balance = state.get("balance", 0)
initial = state.get("initial_balance", 0)
positions = state.get("positions", [])

if not trades:
    print("No trades found.")
    sys.exit(0)

# --- Basic Stats ---
winning = [t for t in trades if t.get("pnl", 0) > 0]
losing = [t for t in trades if t.get("pnl", 0) < 0]
flat = [t for t in trades if t.get("pnl", 0) == 0]
total_pnl = sum(t.get("pnl", 0) for t in trades)
total_fees = sum(t.get("fee", 0) for t in trades)
net_pnl = total_pnl - total_fees

pnls = [t.get("pnl", 0) for t in trades if t.get("pnl", 0) != 0]
win_pnls = [t.get("pnl", 0) for t in winning]
loss_pnls = [t.get("pnl", 0) for t in losing]

first_ts = trades[0].get("timestamp", 0)
last_ts = trades[-1].get("timestamp", 0)
first_dt = datetime.fromtimestamp(first_ts, tz=timezone.utc)
last_dt = datetime.fromtimestamp(last_ts, tz=timezone.utc)
duration_hours = (last_ts - first_ts) / 3600

print("=" * 60)
print("  PAPER TRADING ANALYSIS REPORT")
print("=" * 60)
print(f"  Period:       {first_dt:%Y-%m-%d %H:%M} ~ {last_dt:%Y-%m-%d %H:%M} UTC")
print(f"  Duration:     {duration_hours:.1f} hours ({duration_hours/24:.1f} days)")
print()

print("--- Performance ---")
print(f"  Initial Balance:  ${initial:,.2f}")
print(f"  Current Balance:  ${balance:,.2f}")
print(f"  Gross P&L:        ${total_pnl:+,.4f}")
print(f"  Total Fees:       ${total_fees:,.4f}")
print(f"  Net P&L:          ${net_pnl:+,.4f}")
print(f"  Return:           {(balance - initial) / initial * 100:+.4f}%")
print()

print("--- Trade Statistics ---")
print(f"  Total Trades:     {len(trades)}")
print(f"  Winning:          {len(winning)} ({len(winning)/len(trades)*100:.1f}%)")
print(f"  Losing:           {len(losing)} ({len(losing)/len(trades)*100:.1f}%)")
print(f"  Flat (PnL=0):     {len(flat)}")
print(f"  Trades/hour:      {len(trades)/max(duration_hours,1):.1f}")
print(f"  Trades/day:       {len(trades)/max(duration_hours/24,1):.1f}")
print()

if win_pnls:
    print("--- Win/Loss Analysis ---")
    print(f"  Avg Win:          ${sum(win_pnls)/len(win_pnls):+,.4f}")
    print(f"  Avg Loss:         ${sum(loss_pnls)/len(loss_pnls):+,.4f}" if loss_pnls else "")
    print(f"  Largest Win:      ${max(win_pnls):+,.4f}")
    print(f"  Largest Loss:     ${min(loss_pnls):+,.4f}" if loss_pnls else "")
    print(f"  Avg Fee/Trade:    ${total_fees/len(trades):.4f}")
    if loss_pnls:
        avg_win = sum(win_pnls) / len(win_pnls)
        avg_loss = abs(sum(loss_pnls) / len(loss_pnls))
        print(f"  Win/Loss Ratio:   {avg_win/avg_loss:.2f}" if avg_loss > 0 else "")
    print()

# --- Equity Curve (by trade) ---
print("--- Equity Curve (every 10th trade) ---")
for i, t in enumerate(trades):
    if i % 10 == 0 or i == len(trades) - 1:
        ts = datetime.fromtimestamp(t["timestamp"], tz=timezone.utc)
        print(f"  Trade {i+1:>4}: ${t['balance_after']:>10,.2f}  ({ts:%m-%d %H:%M})")
print()

# --- Hourly Breakdown ---
hourly_pnl = defaultdict(lambda: {"pnl": 0, "fees": 0, "count": 0})
for t in trades:
    dt = datetime.fromtimestamp(t["timestamp"], tz=timezone.utc)
    key = dt.strftime("%Y-%m-%d %H:00")
    hourly_pnl[key]["pnl"] += t.get("pnl", 0)
    hourly_pnl[key]["fees"] += t.get("fee", 0)
    hourly_pnl[key]["count"] += t.get("pnl", 0) != 0  # only count non-zero

# Show daily summary instead if too many hours
daily_pnl = defaultdict(lambda: {"pnl": 0, "fees": 0, "count": 0, "trades": 0})
for t in trades:
    dt = datetime.fromtimestamp(t["timestamp"], tz=timezone.utc)
    key = dt.strftime("%Y-%m-%d")
    daily_pnl[key]["pnl"] += t.get("pnl", 0)
    daily_pnl[key]["fees"] += t.get("fee", 0)
    daily_pnl[key]["trades"] += 1

print("--- Daily Breakdown ---")
cumulative = 0
for day in sorted(daily_pnl):
    d = daily_pnl[day]
    net = d["pnl"] - d["fees"]
    cumulative += net
    print(f"  {day}: {d['trades']:>3} trades | Gross: ${d['pnl']:+,.4f} | Fees: ${d['fees']:.4f} | Net: ${net:+,.4f} | Cum: ${cumulative:+,.4f}")
print()

# --- Current Position ---
print("--- Current Position ---")
if positions:
    for p in positions:
        print(f"  {p.get('direction','?')} {p.get('quantity',0)} {p.get('symbol','?')} @ ${p.get('open_price',0):,.2f}")
else:
    print("  Flat (no open positions)")
print()

# --- Buy vs Sell breakdown ---
buys = [t for t in trades if t.get("side") == "buy"]
sells = [t for t in trades if t.get("side") == "sell"]
print("--- Side Breakdown ---")
print(f"  Buy trades:   {len(buys)}")
print(f"  Sell trades:  {len(sells)}")
print()

# --- Recent 10 Trades ---
print("--- Last 10 Trades ---")
for t in trades[-10:]:
    ts = datetime.fromtimestamp(t["timestamp"], tz=timezone.utc)
    side = t.get("side", "?").upper()
    print(f"  {ts:%m-%d %H:%M} {side:>4} {t.get('quantity',0):.8f} @ ${t.get('price',0):>10,.2f} | PnL: ${t.get('pnl',0):+,.4f} | Fee: ${t.get('fee',0):.4f} | Bal: ${t.get('balance_after',0):,.2f}")

print("=" * 60)
