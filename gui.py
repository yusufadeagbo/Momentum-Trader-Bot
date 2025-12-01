# gui.py - Main GUI window for the trading bot
# PyQt5 dashboard with real-time updates

import sys
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QLineEdit, QDialog,
    QFormLayout, QDoubleSpinBox, QSpinBox, QMessageBox,
    QSplitter, QFrame, QSizePolicy, QGroupBox, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont

from styles import DARK_THEME, COLORS
from widgets import (
    BalancePanel, PositionPanel, PriceChartPanel,
    TradeHistoryTable, LogPanel
)


class BotWorker(QThread):
    
    price_update = pyqtSignal(float)
    trigger_update = pyqtSignal(float, float)
    balance_update = pyqtSignal(float, float, dict)
    position_update = pyqtSignal(dict)
    trade_executed = pyqtSignal(dict)
    log_message = pyqtSignal(str, str)
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bot = None
        self._running = False
        self.symbol = "BTC/USDT"
        self.poll_interval = 5.0
        self.settings = {}
    
    def configure(self, symbol, timeframe, exchange, settings=None):
        self.symbol = symbol
        timeframe_map = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600}
        self.window_seconds = timeframe_map.get(timeframe, 300)
        self.exchange = exchange
        if settings:
            self.settings = settings
    
    def run(self):
        """Main bot loop - runs in separate thread"""
        from bot import TradingBot
        from config import get_config
        import time
        
        self._running = True
        self.status_changed.emit("Connecting...")
        self.log_message.emit("Initializing bot...", "INFO")
        
        try:
            config = get_config()
            
            if self.settings:
                if self.settings.get('api_key'):
                    config['API_KEY'] = self.settings['api_key']
                if self.settings.get('secret_key'):
                    config['API_SECRET'] = self.settings['secret_key']
                if self.settings.get('buy_drop_pct'):
                    config['BUY_DROP_PCT'] = self.settings['buy_drop_pct']
                if self.settings.get('take_profit_pct'):
                    config['TAKE_PROFIT_PCT'] = self.settings['take_profit_pct']
                if self.settings.get('stop_loss_pct'):
                    config['STOP_LOSS_PCT'] = self.settings['stop_loss_pct']
                if self.settings.get('trade_size_pct'):
                    config['TRADE_FRACTION'] = self.settings['trade_size_pct'] / 100.0  # Convert from % to fraction
                if self.settings.get('lookback_minutes'):
                    config['LOOKBACK_MINUTES'] = self.settings['lookback_minutes']
            
            self.bot = TradingBot(symbol=self.symbol, config=config)
            self.bot.window_seconds = self.window_seconds
            
            self.log_message.emit(
                f"Strategy: Buy on {self.bot.buy_drop_pct}% drop, "
                f"TP: {self.bot.profit_target_pct}%, SL: {self.bot.stop_loss_pct}%",
                "INFO"
            )
            
            original_execute_buy = self.bot.execute_buy
            original_execute_sell = self.bot.execute_sell
            
            def wrapped_buy(price):
                original_execute_buy(price)
                if self.bot.in_position:
                    self.trade_executed.emit({
                        'time': datetime.now(),
                        'symbol': self.symbol,
                        'side': 'BUY',
                        'price': price,
                        'quantity': self.bot.position_qty,
                        'pnl': None
                    })
                    self.log_message.emit(f"Bought {self.bot.position_qty:.6f} @ ${price:,.2f}", "SUCCESS")
            
            def wrapped_sell(price, emergency=False):
                entry = self.bot.entry_price
                qty = self.bot.position_qty
                original_execute_sell(price, emergency)
                if not self.bot.in_position and entry:
                    pnl = (price - entry) * qty
                    pnl_pct = ((price - entry) / entry) * 100
                    self.trade_executed.emit({
                        'time': datetime.now(),
                        'symbol': self.symbol,
                        'side': 'SELL',
                        'price': price,
                        'quantity': qty,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })
                    if emergency:
                        self.log_message.emit(f"Stop-loss triggered: {pnl_pct:+.2f}%", "ERROR")
                    else:
                        self.log_message.emit(f"Position closed: {pnl_pct:+.2f}% profit", "SUCCESS")
            
            self.bot.execute_buy = wrapped_buy
            self.bot.execute_sell = wrapped_sell
            
            self.bot._init_exchange()
            self.bot.fetch_balance()
            
            existing_pos = self.bot.fetch_open_position()
            if existing_pos:
                self.log_message.emit(
                    f"📊 Found existing position: {existing_pos['qty']:.6f} {existing_pos['asset']}",
                    "WARNING"
                )
                self.log_message.emit(
                    f"   Entry: ${existing_pos['entry_price']:,.2f} | Current: ${existing_pos['current_price']:,.2f} | PnL: {existing_pos['pnl_pct']:+.2f}%",
                    "INFO"
                )
            
            recent_trades = self.bot.fetch_recent_trades(limit=5)
            if recent_trades:
                self.log_message.emit(f"Loaded {len(recent_trades)} recent trades from exchange", "INFO")
                for t in reversed(recent_trades):
                    trade_time = datetime.fromtimestamp(t['timestamp'] / 1000) if t.get('timestamp') else datetime.now()
                    self.trade_executed.emit({
                        'time': trade_time,
                        'symbol': t.get('symbol', self.symbol),
                        'side': t.get('side', '').upper(),
                        'price': float(t.get('price', 0)),
                        'quantity': float(t.get('amount', 0)),
                        'pnl': None,
                        'pnl_pct': None
                    })
            
            self.status_changed.emit("Running")
            self.log_message.emit(f"Bot started. Watching {self.symbol}", "SUCCESS")
            
            holdings = self.bot.fetch_all_balances()
            self.balance_update.emit(self.bot.available_balance, 0, holdings)
            
            position_start = None
            if self.bot.in_position:
                position_start = datetime.now()
            
            while self._running:
                try:
                    price = self.bot.fetch_price()
                    self.price_update.emit(price)
                    
                    holdings = self.bot.fetch_all_balances()
                    
                    in_pos_value = 0
                    if self.bot.in_position:
                        in_pos_value = self.bot.position_qty * price
                        if position_start is None:
                            position_start = datetime.now()
                    else:
                        position_start = None
                    
                    self.balance_update.emit(self.bot.available_balance, in_pos_value, holdings)
                    
                    if self.bot.in_position:
                        pnl_usd = (price - self.bot.entry_price) * self.bot.position_qty
                        pnl_pct = ((price - self.bot.entry_price) / self.bot.entry_price) * 100
                        duration = str(datetime.now() - position_start).split('.')[0] if position_start else "0:00:00"
                        
                        tp_price = self.bot.entry_price * (1 + self.bot.profit_target_pct / 100)
                        sl_price = self.bot.entry_price * (1 - self.bot.stop_loss_pct / 100)
                        
                        # Log TP/SL status occasionally (every ~30 seconds)
                        if not hasattr(self, '_last_tpsl_log') or (datetime.now() - self._last_tpsl_log).seconds >= 30:
                            self._last_tpsl_log = datetime.now()
                            self.log_message.emit(
                                f"📊 PnL: {pnl_pct:+.2f}% | TP at {self.bot.profit_target_pct}% (${tp_price:,.2f}) | SL at -{self.bot.stop_loss_pct}% (${sl_price:,.2f})",
                                "INFO"
                            )
                        
                        self.position_update.emit({
                            'in_position': True,
                            'symbol': self.symbol,
                            'entry': self.bot.entry_price,
                            'current': price,
                            'qty': self.bot.position_qty,
                            'pnl_pct': pnl_pct,
                            'pnl_usd': pnl_usd,
                            'duration': duration,
                            'take_profit': tp_price,
                            'stop_loss': sl_price
                        })
                    else:
                        self.position_update.emit({'in_position': False})
                        
                        if hasattr(self.bot, 'price_history') and len(self.bot.price_history) > 0:
                            ref_price = max(p for _, p in self.bot.price_history)
                            trigger_price = ref_price * (1 - self.bot.buy_drop_pct / 100)
                            self.trigger_update.emit(ref_price, trigger_price)
                    
                    self.bot.process_price_tick(price)
                    
                except Exception as e:
                    self.log_message.emit(f"Error: {str(e)}", "ERROR")
                
                for _ in range(int(self.poll_interval * 10)):
                    if not self._running:
                        break
                    time.sleep(0.1)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
            self.log_message.emit(f"Bot error: {str(e)}", "ERROR")
        
        self.status_changed.emit("Stopped")
        self.log_message.emit("Bot stopped", "WARNING")
    
    def stop(self):
        self._running = False


