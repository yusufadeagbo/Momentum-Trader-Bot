# Momentum Trader Bot


## What This Bot Does

- **BUYS** when price drops suddenly (catching the dip)
- **SELLS** when profit target is hit, OR cuts losses if price drops too much

**The Strategy:**

1. Bot monitors price over a time window (default: 5 minutes)
2. When price **drops 2%** from the recent high → it buys
3. Once in a position:
   - **Take Profit:** Sells when price rises **3%** above entry ✅
   - **Stop Loss:** Sells if price drops **5%** below entry to limit losses 🛑

All these numbers are configurable in the Settings panel.

---


## Features

### Live Dashboard

- **Real-time price chart** with entry/exit level lines
- **Account balance** showing your holdings
- **Position panel** with live PnL (profit/loss)
- **Trade history** of recent trades
- **Activity log** so you know what's happening

### Full Control

- Start/Stop the bot anytime
- Manual "Sell Now" button to take profit early
- All settings configurable (no coding needed):
  - Buy trigger %
  - Take profit %
  - Stop loss %
  - Position size %
  - Lookback window

### Safety

- Connects to **Binance Testnet** — practice with fake money first
- Built-in stop-loss protection
- Only trades one position at a time

---

## Quick Setup

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add your API keys

```bash
cp .env.example .env
# edit .env and add your keys from https://testnet.binance.vision/
```

### 3. Run the bot

```bash
python main.py
```

That's it! The dashboard will open and you can configure everything from there.

---

## Running Headless (on a server)

For running on a vps without GUI:

```bash
python main.py --headless
```

Or set up as a service:

```ini
# /etc/systemd/system/momentum-trader.service
[Unit]
Description=Momentum Trading Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/momentum-trader
ExecStart=/path/to/momentum-trader/.venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

---

**Current Limitations:**

- Currently supports Binance (testnet and live)
- No database — state is in memory
- One position at a time

---

## Questions?

The bot is designed to be simple and transparent. Everything it does is shown in the dashboard logs. If something isn't clear, check the logs — they tell you exactly what the bot is thinking and doing.
