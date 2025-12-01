# widgets.py - Custom widgets for the trading dashboard
# Nothing fancy, just practical panels and components

from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QSizePolicy, QComboBox
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from styles import COLORS
from datetime import datetime
from collections import deque

try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False


class Panel(QFrame):
    """Base panel with consistent styling"""
    
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setFrameShape(QFrame.StyledPanel)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(8)
        
        if title:
            title_label = QLabel(title)
            title_label.setObjectName("title")
            self.layout.addWidget(title_label)


class BalancePanel(Panel):
    
    def __init__(self, parent=None):
        super().__init__("Account Balance", parent)
        
        from PyQt5.QtWidgets import QListWidget, QListWidgetItem
        
        self.total_label = self._create_row("Total Value:", "$0.00")
        self.usdt_label = self._create_row("USDT:", "$0.00")
        self.pnl_label = self._create_row("Session PnL:", "0.00%")
        
        # Holdings list (scrollable)
        holdings_label = QLabel("Holdings:")
        holdings_label.setStyleSheet("color: #888888; margin-top: 8px;")
        self.layout.addWidget(holdings_label)
        
        self.holdings_list = QListWidget()
        self.holdings_list.setMaximumHeight(80)
        self.holdings_list.setStyleSheet("""
            QListWidget {
                background: #252525;
                border: 1px solid #444;
                border-radius: 4px;
                color: white;
                font-size: 12px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #333;
            }
            QListWidget::item:hover {
                background: #333;
            }
            QListWidget::item:selected {
                background: #3a6ea5;
            }
        """)
        self.holdings_list.addItem("No holdings")
        self.layout.addWidget(self.holdings_list)
        
        self.balance_history = []
        self.start_balance = None
        
        self.layout.addStretch()
    
    def _create_row(self, label_text, value_text):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("color: #888888;")
        value = QLabel(value_text)
        value.setObjectName("value")
        value.setAlignment(Qt.AlignRight)
        row.addWidget(label)
        row.addWidget(value)
        self.layout.addLayout(row)
        return value
    
    def update_data(self, total=0, available=0, in_position=0, pnl=0, holdings=None):
        self.total_label.setText(f"${total:,.2f}")
        self.usdt_label.setText(f"${available:,.2f}")
        
        if holdings:
            self.holdings_list.clear()
            has_holdings = False
            for asset, qty in holdings.items():
                if qty > 0.00001 and asset != 'USDT':
                    self.holdings_list.addItem(f"{asset}: {qty:.6f}")
                    has_holdings = True
            if not has_holdings:
                self.holdings_list.addItem("No holdings")
        
        if self.start_balance is None and total > 0:
            self.start_balance = total
        
        if self.start_balance and self.start_balance > 0:
            session_pnl = ((total - self.start_balance) / self.start_balance) * 100
            pnl_text = f"{session_pnl:+.2f}%"
            if session_pnl >= 0:
                self.pnl_label.setStyleSheet(f"color: {COLORS['profit']}; font-size: 16px; font-weight: bold;")
            else:
                self.pnl_label.setStyleSheet(f"color: {COLORS['loss']}; font-size: 16px; font-weight: bold;")
            self.pnl_label.setText(pnl_text)


class PositionPanel(Panel):
    """Shows current position details"""
    
    def __init__(self, parent=None):
        super().__init__("Current Position", parent)
        
        self.no_position_label = QLabel("No open position")
        self.no_position_label.setStyleSheet("color: #888888; font-style: italic;")
        self.no_position_label.setAlignment(Qt.AlignCenter)
        
        # Position details (hidden when no position)
        self.details_widget = QFrame()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(4)
        
        self.symbol_label = self._create_row(details_layout, "Symbol:", "—")
        self.entry_label = self._create_row(details_layout, "Entry Price:", "—")
        self.current_label = self._create_row(details_layout, "Current Price:", "—")
        self.qty_label = self._create_row(details_layout, "Quantity:", "—")
        self.pnl_label = self._create_row(details_layout, "PnL:", "—")
        self.duration_label = self._create_row(details_layout, "Duration:", "—")
        
        self.layout.addWidget(self.no_position_label)
        self.layout.addWidget(self.details_widget)
        self.details_widget.hide()
        
        self.layout.addStretch()
    
    def _create_row(self, layout, label_text, value_text):
        row = QHBoxLayout()
        label = QLabel(label_text)
        label.setStyleSheet("color: #888888;")
        value = QLabel(value_text)
        value.setAlignment(Qt.AlignRight)
        row.addWidget(label)
        row.addWidget(value)
        layout.addLayout(row)
        return value
    
    def update_data(self, in_position=False, symbol="", entry=0, current=0, qty=0, pnl_pct=0, pnl_usd=0, duration=""):
        if not in_position:
            self.no_position_label.show()
            self.details_widget.hide()
            return
        
        self.no_position_label.hide()
        self.details_widget.show()
        
        self.symbol_label.setText(symbol)
        self.entry_label.setText(f"${entry:,.2f}")
        self.current_label.setText(f"${current:,.2f}")
        self.qty_label.setText(f"{qty:.6f}")
        
        pnl_text = f"${pnl_usd:+,.2f} ({pnl_pct:+.2f}%)"
        if pnl_pct >= 0:
            self.pnl_label.setStyleSheet(f"color: {COLORS['profit']};")
        else:
            self.pnl_label.setStyleSheet(f"color: {COLORS['loss']};")
        self.pnl_label.setText(pnl_text)
        
        self.duration_label.setText(duration)


