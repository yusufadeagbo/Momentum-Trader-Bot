# styles.py - QSS stylesheet for modern dark theme
# Keeping it simple and readable

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1e1e1e;
}

QWidget {
    background-color: #1e1e1e;
    color: #ffffff;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 12px;
}

/* Panels */
QFrame#panel {
    background-color: #2d2d2d;
    border-radius: 8px;
    padding: 10px;
}

QLabel {
    color: #ffffff;
}

QLabel#title {
    font-size: 14px;
    font-weight: bold;
    color: #00d4aa;
}

QLabel#value {
    font-size: 18px;
    font-weight: bold;
}

QLabel#profit {
    color: #00ff00;
}

QLabel#loss {
    color: #ff4444;
}

QLabel#status-running {
    color: #00ff00;
    font-weight: bold;
}

QLabel#status-stopped {
    color: #ff4444;
    font-weight: bold;
}

QLabel#status-connecting {
    color: #ffaa00;
    font-weight: bold;
}

/* Buttons */
QPushButton {
    background-color: #3d3d3d;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #4d4d4d;
}

QPushButton:pressed {
    background-color: #2d2d2d;
}

QPushButton#start {
    background-color: #00aa77;
}

QPushButton#start:hover {
    background-color: #00cc99;
}

QPushButton#stop {
    background-color: #cc4444;
}

QPushButton#stop:hover {
    background-color: #ff5555;
}

QPushButton#settings {
    background-color: #555555;
}

/* Combo boxes */
QComboBox {
    background-color: #3d3d3d;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 12px;
    min-width: 100px;
}

QComboBox:hover {
    border-color: #00d4aa;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox::down-arrow {
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #2d2d2d;
    selection-background-color: #00d4aa;
    border: 1px solid #555555;
}

/* Line edits */
QLineEdit {
    background-color: #3d3d3d;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 6px 12px;
    color: #ffffff;
}

QLineEdit:focus {
    border-color: #00d4aa;
}

/* Tables */
QTableWidget {
    background-color: #2d2d2d;
    border: none;
    gridline-color: #3d3d3d;
}

QTableWidget::item {
    padding: 6px;
}

QTableWidget::item:selected {
    background-color: #00d4aa;
    color: #000000;
}

QHeaderView::section {
    background-color: #3d3d3d;
    color: #00d4aa;
    padding: 8px;
    border: none;
    font-weight: bold;
}

/* Scroll areas and text edits */
QTextEdit, QPlainTextEdit {
    background-color: #2d2d2d;
    border: none;
    border-radius: 4px;
    padding: 8px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 11px;
}

QScrollBar:vertical {
    background-color: #2d2d2d;
    width: 10px;
    border-radius: 5px;
}

QScrollBar::handle:vertical {
    background-color: #555555;
    border-radius: 5px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #00d4aa;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

/* Spin boxes */
QSpinBox, QDoubleSpinBox {
    background-color: #3d3d3d;
    border: 1px solid #555555;
    border-radius: 4px;
    padding: 4px 8px;
}

QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: #00d4aa;
}

/* Group boxes */
QGroupBox {
    border: 1px solid #3d3d3d;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 10px;
}

QGroupBox::title {
    color: #00d4aa;
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""

# Colors for programmatic use
COLORS = {
    'background': '#1e1e1e',
    'panel': '#2d2d2d',
    'text': '#ffffff',
    'accent': '#00d4aa',
    'profit': '#00ff00',
    'loss': '#ff4444',
    'warning': '#ffaa00',
    'muted': '#888888',
}
