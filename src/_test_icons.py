"""Quick test: which icon approaches render in PySide6 on Windows?"""
import sys
from PySide6.QtWidgets import (QApplication, QWidget, QHBoxLayout, QPushButton,
                                QLabel, QStyle, QVBoxLayout)
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QFont

app = QApplication(sys.argv)
win = QWidget()
win.setWindowTitle("Icon Rendering Test")
win.setStyleSheet("background: #1e1e2e; color: #cdd6f4;")
main = QVBoxLayout(win)

# --- Row 1: Unicode characters with default font ---
row1 = QHBoxLayout()
row1.addWidget(QLabel("Default font:"))
for ch in ["?", "ℹ", "⇕", "▼", "▲", "⬇", "⬆", "◀", "▶", "⏬", "☰"]:
    b = QPushButton(ch)
    b.setFixedSize(28, 28)
    b.setStyleSheet("background: #313244; color: #89b4fa; border: 1px solid #585b70; border-radius: 14px; font-size: 12pt; font-weight: bold;")
    row1.addWidget(b)
    row1.addWidget(QLabel(f"U+{ord(ch):04X}"))
main.addLayout(row1)

# --- Row 2: With Segoe UI Symbol font ---
row2 = QHBoxLayout()
row2.addWidget(QLabel("Segoe UI Symbol:"))
for ch in ["?", "ℹ", "⇕", "▼", "▲", "☰", "⚙"]:
    b = QPushButton(ch)
    b.setFixedSize(28, 28)
    b.setStyleSheet("background: #313244; color: #89b4fa; border: 1px solid #585b70; border-radius: 14px; font-size: 12pt; font-weight: bold; font-family: 'Segoe UI Symbol';")
    row2.addWidget(b)
    row2.addWidget(QLabel(f"U+{ord(ch):04X}"))
main.addLayout(row2)

# --- Row 3: QStyle standard icons ---
row3 = QHBoxLayout()
row3.addWidget(QLabel("QStyle icons:"))
icon_map = {
    "Question": QStyle.StandardPixmap.SP_MessageBoxQuestion,
    "Info": QStyle.StandardPixmap.SP_MessageBoxInformation,
    "ArrowDown": QStyle.StandardPixmap.SP_ArrowDown,
    "ArrowUp": QStyle.StandardPixmap.SP_ArrowUp,
    "TitleDown": QStyle.StandardPixmap.SP_TitleBarUnshadeButton,
    "TitleUp": QStyle.StandardPixmap.SP_TitleBarShadeButton,
}
for name, px in icon_map.items():
    b = QPushButton()
    b.setIcon(app.style().standardIcon(px))
    b.setIconSize(QSize(16, 16))
    b.setFixedSize(28, 28)
    b.setStyleSheet("background: #313244; border: 1px solid #585b70; border-radius: 14px;")
    row3.addWidget(b)
    row3.addWidget(QLabel(name))
main.addLayout(row3)

# --- Row 4: HTML-based approach ---
row4 = QHBoxLayout()
row4.addWidget(QLabel("Plain ASCII styled:"))
for text in ["?", "i", "[+]", "[-]", "[?]"]:
    b = QPushButton(text)
    b.setFixedSize(28, 28)
    b.setStyleSheet("background: #313244; color: #89b4fa; border: 1px solid #585b70; border-radius: 14px; font-size: 10pt; font-weight: bold;")
    row4.addWidget(b)
main.addLayout(row4)

win.resize(900, 250)
win.show()
sys.exit(app.exec())
