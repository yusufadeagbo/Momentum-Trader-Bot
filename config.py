import os
from typing import Dict

try:
    # optional helper for local dev
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # dotenv is optional in tests
    pass


def get_config() -> Dict:
    """Load configuration from environment variables.

    Keep this minimal and easy to override.
    """
    conf = {
        "API_KEY": os.getenv("BINANCE_API_KEY", ""),
        "API_SECRET": os.getenv("BINANCE_API_SECRET", ""),
        "TESTNET": os.getenv("TESTNET", "true").lower() in ("1", "true", "yes"),
        
        "SYMBOL": os.getenv("SYMBOL", "BTC/USDT"),
        
        "BUY_DROP_PCT": float(os.getenv("BUY_DROP_PCT", "2.0")),        # Buy when price drops this %
        "TAKE_PROFIT_PCT": float(os.getenv("TAKE_PROFIT_PCT", "3.0")),  # Sell when profit reaches this %
        "STOP_LOSS_PCT": float(os.getenv("STOP_LOSS_PCT", "5.0")),      # Sell when loss reaches this %
        "TRADE_FRACTION": float(os.getenv("TRADE_FRACTION", "0.1")),    # % of balance per trade (0.1 = 10%)
        "LOOKBACK_MINUTES": int(os.getenv("LOOKBACK_MINUTES", "5")),    # Price window in minutes
        
        "LOG_LEVEL": os.getenv("LOG_LEVEL", "INFO"),
    }
    return conf