class SettingsDialog(QDialog):
    """Settings dialog for API keys and trading parameters"""
    
    def __init__(self, parent=None, current_settings=None):
        super().__init__(parent)
        self.setWindowTitle("Trading Settings")
        self.setMinimumWidth(500)
        self.setStyleSheet(DARK_THEME)
        
        settings = current_settings or {}
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        api_group = QGroupBox("API Credentials")
        api_layout = QFormLayout(api_group)
        
        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter your Binance API Key")
        self.api_key_input.setText(settings.get('api_key', ''))
        api_layout.addRow("API Key:", self.api_key_input)
        
        self.secret_key_input = QLineEdit()
        self.secret_key_input.setEchoMode(QLineEdit.Password)
        self.secret_key_input.setPlaceholderText("Enter your Binance Secret Key")
        self.secret_key_input.setText(settings.get('secret_key', ''))
        api_layout.addRow("Secret Key:", self.secret_key_input)
        
        layout.addWidget(api_group)
        
        buy_group = QGroupBox("📉 When to BUY (Entry Signal)")
        buy_layout = QFormLayout(buy_group)
        
        self.buy_drop_input = QDoubleSpinBox()
        self.buy_drop_input.setRange(0.1, 20.0)
        self.buy_drop_input.setSingleStep(0.1)
        self.buy_drop_input.setDecimals(1)
        self.buy_drop_input.setValue(settings.get('buy_drop_pct', 2.0))
        self.buy_drop_input.setSuffix(" %")
        buy_drop_label = QLabel("Buy when price drops by:")
        buy_drop_label.setToolTip("Bot will buy when price drops this much from the lookback window high")
        buy_layout.addRow(buy_drop_label, self.buy_drop_input)
        
        self.lookback_input = QSpinBox()
        self.lookback_input.setRange(1, 60)
        self.lookback_input.setValue(settings.get('lookback_minutes', 5))
        self.lookback_input.setSuffix(" minutes")
        lookback_label = QLabel("Price lookback window:")
        lookback_label.setToolTip("How far back to look for the reference price")
        buy_layout.addRow(lookback_label, self.lookback_input)
        
        layout.addWidget(buy_group)
        
        sell_group = QGroupBox("📈 When to SELL (Exit Signal)")
        sell_layout = QFormLayout(sell_group)
        
        self.take_profit_input = QDoubleSpinBox()
        self.take_profit_input.setRange(0.5, 50.0)
        self.take_profit_input.setSingleStep(0.5)
        self.take_profit_input.setDecimals(1)
        self.take_profit_input.setValue(settings.get('take_profit_pct', 3.0))
        self.take_profit_input.setSuffix(" %")
        tp_label = QLabel("Take profit at:")
        tp_label.setToolTip("Sell when profit reaches this percentage")
        tp_label.setStyleSheet("color: #00ff00;")
        sell_layout.addRow(tp_label, self.take_profit_input)
        
        self.stop_loss_input = QDoubleSpinBox()
        self.stop_loss_input.setRange(0.5, 50.0)
        self.stop_loss_input.setSingleStep(0.5)
        self.stop_loss_input.setDecimals(1)
        self.stop_loss_input.setValue(settings.get('stop_loss_pct', 5.0))
        self.stop_loss_input.setSuffix(" %")
        sl_label = QLabel("Stop loss at:")
        sl_label.setToolTip("Sell to cut losses at this percentage")
        sl_label.setStyleSheet("color: #ff4444;")
        sell_layout.addRow(sl_label, self.stop_loss_input)
        
        layout.addWidget(sell_group)
        
        # === Position Size Section ===
        size_group = QGroupBox("💰 Position Sizing")
        size_layout = QFormLayout(size_group)
        
        self.trade_size_input = QDoubleSpinBox()
        self.trade_size_input.setRange(1, 100)
        self.trade_size_input.setSingleStep(1)
        self.trade_size_input.setDecimals(0)
        self.trade_size_input.setValue(settings.get('trade_size_pct', 10.0))
        self.trade_size_input.setSuffix(" % of balance")
        size_label = QLabel("Use per trade:")
        size_label.setToolTip("Percentage of available balance to use for each trade")
        size_layout.addRow(size_label, self.trade_size_input)
        
        layout.addWidget(size_group)
        
        info_label = QLabel("💡 Settings apply immediately to running bot")
        info_label.setStyleSheet("color: #00ff00; font-style: italic; padding: 8px;")
        layout.addWidget(info_label)
        
        btn_layout = QHBoxLayout()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Save Settings")
        save_btn.setObjectName("start")  # Use green style
        save_btn.clicked.connect(self.accept)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(save_btn)
        
        layout.addLayout(btn_layout)
    
    def get_settings(self):
        return {
            'api_key': self.api_key_input.text(),
            'secret_key': self.secret_key_input.text(),
            'buy_drop_pct': self.buy_drop_input.value(),
            'lookback_minutes': self.lookback_input.value(),
            'take_profit_pct': self.take_profit_input.value(),
            'stop_loss_pct': self.stop_loss_input.value(),
            'trade_size_pct': self.trade_size_input.value(),
        }