class PriceChartPanel(Panel):
    
    def __init__(self, parent=None):
        super().__init__("Price Chart", parent)
        
        self.prices = deque(maxlen=50)
        self.entry_price = None
        self.trigger_price = None
        self.take_profit_price = None
        self.stop_loss_price = None
        
        if HAS_PYQTGRAPH:
            pg.setConfigOptions(antialias=True)
            self.plot_widget = pg.PlotWidget()
            self.plot_widget.setBackground('#2d2d2d')
            self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
            self.plot_widget.setLabel('left', 'Price', units='$')
            self.plot_widget.getAxis('left').setPen(pg.mkPen(color='#888888'))
            self.plot_widget.getAxis('bottom').setPen(pg.mkPen(color='#888888'))
            
            self.price_line = self.plot_widget.plot(pen=pg.mkPen(color='#00d4aa', width=2))
            self.entry_line = None
            self.trigger_line = None
            self.tp_line = None
            self.sl_line = None
            
            self.layout.addWidget(self.plot_widget)
        else:
            self.fallback_label = QLabel("Price chart requires pyqtgraph\nInstall with: pip install pyqtgraph")
            self.fallback_label.setStyleSheet("color: #888888; font-style: italic;")
            self.fallback_label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(self.fallback_label)
            self.layout.addStretch()
    
    def add_price(self, price):
        self.prices.append(price)
        self._update_chart()
    
    def set_entry_price(self, price):
        self.entry_price = price
        self._update_chart()
    
    def set_exit_levels(self, take_profit, stop_loss):
        self.take_profit_price = take_profit
        self.stop_loss_price = stop_loss
        self._update_chart()
    
    def set_trigger_level(self, price):
        self.trigger_price = price
        self._update_chart()
    
    def clear_entry(self):
        self.entry_price = None
        self.take_profit_price = None
        self.stop_loss_price = None
        self._update_chart()
    
    def clear_trigger(self):
        self.trigger_price = None
        self._update_chart()
    
    def _update_chart(self):
        if not HAS_PYQTGRAPH:
            return
        
        if len(self.prices) > 0:
            self.price_line.setData(list(self.prices))
            
            if self.entry_price and self.entry_line is None:
                self.entry_line = pg.InfiniteLine(
                    pos=self.entry_price,
                    angle=0,
                    pen=pg.mkPen(color='#ffaa00', width=1, style=Qt.DashLine),
                    label='Entry: ${:.0f}'.format(self.entry_price),
                    labelOpts={'color': '#ffaa00', 'position': 0.95}
                )
                self.plot_widget.addItem(self.entry_line)
            elif self.entry_price and self.entry_line:
                self.entry_line.setValue(self.entry_price)
            elif not self.entry_price and self.entry_line:
                self.plot_widget.removeItem(self.entry_line)
                self.entry_line = None
            
            if self.take_profit_price and self.tp_line is None:
                self.tp_line = pg.InfiniteLine(
                    pos=self.take_profit_price,
                    angle=0,
                    pen=pg.mkPen(color='#00ff00', width=2, style=Qt.DashLine),
                    label='TP: ${:.0f}'.format(self.take_profit_price),
                    labelOpts={'color': '#00ff00', 'position': 0.85}
                )
                self.plot_widget.addItem(self.tp_line)
            elif self.take_profit_price and self.tp_line:
                self.tp_line.setValue(self.take_profit_price)
                self.tp_line.label.setText('TP: ${:.0f}'.format(self.take_profit_price))
            elif not self.take_profit_price and self.tp_line:
                self.plot_widget.removeItem(self.tp_line)
                self.tp_line = None
            
            if self.stop_loss_price and self.sl_line is None:
                self.sl_line = pg.InfiniteLine(
                    pos=self.stop_loss_price,
                    angle=0,
                    pen=pg.mkPen(color='#ff4444', width=2, style=Qt.DashLine),
                    label='SL: ${:.0f}'.format(self.stop_loss_price),
                    labelOpts={'color': '#ff4444', 'position': 0.75}
                )
                self.plot_widget.addItem(self.sl_line)
            elif self.stop_loss_price and self.sl_line:
                self.sl_line.setValue(self.stop_loss_price)
                self.sl_line.label.setText('SL: ${:.0f}'.format(self.stop_loss_price))
            elif not self.stop_loss_price and self.sl_line:
                self.plot_widget.removeItem(self.sl_line)
                self.sl_line = None
            
            if self.trigger_price and self.trigger_line is None:
                self.trigger_line = pg.InfiniteLine(
                    pos=self.trigger_price,
                    angle=0,
                    pen=pg.mkPen(color='#00ff00', width=2, style=Qt.DashLine),
                    label='BUY if ≤ ${:.0f}'.format(self.trigger_price),
                    labelOpts={'color': '#00ff00', 'position': 0.05}
                )
                self.plot_widget.addItem(self.trigger_line)
            elif self.trigger_price and self.trigger_line:
                self.trigger_line.setValue(self.trigger_price)
                self.trigger_line.label.setText('BUY if ≤ ${:.0f}'.format(self.trigger_price))
            elif not self.trigger_price and self.trigger_line:
                self.plot_widget.removeItem(self.trigger_line)
                self.trigger_line = None


