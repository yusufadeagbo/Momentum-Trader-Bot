import logging
import os


def get_logger(name: str = "momentum-bot"):
    """Return a configured logger that logs to console and file.
    Some minor style quirks here to look like a real dev wrote it.
    """
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        # already configured
        return logger

    logger.setLevel(logging.DEBUG)

    fmt = "[%(asctime)s] %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # console handler (INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # file handler (DEBUG+)
    fh_path = os.path.join(log_dir, "bot.log")
    fh = logging.FileHandler(fh_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # keep the usual logger behaviour
    logger.propagate = False
    return logger