class TradingDashboard(QMainWindow):
    """Main trading dashboard window"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Momentum Trader")
        self.setMinimumSize(1000, 700)
        self.setStyleSheet(DARK_THEME)
        
        # Bot worker thread
        self.worker = None
        self.is_running = False
        
        # Trading settings (loaded from config, can be changed via GUI)
        from config import get_config
        config = get_config()
        self.trading_settings = {
            'api_key': config.get('API_KEY', ''),
            'secret_key': config.get('API_SECRET', ''),
            'buy_drop_pct': config.get('BUY_DROP_PCT', 2.0),
            'lookback_minutes': config.get('LOOKBACK_MINUTES', 5),
            'take_profit_pct': config.get('TAKE_PROFIT_PCT', 3.0),
            'stop_loss_pct': config.get('STOP_LOSS_PCT', 5.0),
            'trade_size_pct': config.get('TRADE_FRACTION', 0.1) * 100,  # Convert to percentage
        }
        
        # Build UI
        self._setup_ui()
        
        # Update timer for UI refresh
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._on_timer_tick)
        
        # Current state
        self.current_price = 0
        self.entry_price = None
    
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)
        
        # === Top Controls ===
        controls = self._create_controls()
        main_layout.addWidget(controls)
        
        # === Middle Section (panels) ===
        panels = self._create_panels()
        main_layout.addWidget(panels, stretch=1)
        
        # === Trade History ===
        self.trade_table = TradeHistoryTable()
        main_layout.addWidget(self.trade_table)
        
        # === Log Panel ===
        self.log_panel = LogPanel()
        main_layout.addWidget(self.log_panel)
    
    def _create_controls(self):
        frame = QFrame()
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Start/Stop button
        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("start")
        self.start_btn.setMinimumWidth(100)
        self.start_btn.clicked.connect(self._toggle_bot)
        layout.addWidget(self.start_btn)
        
        self.sell_btn = QPushButton("💰 Sell Now")
        self.sell_btn.setObjectName("stop")
        self.sell_btn.setMinimumWidth(100)
        self.sell_btn.clicked.connect(self._manual_sell)
        self.sell_btn.setEnabled(False)
        layout.addWidget(self.sell_btn)
        
        # Exchange dropdown with proper styling
        exchange_label = QLabel("Exchange:")
        exchange_label.setStyleSheet("color: #888; margin-left: 10px;")
        layout.addWidget(exchange_label)
        
        self.exchange_combo = QComboBox()
        self.exchange_combo.setMinimumWidth(100)
        self.exchange_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px 10px;
                color: white;
                min-height: 28px;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                border: 1px solid #555;
                selection-background-color: #3a6ea5;
                color: white;
            }
        """)
        self.exchange_combo.addItems(["Binance", "Bybit", "KuCoin"])
        self.exchange_combo.currentTextChanged.connect(self._on_exchange_changed)
        layout.addWidget(self.exchange_combo)
        
        # Pair dropdown with proper styling
        pair_label = QLabel("Pair:")
        pair_label.setStyleSheet("color: #888; margin-left: 10px;")
        layout.addWidget(pair_label)
        
        self.pair_combo = QComboBox()
        self.pair_combo.setEditable(True)
        self.pair_combo.setMinimumWidth(150)
        self.pair_combo.setMaxVisibleItems(15)
        self.pair_combo.setInsertPolicy(QComboBox.NoInsert)
        self.pair_combo.setStyleSheet("""
            QComboBox {
                background: #2a2a2a;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 5px 10px;
                color: white;
                min-height: 28px;
            }
            QComboBox::drop-down {
                border: none;
                width: 25px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 6px solid #888;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background: #2a2a2a;
                border: 1px solid #555;
                selection-background-color: #3a6ea5;
                color: white;
                padding: 5px;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 5px;
            }
            QComboBox QAbstractItemView::item:hover {
                background: #3a6ea5;
            }
        """)
        self.pair_combo.addItems([
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "XRP/USDT",
            "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "DOT/USDT", "MATIC/USDT",
            "LINK/USDT", "LTC/USDT", "UNI/USDT", "ATOM/USDT", "ETC/USDT"
        ])
        self.pair_combo.setCurrentText("BTC/USDT")
        layout.addWidget(self.pair_combo)
        
        refresh_btn = QPushButton("🔄")
        refresh_btn.setMaximumWidth(35)
        refresh_btn.setMinimumHeight(30)
        refresh_btn.setToolTip("Refresh available pairs from exchange")
        refresh_btn.clicked.connect(self._refresh_pairs)
        layout.addWidget(refresh_btn)
        
        layout.addStretch()
        
        self.status_label = QLabel("● Stopped")
        self.status_label.setObjectName("status-stopped")
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        settings_btn = QPushButton("⚙ Settings")
        settings_btn.setObjectName("settings")
        settings_btn.clicked.connect(self._show_settings)
        layout.addWidget(settings_btn)
        
        return frame
    
    def _on_exchange_changed(self, exchange):
        self.log_panel.log(f"Exchange changed to {exchange}", "INFO")
    
    def _refresh_pairs(self):
        self.log_panel.log("Fetching available pairs...", "INFO")
        try:
            import ccxt
            from config import get_config
            config = get_config()
            
            exchange = ccxt.binance({
                'apiKey': config.get('API_KEY', ''),
                'secret': config.get('API_SECRET', ''),
            })
            if config.get('TESTNET', True):
                exchange.set_sandbox_mode(True)
            
            markets = exchange.load_markets()
            usdt_pairs = sorted([s for s in markets.keys() if s.endswith('/USDT')])
            
            current = self.pair_combo.currentText()
            self.pair_combo.clear()
            self.pair_combo.addItems(usdt_pairs[:50])
            if current in usdt_pairs:
                self.pair_combo.setCurrentText(current)
            
            self.log_panel.log(f"Loaded {len(usdt_pairs)} USDT pairs", "SUCCESS")
        except Exception as e:
            self.log_panel.log(f"Failed to fetch pairs: {str(e)}", "ERROR")
    
    def _create_panels(self):
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side: Balance + Position stacked
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)
        
        self.balance_panel = BalancePanel()
        left_layout.addWidget(self.balance_panel)
        
        self.position_panel = PositionPanel()
        left_layout.addWidget(self.position_panel)
        
        splitter.addWidget(left_widget)
        
        # Right side: Chart
        self.chart_panel = PriceChartPanel()
        self.chart_panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        splitter.addWidget(self.chart_panel)
        
        # Set stretch factors
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        
        return splitter
    
    def _toggle_bot(self):
        if self.is_running:
            self._stop_bot()
        else:
            self._start_bot()
    
    def _start_bot(self):
        if self.worker and self.worker.isRunning():
            return
        
        # Calculate timeframe from lookback setting
        lookback = self.trading_settings.get('lookback_minutes', 5)
        if lookback <= 1:
            timeframe = '1m'
        elif lookback <= 5:
            timeframe = '5m'
        elif lookback <= 15:
            timeframe = '15m'
        else:
            timeframe = '1h'
        
        self.worker = BotWorker()
        self.worker.configure(
            symbol=self.pair_combo.currentText(),
            timeframe=timeframe,
            exchange=self.exchange_combo.currentText(),
            settings=self.trading_settings  # Pass all trading settings
        )
        
        # Connect signals
        self.worker.price_update.connect(self._on_price_update)
        self.worker.trigger_update.connect(self._on_trigger_update)
        self.worker.balance_update.connect(self._on_balance_update)
        self.worker.position_update.connect(self._on_position_update)
        self.worker.trade_executed.connect(self._on_trade_executed)
        self.worker.log_message.connect(self._on_log_message)
        self.worker.status_changed.connect(self._on_status_changed)
        self.worker.error_occurred.connect(self._on_error)
        
        self.worker.start()
        
        self.is_running = True
        self.start_btn.setText("Stop")
        self.start_btn.setObjectName("stop")
        self.start_btn.setStyle(self.start_btn.style())
        
        self.exchange_combo.setEnabled(False)
        self.pair_combo.setEnabled(False)
        
        self.update_timer.start(1000)
    
    def _stop_bot(self):
        if self.worker:
            self.worker.stop()
            self.worker.wait(2000)
            self.worker = None
        
        self.is_running = False
        self.start_btn.setText("Start")
        self.start_btn.setObjectName("start")
        self.start_btn.setStyle(self.start_btn.style())
        
        self.sell_btn.setEnabled(False)
        
        self.exchange_combo.setEnabled(True)
        self.pair_combo.setEnabled(True)
        
        self.update_timer.stop()
    
    def _manual_sell(self):
        if not self.worker or not self.worker.bot:
            return
        
        if not self.worker.bot.in_position:
            self.log_panel.log("No position to sell", "WARNING")
            return
        
        reply = QMessageBox.question(
            self, 
            "Confirm Sell",
            f"Sell {self.worker.bot.position_qty:.6f} at current price?\n\n"
            f"Entry: ${self.worker.bot.entry_price:,.2f}\n"
            f"Current: ${self.current_price:,.2f}\n"
            f"PnL: {((self.current_price - self.worker.bot.entry_price) / self.worker.bot.entry_price) * 100:+.2f}%",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.log_panel.log("Manual sell initiated...", "WARNING")
            try:
                self.worker.bot.execute_sell(self.current_price)
                self.sell_btn.setEnabled(False)
            except Exception as e:
                self.log_panel.log(f"Sell failed: {str(e)}", "ERROR")
    
    def _show_settings(self):
        dialog = SettingsDialog(self, current_settings=self.trading_settings)
        if dialog.exec_() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.trading_settings.update(settings)
            
            if self.worker and self.worker.bot:
                self.worker.bot.buy_drop_pct = settings['buy_drop_pct']
                self.worker.bot.profit_target_pct = settings['take_profit_pct']
                self.worker.bot.stop_loss_pct = settings['stop_loss_pct']
                self.worker.bot.trade_fraction = settings['trade_size_pct'] / 100.0
                self.worker.bot.window_seconds = settings['lookback_minutes'] * 60
                self.log_panel.log("✅ Settings applied to running bot!", "SUCCESS")
            
            self.log_panel.log(
                f"Buy at {settings['buy_drop_pct']}% drop | "
                f"TP: {settings['take_profit_pct']}% | "
                f"SL: {settings['stop_loss_pct']}%",
                "INFO"
            )
    
    @pyqtSlot(float)
    def _on_price_update(self, price):
        self.current_price = price
        self.chart_panel.add_price(price)
    
    @pyqtSlot(float, float)
    def _on_trigger_update(self, ref_price, trigger_price):
        """Update chart with trigger level (shows where buy would happen)"""
        self.chart_panel.set_trigger_level(trigger_price)
    
    @pyqtSlot(float, float, dict)
    def _on_balance_update(self, available, in_position, holdings):
        total = available + in_position
        
        self.balance_panel.update_data(
            total=total,
            available=available,
            in_position=in_position,
            pnl=0,
            holdings=holdings
        )
    
    @pyqtSlot(dict)
    def _on_position_update(self, pos):
        if pos.get('in_position'):
            self.entry_price = pos['entry']
            self.chart_panel.set_entry_price(pos['entry'])
            self.chart_panel.set_exit_levels(pos.get('take_profit'), pos.get('stop_loss'))
            self.chart_panel.clear_trigger()
            self.sell_btn.setEnabled(True)
            self.position_panel.update_data(
                in_position=True,
                symbol=pos['symbol'],
                entry=pos['entry'],
                current=pos['current'],
                qty=pos['qty'],
                pnl_pct=pos['pnl_pct'],
                pnl_usd=pos['pnl_usd'],
                duration=pos['duration']
            )
        else:
            self.entry_price = None
            self.chart_panel.clear_entry()
            self.sell_btn.setEnabled(False)
            self.position_panel.update_data(in_position=False)
    
    @pyqtSlot(dict)
    def _on_trade_executed(self, trade):
        self.trade_table.add_trade(
            timestamp=trade['time'],
            symbol=trade['symbol'],
            side=trade['side'],
            price=trade['price'],
            quantity=trade['quantity'],
            pnl=trade.get('pnl'),
            pnl_pct=trade.get('pnl_pct')
        )
    
    @pyqtSlot(str, str)
    def _on_log_message(self, message, level):
        self.log_panel.log(message, level)
    
    @pyqtSlot(str)
    def _on_status_changed(self, status):
        self.status_label.setText(f"● {status}")
        if status == "Running":
            self.status_label.setObjectName("status-running")
        elif status == "Stopped":
            self.status_label.setObjectName("status-stopped")
        else:
            self.status_label.setObjectName("status-connecting")
        self.status_label.setStyle(self.status_label.style())
    
    @pyqtSlot(str)
    def _on_error(self, error):
        QMessageBox.critical(self, "Error", error)
        self._stop_bot()
    
    def _on_timer_tick(self):
        # Could add additional periodic updates here
        pass
    
    def closeEvent(self, event):
        """Clean shutdown when window closes"""
        if self.is_running:
            self._stop_bot()
        event.accept()


def run_gui():
    """Entry point for GUI mode"""
    from PyQt5.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    app.setStyle('Fusion')  # consistent look across platforms
    
    window = TradingDashboard()
    window.show()
    
    sys.exit(app.exec_())


if __name__ == "__main__":
    run_gui()