class TradeHistoryTable(Panel):
    """Table showing recent trades"""
    
    def __init__(self, parent=None):
        super().__init__("Recent Trades", parent)
        
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Time", "Symbol", "Side", "Price", "Quantity", "PnL"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setMaximumHeight(200)
        
        self.layout.addWidget(self.table)
        
        # Store trades
        self.trades = []
    
    def add_trade(self, timestamp, symbol, side, price, quantity, pnl=None, pnl_pct=None):
        trade = {
            'time': timestamp,
            'symbol': symbol,
            'side': side,
            'price': price,
            'quantity': quantity,
            'pnl': pnl,
            'pnl_pct': pnl_pct
        }
        self.trades.insert(0, trade)
        self.trades = self.trades[:10]
        self._refresh_table()
    
    def _refresh_table(self):
        self.table.setRowCount(len(self.trades))
        
        for row, trade in enumerate(self.trades):
            time_str = trade['time'].strftime("%H:%M:%S") if isinstance(trade['time'], datetime) else str(trade['time'])
            
            self.table.setItem(row, 0, QTableWidgetItem(time_str))
            self.table.setItem(row, 1, QTableWidgetItem(trade['symbol']))
            
            side_item = QTableWidgetItem(trade['side'])
            if trade['side'] == 'BUY':
                side_item.setForeground(QColor(COLORS['accent']))
            else:
                side_item.setForeground(QColor(COLORS['warning']))
            self.table.setItem(row, 2, side_item)
            
            self.table.setItem(row, 3, QTableWidgetItem(f"${trade['price']:,.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(f"{trade['quantity']:.6f}"))
            
            if trade['pnl'] is not None:
                pnl_text = f"${trade['pnl']:+,.2f}"
                if trade.get('pnl_pct') is not None:
                    pnl_text += f" ({trade['pnl_pct']:+.2f}%)"
                pnl_item = QTableWidgetItem(pnl_text)
                if trade['pnl'] >= 0:
                    pnl_item.setForeground(QColor(COLORS['profit']))
                else:
                    pnl_item.setForeground(QColor(COLORS['loss']))
                self.table.setItem(row, 5, pnl_item)
            else:
                self.table.setItem(row, 5, QTableWidgetItem("—"))


class LogPanel(Panel):
    """Scrollable log viewer"""
    
    def __init__(self, parent=None):
        super().__init__("Activity Log", parent)
        
        from PyQt5.QtWidgets import QTextEdit
        
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMinimumHeight(120)
        
        self.layout.addWidget(self.log_view)
    
    def log(self, message, level="INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if level == "SUCCESS":
            color = COLORS['profit']
            icon = "✓"
        elif level == "ERROR":
            color = COLORS['loss']
            icon = "✗"
        elif level == "WARNING":
            color = COLORS['warning']
            icon = "⚠"
        else:
            color = COLORS['text']
            icon = "→"
        
        html = f'<span style="color: #888888;">[{timestamp}]</span> <span style="color: {color};">{icon} {message}</span><br>'
        self.log_view.insertHtml(html)
        
        # Auto-scroll to bottom
        scrollbar = self.log_view.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear(self):
        self.log_view.clear()
