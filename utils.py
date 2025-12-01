import time


def check_price_drop(current_price, reference_price, threshold_pct=2.0):
    """Return (bool, pct) — True if drop >= threshold.

    A small, realistic implementation — not over-documented on purpose.
    """
    try:
        drop_pct = ((reference_price - current_price) / reference_price) * 100.0
    except Exception:
        # defensive
        return False, 0.0

    # TODO: make threshold configurable via config
    if drop_pct >= threshold_pct:
        # quick debug print (left intentionally)
        # print(f"DEBUG drop_pct={drop_pct}")
        return True, round(drop_pct, 2)
    return False, round(drop_pct, 2)


def check_profit_target(current_price, entry_price, target_pct=3.0):
    try:
        profit_pct = ((current_price - entry_price) / entry_price) * 100.0
    except Exception:
        return False, 0.0
    return (profit_pct >= target_pct), round(profit_pct, 2)


def check_stop_loss(current_price, entry_price, stop_pct=5.0):
    try:
        loss_pct = ((entry_price - current_price) / entry_price) * 100.0
    except Exception:
        return False, 0.0
    return (loss_pct >= stop_pct), round(loss_pct, 2)


def exponential_backoff(attempt: int, base: float = 1.0, cap: float = 32.0):
    """Return delay in seconds for a given attempt count.

    Example: attempt=0 -> 1s, attempt=1 -> 2s, etc.
    """
    delay = base * (2 ** attempt)
    if delay > cap:
        delay = cap
    # small sleep to simulate the backoff in tests if needed
    return delay
