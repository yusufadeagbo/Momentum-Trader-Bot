import asyncio
import os
import signal
import time
from datetime import datetime

from config import get_config
from logger import get_logger
from utils import (
    check_price_drop,
    check_profit_target,
    check_stop_loss,
    exponential_backoff,
)


logger = get_logger()


class TradingBot:
    """A simple momentum trading bot demo.

    Designed to be readable and look like a quick 2-day demo project.
    """

    def __init__(self, symbol=None, balance: float = None, config=None):
        self.config = config or get_config()
        self.symbol = symbol or self.config.get("SYMBOL", "BTC/USDT")
        self.testnet = self.config.get("TESTNET", True)

        # position / money tracking — balance will be fetched from exchange if None
        self._initial_balance = balance
        self.available_balance = float(balance) if balance else 0.0
        self.in_position = False
        self.entry_price = None
        self.position_qty = 0.0

        # price window for momentum check (timestamp, price)
        self.price_window = []
        lookback = self.config.get("LOOKBACK_MINUTES", 5)
        self.window_seconds = int(lookback) * 60

        # trading rules — all from config, can be updated at runtime
        self.trade_fraction = float(self.config.get("TRADE_FRACTION", 0.1))
        self.buy_drop_pct = float(self.config.get("BUY_DROP_PCT", 2.0))
        self.profit_target_pct = float(self.config.get("TAKE_PROFIT_PCT", 3.0))
        self.stop_loss_pct = float(self.config.get("STOP_LOSS_PCT", 5.0))

        # control
        self._running = False
        self._backoff_attempts = 0

        # exchange client (lazy init)
        self._exchange = None

        logger.info("TradingBot init: symbol=%s testnet=%s", self.symbol, self.testnet)

    # ============ Exchange connection ============
    def _init_exchange(self):
        """Initialize CCXT exchange client for Binance (testnet or mainnet)."""
        import ccxt

        api_key = self.config.get("API_KEY", "")
        api_secret = self.config.get("API_SECRET", "")

        if not api_key or not api_secret:
            raise ValueError("API_KEY and API_SECRET must be set in .env")

        exchange_class = ccxt.binance
        params = {
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
        }

        if self.testnet:
            # Binance testnet URLs
            params["urls"] = {
                "api": {
                    "public": "https://testnet.binance.vision/api",
                    "private": "https://testnet.binance.vision/api",
                }
            }
            # also need to set sandbox mode
            params["options"] = {"defaultType": "spot"}

        self._exchange = exchange_class(params)

        if self.testnet:
            self._exchange.set_sandbox_mode(True)

        logger.info("Exchange client initialized (testnet=%s)", self.testnet)

    def fetch_balance(self):
        if not self._exchange:
            self._init_exchange()

        try:
            balance = self._exchange.fetch_balance()
            usdt_free = balance.get("USDT", {}).get("free", 0.0)
            self.available_balance = float(usdt_free)
            logger.info("Fetched balance: %.2f USDT", self.available_balance)
            return self.available_balance
        except Exception as e:
            logger.error("Failed to fetch balance: %s", str(e))
            raise

    def fetch_all_balances(self):
        if not self._exchange:
            self._init_exchange()

        try:
            balance = self._exchange.fetch_balance()
            holdings = {}
            for asset, data in balance.get('total', {}).items():
                if float(data) > 0.00001:
                    holdings[asset] = float(data)
            return holdings
        except Exception as e:
            logger.error("Failed to fetch all balances: %s", str(e))
            return {}

    def fetch_open_position(self):
        """Check if we have an existing position (holding the base asset)."""
        if not self._exchange:
            self._init_exchange()

        try:
            base_asset = self.symbol.split("/")[0]
            balance = self._exchange.fetch_balance()
            held_qty = float(balance.get(base_asset, {}).get("free", 0.0))
            
            if held_qty > 0.00001:
                current_price = self.fetch_price()
                self.in_position = True
                self.position_qty = held_qty
                
                entry_price = current_price
                try:
                    trades = self._exchange.fetch_my_trades(self.symbol, limit=10)
                    buy_trades = [t for t in trades if t.get('side') == 'buy']
                    if buy_trades:
                        last_buy = buy_trades[-1]
                        entry_price = float(last_buy.get('price', current_price))
                        logger.info("Found entry price from last buy: $%.2f", entry_price)
                except:
                    pass
                
                self.entry_price = entry_price
                
                logger.info("Found existing position: %.6f %s (entry: $%.2f, current: $%.2f)", 
                           held_qty, base_asset, entry_price, current_price)
                return {
                    'qty': held_qty,
                    'asset': base_asset,
                    'entry_price': entry_price,
                    'current_price': current_price,
                    'value': held_qty * current_price,
                    'pnl_pct': ((current_price - entry_price) / entry_price) * 100
                }
            return None
        except Exception as e:
            logger.error("Failed to check position: %s", str(e))
            return None

    def fetch_recent_trades(self, limit=10):
        """Fetch recent trades from exchange."""
        if not self._exchange:
            self._init_exchange()

        try:
            trades = self._exchange.fetch_my_trades(self.symbol, limit=limit)
            return trades
        except Exception as e:
            logger.error("Failed to fetch trades: %s", str(e))
            return []

    def fetch_price(self):
        """Fetch current price for symbol."""
        if not self._exchange:
            self._init_exchange()

        try:
            ticker = self._exchange.fetch_ticker(self.symbol)
            price = float(ticker["last"])
            return price
        except Exception as e:
            logger.error("Failed to fetch price: %s", str(e))
            raise

    # ============ Core logic (pure-ish) ============
    def process_price_tick(self, price: float, ts: float = None):
        """Process a new price tick. This is the core entrypoint for strategy logic.

        Designed to be callable from tests without network dependencies.
        """
        ts = ts or time.time()
        # append and purge old entries
        self.price_window.append((ts, float(price)))
        cutoff = ts - self.window_seconds
        self.price_window = [(t, p) for (t, p) in self.price_window if t >= cutoff]

        # need at least a reference price from 5min ago - use earliest in window
        if not self.price_window:
            return

        reference_time, reference_price = self.price_window[0]
        current_price = float(price)

        # DEBUG level logs for prices
        logger.debug("Tick %s price=%.2f ref=%.2f", datetime.utcfromtimestamp(ts).isoformat(), current_price, reference_price)

        # If not in a trade, consider buy
        if not self.in_position:
            should_buy, drop_pct = check_price_drop(current_price, reference_price, threshold_pct=self.buy_drop_pct)
            if should_buy:
                logger.info("Buy signal detected: drop=%.2f%%", drop_pct)
                self.execute_buy(price=current_price)
            # else: no-op
            return

        # If we are in a trade, check for profit target or stop loss
        sold = False
        hit_profit, profit_pct = check_profit_target(current_price, self.entry_price, target_pct=self.profit_target_pct)
        if hit_profit:
            logger.info("Profit target hit: %.2f%% — selling", profit_pct)
            self.execute_sell(price=current_price)
            sold = True

        if not sold:
            hit_stop, loss_pct = check_stop_loss(current_price, self.entry_price, stop_pct=self.stop_loss_pct)
            if hit_stop:
                logger.error("Stop-loss triggered: %.2f%% loss — emergency sell", loss_pct)
                self.execute_sell(price=current_price, emergency=True)

    # ============ Simulated order execution (for tests) ============
    def buy(self, price: float):
        """Simulate placing a buy order using a fraction of available balance.

        Used by tests. For real trading, use execute_buy().
        """
        if self.in_position:
            logger.warning("Attempt to buy while already in position — ignored")
            return

        amount_to_use = self.available_balance * self.trade_fraction
        if amount_to_use <= 0:
            logger.warning("Insufficient available balance to buy")
            return

        qty = amount_to_use / price
        # rounding to simulate exchange behaviour
        self.position_qty = round(qty, 6)
        self.entry_price = price
        self.available_balance -= amount_to_use
        self.in_position = True

        logger.info("BUY executed: price=%.2f qty=%.6f used=%.2f", price, self.position_qty, amount_to_use)
        # TODO: record order id, timestamp etc. temporary solution

    def sell(self, price: float, emergency: bool = False):
        """Simulate selling the current position.

        Used by tests. For real trading, use execute_sell().
        """
        if not self.in_position:
            logger.warning("Attempt to sell but no position open — ignored")
            return

        proceeds = self.position_qty * price
        cost_basis = self.position_qty * self.entry_price
        pnl = proceeds - cost_basis
        self.available_balance += proceeds

        logger.info("SELL executed: price=%.2f qty=%.6f proceeds=%.2f pnl=%.2f", price, self.position_qty, proceeds, pnl)

        # reset position
        self.in_position = False
        self.entry_price = None
        self.position_qty = 0.0

        if emergency:
            # small debug note
            logger.debug("Emergency sell completed")

    # ============ Real order execution ============
    def execute_buy(self, price: float):
        """Place a real market buy order on the exchange."""
        if self.in_position:
            logger.warning("Attempt to buy while already in position — ignored")
            return

        if not self._exchange:
            self._init_exchange()

        # Refresh balance before buying
        try:
            self.fetch_balance()
        except Exception:
            logger.error("Could not refresh balance before buy")
            return

        amount_to_use = self.available_balance * self.trade_fraction
        if amount_to_use < 10:  # Binance min order ~10 USDT
            logger.warning("Insufficient balance to buy (need at least 10 USDT, have %.2f)", amount_to_use)
            return

        # Calculate quantity (base asset)
        qty = amount_to_use / price
        # Round to reasonable precision for BTC
        qty = round(qty, 5)

        try:
            logger.info("Placing BUY order: %s qty=%.5f @ market", self.symbol, qty)
            order = self._exchange.create_market_buy_order(self.symbol, qty)
            
            # Extract filled info
            filled_qty = float(order.get("filled", qty))
            avg_price = float(order.get("average", price))
            
            self.position_qty = filled_qty
            self.entry_price = avg_price
            self.in_position = True

            logger.info("BUY filled: price=%.2f qty=%.6f order_id=%s", avg_price, filled_qty, order.get("id"))
        except Exception as e:
            logger.error("BUY order failed: %s", str(e))

    def execute_sell(self, price: float, emergency: bool = False):
        """Place a real market sell order on the exchange."""
        if not self.in_position:
            logger.warning("Attempt to sell but no position open — ignored")
            return

        if not self._exchange:
            self._init_exchange()

        qty = self.position_qty
        if qty <= 0:
            logger.warning("No quantity to sell")
            return

        try:
            logger.info("Placing SELL order: %s qty=%.5f @ market", self.symbol, qty)
            order = self._exchange.create_market_sell_order(self.symbol, qty)

            filled_qty = float(order.get("filled", qty))
            avg_price = float(order.get("average", price))
            proceeds = filled_qty * avg_price
            cost_basis = filled_qty * self.entry_price
            pnl = proceeds - cost_basis

            logger.info("SELL filled: price=%.2f qty=%.6f pnl=%.2f order_id=%s", avg_price, filled_qty, pnl, order.get("id"))

            # reset position
            self.in_position = False
            self.entry_price = None
            self.position_qty = 0.0

            if emergency:
                logger.debug("Emergency sell completed")

        except Exception as e:
            logger.error("SELL order failed: %s", str(e))

    # ============ Main run loop ============
    def run(self, poll_interval: float = 5.0):
        """Main loop: poll price and run strategy."""
        if not self._exchange:
            self._init_exchange()

        # Fetch initial balance
        try:
            self.fetch_balance()
        except Exception as e:
            logger.error("Failed to fetch initial balance: %s", e)
            return

        self._running = True
        logger.info("Starting price polling loop (interval=%.1fs)", poll_interval)
        print(f"Bot running. Watching {self.symbol}. Press Ctrl+C to stop.")

        consecutive_errors = 0
        max_errors = 10

        while self._running:
            try:
                price = self.fetch_price()
                logger.info("Price: %.2f | Position: %s | Balance: %.2f USDT",
                           price,
                           f"YES @ {self.entry_price:.2f}" if self.in_position else "NO",
                           self.available_balance)

                self.process_price_tick(price)
                consecutive_errors = 0  # reset on success

            except Exception as e:
                consecutive_errors += 1
                delay = exponential_backoff(consecutive_errors - 1)
                logger.error("Error fetching price (%d/%d): %s — retrying in %.1fs",
                            consecutive_errors, max_errors, str(e), delay)

                if consecutive_errors >= max_errors:
                    logger.error("Too many consecutive errors, stopping bot")
                    break

                time.sleep(delay)
                continue

            time.sleep(poll_interval)

        logger.info("Bot stopped")

    def health_check(self):
        """Simple health check — could be extended for real monitoring.

        Returns True if bot thinks it's healthy.
        """
        # quick checks
        if self._running and self.in_position is None:
            return False
        return True


def _handle_sigint(bot: TradingBot):
    def _cb(signum, frame):
        logger.info("Received signal %s — shutting down", signum)
        bot._running = False

    return _cb


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Momentum trading bot demo")
    parser.add_argument("--mainnet", action="store_true", help="Use mainnet (default: testnet)")
    parser.add_argument("--interval", type=float, default=5.0, help="Price poll interval in seconds")
    args = parser.parse_args()

    config = get_config()
    config["TESTNET"] = not args.mainnet

    bot = TradingBot(config=config)

    # graceful shutdown
    signal.signal(signal.SIGINT, _handle_sigint(bot))
    signal.signal(signal.SIGTERM, _handle_sigint(bot))

    # Run the bot
    bot.run(poll_interval=args.interval)


if __name__ == "__main__":
    main()
