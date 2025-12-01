#!/usr/bin/env python3
# main.py - Entry point for the trading bot
# Run with GUI by default, or use --headless for CLI mode

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Momentum Trading Bot")
    parser.add_argument("--headless", action="store_true", help="Run without GUI (CLI mode)")
    parser.add_argument("--mainnet", action="store_true", help="Use mainnet instead of testnet")
    parser.add_argument("--interval", type=float, default=5.0, help="Price poll interval in seconds")
    args = parser.parse_args()
    
    if args.headless:
        # Run in CLI mode (original bot.py behavior)
        from bot import main as run_cli
        sys.argv = ['bot.py']  # reset argv for bot's argparse
        if args.mainnet:
            sys.argv.append('--mainnet')
        if args.interval != 5.0:
            sys.argv.extend(['--interval', str(args.interval)])
        run_cli()
    else:
        # Run with GUI
        try:
            from gui import run_gui
            run_gui()
        except ImportError as e:
            print(f"Error: Could not load GUI. Missing dependency: {e}")
            print("Install with: pip install PyQt5 pyqtgraph")
            print("Or run in headless mode: python main.py --headless")
            sys.exit(1)


if __name__ == "__main__":
    main()
