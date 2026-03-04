"""
main.py — XY Stage Positioning Offset Analysis (PySide6)

Layout:
  [Left]  Top:   X/Y Stat Cards (Pass/Fail)
          Bottom: [시스템 로그] | [데이터 테이블]
  [Right] Full-height chart tabs (Contour, Vector Map, Scatter, etc.)
"""

import os
import sys
import math
import subprocess
import threading
from datetime import datetime
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QPushButton, QLabel, QLineEdit, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QFrame, QDialog, QComboBox, QSlider, QToolTip, QCheckBox, QInputDialog,
    QAbstractItemView, QSizePolicy, QStatusBar, QScrollArea, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QColor, QFont, QKeySequence, QShortcut

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_loader import scan_lot_folders, batch_load, get_scan_summary
from analyzer import (
    compute_statistics, compute_group_statistics, compute_trend,
    detect_outliers, compute_repeatability, compute_cpk,
    filter_by_method, filter_valid_only, compute_deviation_matrix,
    compute_xy_product, compute_affine_transform, DIE_POSITIONS, get_die_position,
    compute_pareto_data, compute_correlation, extract_die_positions,
    filter_stabilization_die,
)
from exporter import export_combined_csv, export_excel_report
from settings import load_settings, save_settings, add_recent_folder
## sparkline_delegate not currently used (gauge removed)
from recipe_scanner import scan_recipes, load_recipe_data, load_all_recipes, compare_recipes
import visualizer as viz
import visualizer_pg as viz_pg


# ═══════════════════════════════════════════════
#  Color Constants (Catppuccin Mocha)
# ═══════════════════════════════════════════════
BG      = '#1e1e2e'
BG2     = '#282a3a'
BG3     = '#313244'
FG      = '#cdd6f4'
FG2     = '#a6adc8'
ACCENT  = '#89b4fa'
GREEN   = '#a6e3a1'
RED     = '#f38ba8'
ORANGE  = '#fab387'
PURPLE  = '#cba6f7'

DARK_STYLE = f"""
QMainWindow, QWidget {{ background-color: {BG}; color: {FG}; }}
QSplitter::handle {{ background-color: {BG3}; }}
QTabWidget::pane {{ border: 1px solid {BG3}; background: {BG}; }}
QTabBar::tab {{
    background: {BG3}; color: {FG2}; padding: 8px 16px;
    border-top-left-radius: 6px; border-top-right-radius: 6px;
    font-weight: bold; font-size: 9pt; margin-right: 2px;
}}
QTabBar::tab:selected {{ background: #45475a; color: {ACCENT}; }}
QTabBar::tab:hover {{ background: #3b3d50; }}
QPushButton {{
    background: {BG3}; color: {FG}; border: none; padding: 6px 14px;
    border-radius: 4px; font-size: 9pt;
}}
QPushButton:hover {{ background: {ACCENT}; color: {BG}; }}
QPushButton[accent="true"] {{
    background: {ACCENT}; color: {BG}; font-weight: bold;
}}
QPushButton[accent="true"]:hover {{ background: #74c7ec; }}
QPushButton[step="true"] {{
    padding: 8px 14px; font-weight: bold;
}}
QPushButton[active_step="true"] {{
    background: {ACCENT}; color: {BG}; font-weight: bold; padding: 7px 13px;
    border-radius: 4px; border: 3px solid #ffffff;
}}
QPushButton[step_pass="true"] {{
    background: {GREEN}; color: {BG}; font-weight: bold; padding: 8px 14px;
    border-radius: 4px; border: 2px solid transparent;
}}
QPushButton[step_pass="true"]:hover {{ background: #8ec07c; }}
QPushButton[step_fail="true"] {{
    background: {RED}; color: {BG}; font-weight: bold; padding: 8px 14px;
    border-radius: 4px; border: 2px solid transparent;
}}
QPushButton[step_fail="true"]:hover {{ background: #cc241d; }}
QPushButton[step_active_pass="true"] {{
    background: {GREEN}; color: {BG}; font-weight: bold; padding: 7px 13px;
    border-radius: 4px; border: 3px solid #ffffff;
}}
QPushButton[step_active_pass="true"]:hover {{ background: #8ec07c; }}
QPushButton[step_active_fail="true"] {{
    background: {RED}; color: {BG}; font-weight: bold; padding: 7px 13px;
    border-radius: 4px; border: 3px solid #ffffff;
}}
QPushButton[step_active_fail="true"]:hover {{ background: #cc241d; }}
QLineEdit {{
    background: {BG3}; color: {FG}; border: 1px solid #45475a;
    padding: 4px 8px; border-radius: 4px;
}}
QTableWidget {{
    background: {BG2}; color: {FG}; gridline-color: #45475a;
    border: none; font-family: 'Consolas'; font-size: 9pt;
}}
QTableWidget::item:selected {{ background: #45475a; }}
QHeaderView::section {{
    background: {BG3}; color: {ACCENT}; font-weight: bold;
    padding: 4px; border: none; font-size: 9pt;
}}
QTextEdit {{
    background: #181825; color: {FG}; border: none;
    font-family: 'Consolas'; font-size: 9pt;
}}
QStatusBar {{ background: {BG3}; color: {FG2}; font-family: 'Consolas'; font-size: 9pt; }}
QScrollBar:vertical {{
    background: {BG2}; width: 10px; border: none;
}}
QScrollBar::handle:vertical {{ background: #45475a; border-radius: 5px; min-height: 30px; }}
QScrollBar:horizontal {{
    background: {BG2}; height: 10px; border: none;
}}
QScrollBar::handle:horizontal {{ background: #45475a; border-radius: 5px; min-width: 30px; }}
"""


# ═══════════════════════════════════════════════
#  SystemLogger
# ═══════════════════════════════════════════════
class SystemLogger:
    COLORS = {'info': FG2, 'ok': GREEN, 'warn': ORANGE, 'err': RED, 'head': PURPLE}

    def __init__(self, text_edit: QTextEdit):
        self._te = text_edit
        self._te.setReadOnly(True)

    def _append(self, msg: str, tag: str = 'info'):
        ts = datetime.now().strftime('%H:%M:%S')
        color = self.COLORS.get(tag, FG2)
        tc = ACCENT
        self._te.append(f'<span style="color:{tc}">[{ts}]</span> '
                        f'<span style="color:{color}">{msg}</span>')

    def info(self, m):  self._append(m, 'info')
    def ok(self, m):    self._append(m, 'ok')
    def warn(self, m):  self._append(m, 'warn')
    def error(self, m): self._append(m, 'err')
    def head(self, m):  self._append(m, 'head')

    def section(self, title):
        self._te.append(f'<br><span style="color:{PURPLE};font-weight:bold">'
                        f'{"═"*50}<br>  {title}<br>{"═"*50}</span>')


# ═══════════════════════════════════════════════
#  CopyableTable — QTableWidget + Ctrl+C
# ═══════════════════════════════════════════════
class CopyableTable(QTableWidget):
    """QTableWidget with Ctrl+C → tab-separated clipboard copy (read-only viewer)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setAlternatingRowColors(False)
        self.horizontalHeader().setStretchLastSection(True)
        # Read-only: block all edit triggers while preserving selection
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def _copy_selection(self):
        sel = self.selectedRanges()
        if not sel:
            return
        r = sel[0]
        lines = []
        for row in range(r.topRow(), r.bottomRow() + 1):
            cells = []
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                item = self.item(row, col)
                cells.append(item.text() if item else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))


# ═══════════════════════════════════════════════
#  FlowLayout — 가로 줄바꿈 레이아웃 (Die 체크박스용)
# ═══════════════════════════════════════════════
from PySide6.QtWidgets import QLayout, QWidgetItem
from PySide6.QtCore import QRect, QSize

class FlowLayout(QLayout):
    """가로로 배치하다 넘치면 다음 줄로 넘기는 레이아웃."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        if spacing >= 0:
            self._spacing = spacing
        else:
            self._spacing = 4
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only=False):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            w = item.widget()
            if w is None:
                continue
            space = self._spacing
            next_x = x + w.sizeHint().width() + space
            if next_x - space > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + space
                next_x = x + w.sizeHint().width() + space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, w.sizeHint().width(), w.sizeHint().height()))
            x = next_x
            line_height = max(line_height, w.sizeHint().height())
        return y + line_height - rect.y() + m.bottom()


# ═══════════════════════════════════════════════
#  ChartWidget — FigureCanvas + Toolbar (Matplotlib)
# ═══════════════════════════════════════════════
class ChartWidget(QWidget):
    """Matplotlib Figure를 인터랙티브 차트로 표시 (줌/패닝/저장)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = None
        self._toolbar = None

    def set_figure(self, fig):
        if self._canvas:
            old_fig = self._canvas.figure
            self._layout.removeWidget(self._toolbar)
            self._layout.removeWidget(self._canvas)
            self._toolbar.deleteLater()
            self._canvas.deleteLater()
            import matplotlib.pyplot as _plt
            _plt.close(old_fig)
        self._canvas = FigureCanvasQTAgg(fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._layout.addWidget(self._toolbar)
        self._layout.addWidget(self._canvas)

    def clear(self):
        if self._canvas:
            self._layout.removeWidget(self._toolbar)
            self._layout.removeWidget(self._canvas)
            self._toolbar.deleteLater()
            self._canvas.deleteLater()
            self._canvas = None
            self._toolbar = None


# ═══════════════════════════════════════════════
#  InteractiveChartWidget — pyqtgraph 위젯 컨테이너
# ═══════════════════════════════════════════════
class InteractiveChartWidget(QWidget):
    """pyqtgraph 위젯을 감싸는 컨테이너. ChartWidget과 동일한 패턴."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._widget = None

    def set_widget(self, widget):
        """pyqtgraph 위젯을 설정 (기존 위젯 교체)."""
        if self._widget:
            self._layout.removeWidget(self._widget)
            self._widget.deleteLater()
        self._widget = widget
        self._layout.addWidget(widget)

    def get_widget(self):
        """현재 설정된 pyqtgraph 위젯 반환."""
        return self._widget

    def clear(self):
        if self._widget:
            self._layout.removeWidget(self._widget)
            self._widget.deleteLater()
            self._widget = None


# ═══════════════════════════════════════════════
#  StatCard
# ═══════════════════════════════════════════════
class StatCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statcard")
        self.setStyleSheet(f"""
            #statcard {{ background: {BG2}; border: 1px solid #585b70;
                         border-radius: 6px; padding: 8px; }}
            #statcard QLabel {{ background: transparent; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {FG2};")
        layout.addWidget(lbl_title)

        self.lbl_avg = self._row(layout, "Avg (nm):")
        self.lbl_rng, self.lbl_rng_spec = self._row_with_spec(layout, "Dev Range (µm):")
        self.lbl_std, self.lbl_std_spec = self._row_with_spec(layout, "Dev StdDev (µm):")
        self.lbl_cpk = self._row(layout, "Cpk:")

        self.badge = QLabel("—")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(
            f"background: gray; color: {BG}; font-weight: bold; "
            f"padding: 4px; border-radius: 4px; font-size: 10pt;"
        )
        layout.addWidget(self.badge)

    def _row(self, layout, label_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        val = QLabel("—")
        val.setAlignment(Qt.AlignRight)
        val.setStyleSheet(f"color: {FG}; font-weight: bold; font-size: 12pt;")
        row.addWidget(lbl)
        row.addWidget(val)
        layout.addLayout(row)
        return val

    def _row_with_spec(self, layout, label_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        val = QLabel("—")
        val.setAlignment(Qt.AlignRight)
        val.setStyleSheet(f"color: {FG}; font-weight: bold; font-size: 12pt;")
        spec_lbl = QLabel("")
        spec_lbl.setAlignment(Qt.AlignRight)
        spec_lbl.setStyleSheet(f"font-size: 9pt; min-width: 90px;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        row.addWidget(spec_lbl)
        layout.addLayout(row)
        return val, spec_lbl

    def _format_spec_delta(self, value, spec):
        """Spec 대비 표기 생성: 초과=빨강▲, 여유=초록✓"""
        if spec is None or spec == 0:
            return "", ""
        ratio = value / spec * 100
        if value > spec:
            pct = ratio - 100
            text = f"/ {spec}  ▲+{pct:.0f}%"
            color = RED
        else:
            pct = 100 - ratio
            text = f"/ {spec}  ✓{pct:.0f}%"
            color = GREEN
        return text, color

    def update_stats(self, avg, rng, std, cpk, is_pass: bool = None,
                     spec_r=None, spec_s=None):
        self.lbl_avg.setText(f"{avg:.3f}")
        self.lbl_rng.setText(f"{rng:.3f}")
        self.lbl_std.setText(f"{std:.3f}")
        self.lbl_cpk.setText(f"{cpk:.2f}")

        # Spec 대비 표기
        rng_text, rng_color = self._format_spec_delta(rng, spec_r)
        self.lbl_rng_spec.setText(rng_text)
        self.lbl_rng_spec.setStyleSheet(
            f"font-size: 9pt; color: {rng_color}; min-width: 90px;")

        std_text, std_color = self._format_spec_delta(std, spec_s)
        self.lbl_std_spec.setText(std_text)
        self.lbl_std_spec.setStyleSheet(
            f"font-size: 9pt; color: {std_color}; min-width: 90px;")

        if is_pass is None:
            self.badge.setText("—")
            self.badge.setStyleSheet(
                f"background: gray; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )
        elif is_pass:
            self.badge.setText("✅ PASS")
            self.badge.setStyleSheet(
                f"background: {GREEN}; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )
        else:
            self.badge.setText("❌ FAIL")
            self.badge.setStyleSheet(
                f"background: {RED}; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )


# ═══════════════════════════════════════════════
#  DataLoaderThread
# ═══════════════════════════════════════════════
class DataLoaderThread(QThread):
    finished = Signal(object, object, float)
    error = Signal(str)

    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder = folder

    def run(self):
        import time
        t0 = time.perf_counter()
        try:
            results = load_all_recipes(self.folder, round_name='1st', axis='both')
            comparison = compare_recipes(results)
            elapsed = time.perf_counter() - t0
            self.finished.emit(results, comparison, elapsed)
        except Exception as e:
            self.error.emit(str(e))


# ═══════════════════════════════════════════════
#  Color Helpers
# ═══════════════════════════════════════════════
def _heatmap_diverging(ratio: float) -> QColor:
    ratio = max(-1.0, min(1.0, ratio))
    if ratio >= 0:
        r, g, b = 255, int(255*(1-ratio)), int(235*(1-ratio))
    else:
        r, g, b = int(255*(1+ratio)), int(230*(1+ratio)), 255
    return QColor(r, g, b)

def _heatmap_single(ratio: float) -> QColor:
    ratio = max(0.0, min(1.0, ratio))
    r = int(240 - (240-58)*ratio)
    g = int(244 - (244-122)*ratio)
    b = int(248 - (248-189)*ratio)
    return QColor(r, g, b)

def _contrast_fg(bg: QColor) -> QColor:
    lum = 0.299*bg.red() + 0.587*bg.green() + 0.114*bg.blue()
    return QColor('#1e1e2e') if lum > 140 else QColor('#ffffff')


# ═══════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════
class DataAnalyzerApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 XY Stage Offset Analyzer — Workflow")
        self.setMinimumSize(1280, 860)
        self.resize(1600, 1050)

        # State
        self.settings = load_settings()
        self.folder_path = self.settings.get('last_folder', '')
        self.recipes = []
        self.recipe_results = []
        self.current_recipe_idx = -1
        self.raw_data = []
        self.lot_list = []
        self.last_tiff_folder = ''
        self._dev_x = {}
        self._dev_y = {}
        self._loader_thread = None
        self.step_pass_states = {}  # {idx: True/False/None}
        self._trend_data_x = []  # 현재 Step의 X trend 원본 (Lot 필터용)
        self._trend_data_y = []  # 현재 Step의 Y trend 원본
        self._trend_spec = None  # Spec 한계선용
        self._lot_filter_updating = False
        self._lot_checkboxes = {}  # {lot_name: QCheckBox}

        self._build_ui()
        self._restore_settings()
        self.showMaximized()  # 1920×1080 최대화 상태로 시작

    # ──────────────────────────────────────────────
    # Build UI
    # ──────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(8, 4, 8, 2)
        root_layout.setSpacing(2)

        # ===== TOP BAR =====
        top = QHBoxLayout()
        top.addWidget(QLabel("📁"))
        self.path_edit = QLineEdit(self.folder_path)
        self.path_edit.setMinimumWidth(250)
        self.path_edit.setMaximumWidth(450)
        top.addWidget(self.path_edit)

        btn_browse = QPushButton("찾아보기")
        btn_browse.clicked.connect(self._browse_folder)
        top.addWidget(btn_browse)

        btn_scan = QPushButton("🔄 스캔 & 분석")
        btn_scan.setProperty("accent", True)
        btn_scan.clicked.connect(self._scan_folder)
        top.addWidget(btn_scan)

        # Wafer 크기 선택 (200mm / 300mm)
        top.addSpacing(16)
        wafer_label = QLabel("Wafer:")
        wafer_label.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        top.addWidget(wafer_label)
        self.wafer_combo = QComboBox()
        self.wafer_combo.addItems(['200mm', '300mm'])
        wafer_size = self.settings.get('wafer_size', 300)
        self.wafer_combo.setCurrentIndex(0 if wafer_size == 200 else 1)
        self.wafer_combo.setFixedWidth(80)
        self.wafer_combo.setStyleSheet(f"""
            QComboBox {{
                background: {BG3}; color: {FG}; border: 1px solid #585b70;
                border-radius: 4px; padding: 3px 8px; font-size: 9pt;
            }}
            QComboBox::drop-down {{ border: none; }}
            QComboBox QAbstractItemView {{
                background: {BG2}; color: {FG}; selection-background-color: {ACCENT};
            }}
        """)
        self.wafer_combo.currentIndexChanged.connect(self._on_wafer_size_changed)
        top.addWidget(self.wafer_combo)

        top.addStretch()

        root_layout.addLayout(top)

        # ===== STEP NAV =====
        self.nav_layout = QHBoxLayout()
        self.nav_layout.setSpacing(4)
        nav_container = QWidget()
        nav_container.setLayout(self.nav_layout)
        root_layout.addWidget(nav_container)
        self.step_buttons = []

        # ===== MAIN SPLITTER =====
        splitter = QSplitter(Qt.Horizontal)
        root_layout.addWidget(splitter, 1)

        # ════════════ LEFT PANEL ════════════
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 4, 0)
        left_layout.setSpacing(4)

        self.step_title = QLabel("Step: 폴더를 선택하세요")
        self.step_title.setStyleSheet(f"font-size: 16pt; font-weight: bold; color: {ACCENT};")
        left_layout.addWidget(self.step_title)

        # --- Stat Cards ---
        cards = QHBoxLayout()
        self.card_x = StatCard("X Offset")
        self.card_y = StatCard("Y Offset")
        cards.addWidget(self.card_x)
        cards.addWidget(self.card_y)
        left_layout.addLayout(cards)

        btn_spec = QPushButton("⚙️ Spec 설정")
        btn_spec.clicked.connect(self._open_spec_config)
        left_layout.addWidget(btn_spec, alignment=Qt.AlignRight)

        # --- Bottom Tabs ---
        self.main_tabs = QTabWidget()
        left_layout.addWidget(self.main_tabs, 1)

        # Tab 1: System Log
        log_widget = QTextEdit()
        self.main_tabs.addTab(log_widget, "📝 시스템 로그")
        self.logger = SystemLogger(log_widget)

        # Tab 2: Data Table Hub
        data_widget = QWidget()
        data_layout = QVBoxLayout(data_widget)
        data_layout.setContentsMargins(0, 0, 0, 0)
        self.data_tabs = QTabWidget()
        data_layout.addWidget(self.data_tabs)

        # ── Die 필터 패널 ──
        die_filter_frame = QFrame()
        die_filter_frame.setStyleSheet(f"""
            QFrame {{ background: {BG2}; border: 1px solid {BG3};
                     border-radius: 4px; margin: 2px 4px; }}
        """)
        die_filter_layout = QVBoxLayout(die_filter_frame)
        die_filter_layout.setContentsMargins(8, 4, 8, 4)
        die_filter_layout.setSpacing(4)

        # 헤더 행: 타이틀 + 전체 선택 + 안정화 제외 + 정보
        filter_header = QHBoxLayout()
        filter_header.setSpacing(8)
        lbl_filter = QLabel("🎯 Die 필터")
        lbl_filter.setStyleSheet(f"color: {ACCENT}; font-size: 9pt; font-weight: bold; border: none;")
        filter_header.addWidget(lbl_filter)

        self.die_select_all_btn = QPushButton("✅ 전체 선택")
        self.die_select_all_btn.setFixedHeight(22)
        self.die_select_all_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {FG2}; border: none;
                          border-radius: 3px; padding: 0 8px; font-size: 8pt; }}
            QPushButton:hover {{ background: {ACCENT}; color: white; }}
        """)
        self.die_select_all_btn.clicked.connect(self._die_filter_select_all)
        filter_header.addWidget(self.die_select_all_btn)

        self.die_stab_btn = QPushButton("🚫 안정화 Die 제외")
        self.die_stab_btn.setFixedHeight(22)
        self.die_stab_btn.setToolTip(
            "처음 측정된 Die를 자동으로 체크 해제합니다.\n"
            "장비 안정화 목적으로 첫 Die를 이중 측정한 경우 사용하세요.")
        self.die_stab_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: #f38ba8; border: none;
                          border-radius: 3px; padding: 0 8px; font-size: 8pt; }}
            QPushButton:hover {{ background: #f38ba8; color: white; }}
        """)
        self.die_stab_btn.clicked.connect(self._die_filter_exclude_stabilization)
        filter_header.addWidget(self.die_stab_btn)

        self.filter_info_label = QLabel("")
        self.filter_info_label.setStyleSheet("color: #f9e2af; font-size: 8pt; border: none;")
        filter_header.addWidget(self.filter_info_label)
        filter_header.addStretch()
        die_filter_layout.addLayout(filter_header)

        # Die 체크박스 컨테이너 (동적으로 채워짐)
        self._die_cb_container = QWidget()
        self._die_cb_container.setStyleSheet("border: none;")
        self._die_cb_flow = FlowLayout(self._die_cb_container, margin=2, spacing=4)
        die_filter_layout.addWidget(self._die_cb_container)

        self._die_checkboxes = {}  # {die_num(0-based): QCheckBox}
        self._die_filter_updating = False  # 재진입 방지 플래그

        data_layout.addWidget(die_filter_frame)
        self.main_tabs.addTab(data_widget, "🗄️ 데이터 테이블")

        # Sub 1: Summary
        self.sum_table = CopyableTable()
        cols_s = ['Recipe', 'R', 'N', 'Mean', 'Stdev', 'Min', 'Max', 'CV%', 'Out', 'X', 'Y', '결과']
        self.sum_table.setColumnCount(len(cols_s))
        self.sum_table.setHorizontalHeaderLabels(cols_s)
        hdr = self.sum_table.horizontalHeader()
        for col in range(len(cols_s)):
            hdr.setSectionResizeMode(col, QHeaderView.Stretch)
        for col, width in [(1, 30), (8, 30), (9, 30), (10, 30), (11, 45)]:
            hdr.setSectionResizeMode(col, QHeaderView.Fixed)
            self.sum_table.setColumnWidth(col, width)
        self.data_tabs.addTab(self.sum_table, "📊 Summary")

        # Sub 2: Die 평균 (X/Y sub-tabs)
        die_widget = QWidget()
        die_layout = QVBoxLayout(die_widget)
        die_layout.setContentsMargins(0, 0, 0, 0)
        self.die_tabs = QTabWidget()
        die_layout.addWidget(self.die_tabs)
        self.die_x_table = CopyableTable()
        self.die_y_table = CopyableTable()
        self.die_tabs.addTab(self.die_x_table, "X Die Average")
        self.die_tabs.addTab(self.die_y_table, "Y Die Average")
        self.data_tabs.addTab(die_widget, "🔢 Die별 평균")

        # Sub 3: Raw Deviation (X/Y)
        dev_widget = QWidget()
        dev_layout = QVBoxLayout(dev_widget)
        dev_layout.setContentsMargins(0, 0, 0, 0)
        self.dev_tabs = QTabWidget()
        dev_layout.addWidget(self.dev_tabs)
        self.dev_x_table = CopyableTable()
        self.dev_y_table = CopyableTable()
        self.dev_tabs.addTab(self.dev_x_table, "X offset")
        self.dev_tabs.addTab(self.dev_y_table, "Y offset")
        self.data_tabs.addTab(dev_widget, "🔲 Raw Deviation")

        # Sub 4: Raw Data — 폴더 열기 버튼 포함
        raw_widget = QWidget()
        raw_layout = QVBoxLayout(raw_widget)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.setSpacing(2)

        # 폴더 열기 툴바
        tiff_bar2 = QHBoxLayout()
        btn_tiff_open = QPushButton("📂 TIFF 폴더 열기")
        btn_tiff_open.clicked.connect(self._open_tiff_folder)
        tiff_bar2.addWidget(btn_tiff_open)
        self.tiff_path_label = QLabel("더블클릭 → TIFF 로드")
        self.tiff_path_label.setStyleSheet(f"color: {FG2}; font-size: 8pt;")
        tiff_bar2.addWidget(self.tiff_path_label, 1)
        raw_bar_w = QWidget()
        raw_bar_w.setLayout(tiff_bar2)
        raw_layout.addWidget(raw_bar_w)

        self.raw_table = CopyableTable()
        cols_r = ['Lot', 'Site', 'Axis', 'HZ1_O', 'V', 'Out']
        self.raw_table.setColumnCount(len(cols_r))
        self.raw_table.setHorizontalHeaderLabels(cols_r)
        raw_hdr = self.raw_table.horizontalHeader()
        for col in range(len(cols_r)):
            raw_hdr.setSectionResizeMode(col, QHeaderView.Stretch)
        for col, width in [(4, 30), (5, 30)]:
            raw_hdr.setSectionResizeMode(col, QHeaderView.Fixed)
            self.raw_table.setColumnWidth(col, width)
        self.raw_table.cellDoubleClicked.connect(self._on_row_double_click)
        raw_layout.addWidget(self.raw_table, 1)
        self.data_tabs.addTab(raw_widget, "📄 원본 데이터")

        splitter.addWidget(left)

        # ════════════ RIGHT PANEL (2-Tier Grouped Tabs) ════════════
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(0)

        # ─── Outer Category Tabs ───
        self.chart_category_tabs = QTabWidget()
        right_layout.addWidget(self.chart_category_tabs)

        self.chart_widgets = {}
        self._inner_tabs = {}  # category_name → inner QTabWidget

        def _add_chart(category, name, widget, register=True):
            if category not in self._inner_tabs:
                inner = QTabWidget()
                inner.setDocumentMode(True)
                self._inner_tabs[category] = inner
                self.chart_category_tabs.addTab(inner, category)
            self._inner_tabs[category].addTab(widget, name)
            if register:
                self.chart_widgets[name] = widget

        # Contour X/Y — Repeat Contour 버튼을 컨테이너에 포함하여 차트 짤림 방지
        _contour_help = (
            "Contour Map 색상 안내\n\n"
            "색상은 편차의 ± 방향을 나타냅니다:\n"
            "  🟢 초록 = 양(+) 방향 오프셋\n"
            "  🟡 노랑 = 0 근처 (편차 없음)\n"
            "  🔴 빨강 = 음(−) 방향 오프셋\n\n"
            "• 색상 대비가 클수록 공간적 편향 존재\n"
            "• 한쪽 빨강 ↔ 반대쪽 초록 = Stage Tilt\n"
            "• 전체가 한 색으로 치우침 = Translation Offset\n\n"
            "💡 Raw Deviation 테이블은 |절대값| 기준이므로\n"
            "   색상이 다를 수 있습니다 (크기 vs 방향)")
        for axis_name in ('Contour X', 'Contour Y'):
            axis = 'X' if 'X' in axis_name else 'Y'
            container = QWidget()
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(2)

            toolbar_row = QHBoxLayout()
            toolbar_row.setContentsMargins(8, 4, 8, 0)
            btn = QPushButton(f"🗺️ Repeat별 Contour ({axis})")
            btn.clicked.connect(partial(self._open_repeat_contour, axis))
            toolbar_row.addWidget(btn)

            help_btn = QPushButton("?")
            help_btn.setFixedSize(22, 22)
            help_btn.setCursor(Qt.WhatsThisCursor)
            help_btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {FG2};
                              border: 1px solid #585b70; border-radius: 11px;
                              font-size: 10pt; font-weight: bold; }}
                QPushButton:hover {{ background: {BG3}; color: {ACCENT}; }}
            """)
            help_btn.setToolTip(_contour_help)
            help_btn.clicked.connect(
                lambda checked=False, b=help_btn, t=_contour_help:
                    QToolTip.showText(b.mapToGlobal(
                        b.rect().bottomLeft()), t, b, b.rect(), 10000))
            toolbar_row.addWidget(help_btn)
            toolbar_row.addStretch()
            container_layout.addLayout(toolbar_row)

            cw = ChartWidget()
            container_layout.addWidget(cw, 1)
            self.chart_widgets[axis_name] = cw
            _add_chart('기본 분석', axis_name, container, register=False)

        for name in ['X*Y Offset', 'Die Position']:
            _add_chart('기본 분석', name, ChartWidget())

        # Vector Map (슬라이더 컨트롤 포함)
        vm_container = QWidget()
        vm_layout = QVBoxLayout(vm_container)
        vm_layout.setContentsMargins(0, 0, 0, 0)
        vm_layout.setSpacing(2)

        # 슬라이더 바
        slider_bar = QHBoxLayout()
        slider_bar.setContentsMargins(8, 4, 8, 0)
        lbl_icon = QLabel("📏")
        lbl_icon.setStyleSheet(f"color: {FG2}; font-size: 10pt;")
        slider_bar.addWidget(lbl_icon)
        lbl_title = QLabel("화살표 배율:")
        lbl_title.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        slider_bar.addWidget(lbl_title)

        self.vector_scale_slider = QSlider(Qt.Horizontal)
        self.vector_scale_slider.setRange(5, 50)  # 5% ~ 50%
        self.vector_scale_slider.setValue(10)      # 기본 10%
        self.vector_scale_slider.setTickPosition(QSlider.TicksBelow)
        self.vector_scale_slider.setTickInterval(5)
        self.vector_scale_slider.setFixedWidth(200)
        self.vector_scale_slider.setStyleSheet(f"""
            QSlider::groove:horizontal {{
                background: {BG3}; height: 6px; border-radius: 3px;
            }}
            QSlider::handle:horizontal {{
                background: {ACCENT}; width: 14px; height: 14px;
                margin: -4px 0; border-radius: 7px;
            }}
            QSlider::sub-page:horizontal {{
                background: {ACCENT}; border-radius: 3px;
            }}
        """)
        slider_bar.addWidget(self.vector_scale_slider)

        self.vector_scale_label = QLabel("10%")
        self.vector_scale_label.setFixedWidth(35)
        self.vector_scale_label.setStyleSheet(f"color: {FG}; font-size: 9pt; font-weight: bold;")
        slider_bar.addWidget(self.vector_scale_label)

        _help_text = (
            "화살표 배율 (기본 10%)\n\n"
            "• 값이 클수록 화살표가 길어집니다\n"
            "• 10% = 최대 편차 벡터가 웨이퍼 반경의 10% 길이\n"
            "• 작은 편차가 잘 안 보이면 배율을 높이세요\n\n"
            "예) 300mm 웨이퍼, 10% → 최대 화살표 ≈ 15,000µm\n"
            "예) 300mm 웨이퍼, 30% → 최대 화살표 ≈ 45,000µm")
        help_btn = QPushButton("?")
        help_btn.setFixedSize(22, 22)
        help_btn.setCursor(Qt.WhatsThisCursor)
        help_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {FG2};
                          border: 1px solid #585b70; border-radius: 11px;
                          font-size: 10pt; font-weight: bold; }}
            QPushButton:hover {{ background: {BG3}; color: {ACCENT}; }}
        """)
        help_btn.setToolTip(_help_text)
        help_btn.clicked.connect(
            lambda: QToolTip.showText(help_btn.mapToGlobal(
                help_btn.rect().bottomLeft()), _help_text, help_btn, help_btn.rect(), 8000))
        slider_bar.addWidget(help_btn)
        slider_bar.addStretch()

        vm_layout.addLayout(slider_bar)

        # Chart area
        self._vector_chart = ChartWidget()
        vm_layout.addWidget(self._vector_chart, 1)
        self.chart_widgets['↗️ Vector Map'] = self._vector_chart

        self.vector_scale_slider.valueChanged.connect(self._on_vector_scale_changed)

        _add_chart('기본 분석', '↗️ Vector Map', vm_container, register=False)

        # 인터랙티브 (pyqtgraph)
        # ─── 📈 Lot 트렌드: 컨테이너 (Lot 필터 + 차트) ───
        lot_trend_container = QWidget()
        lt_layout = QVBoxLayout(lot_trend_container)
        lt_layout.setContentsMargins(0, 0, 0, 0)
        lt_layout.setSpacing(2)

        # 도움말 + 필터 버튼 행
        lt_toolbar = QHBoxLayout()
        lt_toolbar.setContentsMargins(8, 4, 8, 0)

        _lot_trend_help = (
            "Lot 트렌드 차트 가이드\n\n"
            "그래프 요소:\n"
            "  🔵 파란 실선 (●) = Lot별 Mean (평균 오프셋)\n"
            "  🟢 초록 점선 (▲) = Lot별 Max (최대값)\n"
            "  🔴 빨강 점선 (▼) = Lot별 Min (최소값)\n"
            "  ░░ 반투명 밴드   = Mean ± 1σ (표준편차 범위)\n"
            "  --- 회색 점선     = Overall Mean (전체 평균)\n\n"
            "패턴 해석:\n"
            "  📈 우상향  = Lot 진행 시 오프셋 증가 (드리프트)\n"
            "  📉 우하향  = 오프셋 감소 (자동 보정 의심)\n"
            "  ➡️ 수평   = 안정적 (정상)\n"
            "  🔀 지그재그 = 불안정 (재현성 점검 필요)\n\n"
            "Lot 필터:\n"
            "  • 체크 해제 → 해당 Lot 제외 후 트렌드 재계산\n"
            "  • [이상 Lot 제외] 장비 이상 Lot를 빼고 추세 확인\n"
            "  • [범위 지정] 처음 N개 / 마지막 N개 구간 비교")

        lt_help_btn = QPushButton("?")
        lt_help_btn.setFixedSize(22, 22)
        lt_help_btn.setCursor(Qt.WhatsThisCursor)
        lt_help_btn.setStyleSheet(f"""
            QPushButton {{ background: transparent; color: {FG2};
                          border: 1px solid #585b70; border-radius: 11px;
                          font-size: 10pt; font-weight: bold; }}
            QPushButton:hover {{ background: {BG3}; color: {ACCENT}; }}
        """)
        lt_help_btn.setToolTip(_lot_trend_help)
        lt_help_btn.clicked.connect(
            lambda checked=False, b=lt_help_btn, t=_lot_trend_help:
                QToolTip.showText(b.mapToGlobal(
                    b.rect().bottomLeft()), t, b, b.rect(), 10000))
        lt_toolbar.addWidget(lt_help_btn)

        lt_lbl = QLabel("🎯 Lot 필터")
        lt_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 9pt; font-weight: bold;")
        lt_toolbar.addWidget(lt_lbl)

        self._lot_select_all_btn = QPushButton("✅ 전체 선택")
        self._lot_select_all_btn.setFixedHeight(22)
        self._lot_select_all_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {FG2}; border: none;
                          border-radius: 3px; padding: 0 8px; font-size: 8pt; }}
            QPushButton:hover {{ background: {ACCENT}; color: white; }}
        """)
        self._lot_select_all_btn.clicked.connect(self._lot_filter_select_all)
        lt_toolbar.addWidget(self._lot_select_all_btn)

        self._lot_range_btn = QPushButton("📐 범위 지정")
        self._lot_range_btn.setFixedHeight(22)
        self._lot_range_btn.setToolTip(
            "표시할 Lot 범위를 지정합니다.\n"
            "예: 1-5 (처음 5개), -3 (마지막 3개)")
        self._lot_range_btn.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {ORANGE}; border: none;
                          border-radius: 3px; padding: 0 8px; font-size: 8pt; }}
            QPushButton:hover {{ background: {ORANGE}; color: white; }}
        """)
        self._lot_range_btn.clicked.connect(self._lot_filter_range)
        lt_toolbar.addWidget(self._lot_range_btn)

        self._lot_filter_info = QLabel("")
        self._lot_filter_info.setStyleSheet("color: #f9e2af; font-size: 8pt;")
        lt_toolbar.addWidget(self._lot_filter_info)
        lt_toolbar.addStretch()
        lt_layout.addLayout(lt_toolbar)

        # Lot 체크박스 컨테이너
        self._lot_cb_container = QWidget()
        self._lot_cb_container.setStyleSheet(f"background: {BG2}; border-radius: 4px;")
        self._lot_cb_flow = FlowLayout(self._lot_cb_container, margin=2, spacing=4)
        lt_layout.addWidget(self._lot_cb_container)

        # 트렌드 차트 위젯
        self._lot_trend_chart = InteractiveChartWidget()
        lt_layout.addWidget(self._lot_trend_chart, 1)
        self.chart_widgets['📈 Lot 트렌드'] = self._lot_trend_chart
        _add_chart('인터랙티브', '📈 Lot 트렌드', lot_trend_container, register=False)

        _add_chart('인터랙티브', '🎯 XY Scatter', InteractiveChartWidget())

        # ─── 📊 분포: X/Y 서브탭 ───
        dist_tabs = QTabWidget()
        dist_tabs.setDocumentMode(True)
        dist_x = InteractiveChartWidget()
        dist_y = InteractiveChartWidget()
        dist_tabs.addTab(dist_x, 'X')
        dist_tabs.addTab(dist_y, 'Y')
        self.chart_widgets['📊 분포 X'] = dist_x
        self.chart_widgets['📊 분포 Y'] = dist_y
        _add_chart('인터랙티브', '📊 분포', dist_tabs, register=False)

        # TIFF
        tiff_cw = InteractiveChartWidget()
        tiff_viewer = viz_pg.create_tiff_widget()
        tiff_cw.set_widget(tiff_viewer)
        _add_chart('인터랙티브', '🔬 TIFF', tiff_cw)
        self._tiff_viewer = tiff_viewer

        # 고급 분석 (pyqtgraph — Phase 2)
        for name in ['🔍 Pareto', '🔗 Correlation']:
            _add_chart('고급 분석', name, InteractiveChartWidget())

        # ─── 🌐 3D Surface: X/Y 서브탭 ───
        surface_tabs = QTabWidget()
        surface_tabs.setDocumentMode(True)
        surface_x = InteractiveChartWidget()
        surface_y = InteractiveChartWidget()
        surface_tabs.addTab(surface_x, 'X')
        surface_tabs.addTab(surface_y, 'Y')
        self.chart_widgets['🌐 3D X'] = surface_x
        self.chart_widgets['🌐 3D Y'] = surface_y
        _add_chart('고급 분석', '🌐 3D Surface', surface_tabs, register=False)

        # 비교 (matplotlib — Recipe Comparison: 3개 서브탭)
        for name in ['📊 Boxplot', '📈 Trend', '🗺️ Heatmap']:
            _add_chart('비교', name, ChartWidget())

        # 📤 Export 탭
        export_widget = QWidget()
        export_layout = QVBoxLayout(export_widget)
        export_layout.setContentsMargins(40, 40, 40, 40)
        export_layout.setSpacing(16)

        export_header = QLabel("📤 데이터 내보내기")
        export_header.setStyleSheet(f"color:{ACCENT}; font-size:16pt; font-weight:bold;")
        export_header.setAlignment(Qt.AlignCenter)
        export_layout.addWidget(export_header)

        export_desc = QLabel("분석 결과를 다양한 형식으로 내보낼 수 있습니다.")
        export_desc.setStyleSheet(f"color:{FG2}; font-size:10pt;")
        export_desc.setAlignment(Qt.AlignCenter)
        export_layout.addWidget(export_desc)

        export_layout.addSpacing(10)

        export_buttons_data = [
            ('📊 Excel 내보내기', 'Die별 편차, Summary, Raw Data 등\n전체 데이터를 Excel 파일로 저장', self._export_excel, ACCENT),
            ('💾 CSV 내보내기', 'Raw Data를 CSV 형식으로 저장\n타 프로그램에서 불러오기 용이', self._export_csv, GREEN),
            ('📄 PDF 보고서', '차트 + 통계 포함 PDF 보고서 생성\n출력 및 공유용', self._export_pdf, RED),
        ]
        for text, desc, slot, color in export_buttons_data:
            btn = QPushButton(f"{text}")
            btn.setMinimumHeight(60)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {BG3}; color: {FG};
                    border: 1px solid {color}40; border-left: 4px solid {color};
                    border-radius: 6px; font-size: 12pt; font-weight: bold;
                    text-align: left; padding: 12px 20px;
                }}
                QPushButton:hover {{ background: #45475a; border-color: {color}; }}
            """)
            btn.setToolTip(desc)
            btn.clicked.connect(slot)
            export_layout.addWidget(btn)

            desc_label = QLabel(f"    {desc.split(chr(10))[0]}")
            desc_label.setStyleSheet(f"color:{FG2}; font-size:8pt; margin-bottom:4px;")
            export_layout.addWidget(desc_label)

        export_layout.addStretch()

        # Export 카테고리로 등록 (단일 페이지 — 내부 탭 없음)
        inner_export = QTabWidget()
        inner_export.setDocumentMode(True)
        inner_export.addTab(export_widget, '내보내기')
        self._inner_tabs['📤 Export'] = inner_export
        self.chart_category_tabs.addTab(inner_export, '📤 Export')

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)
        splitter.setSizes([960, 960])  # 초기 5:5 비율

        # ─── 좌측 패널 토글 (F11 + 스플리터 더블클릭) ───
        self._main_splitter = splitter
        self._left_panel = left
        self._saved_splitter_sizes = None

        shortcut = QShortcut(QKeySequence('F11'), self)
        shortcut.activated.connect(self._toggle_left_panel)
        splitter.handle(1).installEventFilter(self)

        # Render die position immediately
        QTimer.singleShot(200, self._render_die_position)

        # Boot log
        QTimer.singleShot(50, lambda: self.logger.head("XY Stage Offset Analyzer v8.0 시작"))
        QTimer.singleShot(100, lambda: self.logger.info(
            "폴더를 선택하고 '스캔 & 분석'을 눌러주세요."))

        # Status bar
        self.statusBar().showMessage("폴더를 선택하세요.")

    # ──────────────────────────────────────────────
    # Chart Navigation
    # ──────────────────────────────────────────────
    def _select_chart(self, name: str):
        """프로그래밍 방식으로 차트 선택 (카테고리 + 내부 탭 자동 전환)."""
        for cat_name, inner_tab in self._inner_tabs.items():
            for i in range(inner_tab.count()):
                if inner_tab.tabText(i) == name:
                    self.chart_category_tabs.setCurrentWidget(inner_tab)
                    inner_tab.setCurrentIndex(i)
                    return

    def _toggle_left_panel(self):
        """좌측 패널 접기/펼치기 (F11)."""
        sizes = self._main_splitter.sizes()
        if sizes[0] > 0:
            self._saved_splitter_sizes = sizes
            self._main_splitter.setSizes([0, sum(sizes)])
        else:
            if self._saved_splitter_sizes:
                self._main_splitter.setSizes(self._saved_splitter_sizes)
            else:
                total = sum(sizes)
                self._main_splitter.setSizes([total // 2, total // 2])

    def eventFilter(self, obj, event):
        """스플리터 핸들 더블클릭 → 좌측 패널 토글."""
        from PySide6.QtCore import QEvent
        if (hasattr(self, '_main_splitter')
                and obj is self._main_splitter.handle(1)
                and event.type() == QEvent.MouseButtonDblClick):
            self._toggle_left_panel()
            return True
        return super().eventFilter(obj, event)

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────
    def closeEvent(self, event):
        self._save_settings()
        import matplotlib.pyplot as plt
        plt.close('all')
        event.accept()

    def _save_settings(self):
        self.settings['last_folder'] = self.path_edit.text()
        geom = self.geometry()
        self.settings['window_geometry'] = f"{geom.width()}x{geom.height()}+{geom.x()}+{geom.y()}"
        save_settings(self.settings)

    def _restore_settings(self):
        if self.folder_path and os.path.isdir(self.folder_path):
            self.path_edit.setText(self.folder_path)
            QTimer.singleShot(100, self._scan_folder)

    # ──────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────
    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Root Data 폴더 선택", self.path_edit.text() or "")
        if path:
            self.path_edit.setText(path)
            self._scan_folder()

    def _scan_folder(self):
        folder = self.path_edit.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "경고", "유효한 폴더를 선택해주세요.")
            return

        self.main_tabs.setCurrentIndex(0)
        self.logger.section("폴더 스캔 시작")
        self.logger.info(f"경로: {folder}")
        self.statusBar().showMessage("스캔 중...")

        self.recipes = scan_recipes(folder)
        if not self.recipes:
            self.logger.warn("Recipe 구조를 찾지 못했습니다.")
            QMessageBox.information(self, "알림", "Recipe 구조를 찾지 못했습니다.")
            return

        # ─── 표준 Recipe 이름 검증 ───
        std_names = self.settings.get('standard_recipe_names', [])
        if std_names:
            detected = [r['short_name'] for r in self.recipes]
            mismatched = []
            for d in detected:
                if not any(std.lower() in d.lower() or d.lower() in std.lower()
                           for std in std_names):
                    mismatched.append(d)

            if mismatched:
                std_list = '\n'.join(f"  • {s}" for s in std_names)
                det_list = '\n'.join(f"  • {d}" for d in detected)
                mis_list = '\n'.join(f"  ⚠ {m}" for m in mismatched)
                reply = QMessageBox.warning(
                    self, "⚠ Recipe 이름 불일치",
                    f"표준 Recipe 이름과 일치하지 않는 항목이 있습니다.\n\n"
                    f"【표준 이름】\n{std_list}\n\n"
                    f"【감지된 이름】\n{det_list}\n\n"
                    f"【불일치 항목】\n{mis_list}\n\n"
                    f"계속 진행하시겠습니까?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes)
                if reply == QMessageBox.No:
                    self.logger.warn("사용자가 스캔을 취소했습니다 (Recipe 이름 불일치).")
                    return

        self.logger.ok(f"✅ {len(self.recipes)}개 Recipe 발견")
        for r in self.recipes:
            self.logger.info(f"  Step {r['index']}: {r['name']}")

        self.settings = add_recent_folder(self.settings, folder)
        self._save_settings()
        self._build_nav()

        self.logger.info("전체 Recipe 데이터 로드 시작 (1st round)...")
        self._loader_thread = DataLoaderThread(folder)
        self._loader_thread.finished.connect(self._on_scan_complete)
        self._loader_thread.error.connect(
            lambda e: (self.logger.error(f"로드 오류: {e}"),
                       QMessageBox.critical(self, "오류", e)))
        self._loader_thread.start()

    def _on_scan_complete(self, results, comparison, elapsed):
        self.recipe_results = results
        total = sum(len(r.get('raw_data', [])) for r in results)
        self.logger.ok(f"✅ 전체 로드 완료: {total}개 데이터 ({elapsed:.1f}초 소요)")
        self._update_summary_table(comparison, results)

        # 모든 Step Pass/Fail 일괄 계산 → 버튼 색상 즉시 반영
        self._compute_all_step_pass_states()

        # Affine Transform
        self.logger.section("Affine Transform 계통 오차 분석")
        for i, result in enumerate(self.recipe_results):
            data = result.get('raw_data', [])
            dx = compute_deviation_matrix(data, 'X')
            dy = compute_deviation_matrix(data, 'Y')
            if dx['die_stats'] and dy['die_stats']:
                af = compute_affine_transform(dx['die_stats'], dy['die_stats'])
                name = result.get('short_name', f'Step {i+1}')
                self.logger.head(f"[{name}]")
                self.logger.info(f"  Translation: Tx={af['tx']:+.4f} µm, Ty={af['ty']:+.4f} µm")
                self.logger.info(f"  Scaling: Sx={af['sx_ppm']:+.2f} ppm, Sy={af['sy_ppm']:+.2f} ppm")
                self.logger.info(f"  Rotation: θ={af['theta_deg']:+.6f}° ({af['theta_urad']:+.2f} µrad)")
                self.logger.info(f"  Residual RMS: X={af['residual_x']:.4f}, Y={af['residual_y']:.4f}")

        self.main_tabs.setCurrentIndex(1)
        self.data_tabs.setCurrentIndex(0)
        if self.recipe_results:
            self._select_step(0)

        # ─── Recipe 비교 차트 렌더링 ───
        if len(self.recipe_results) >= 2:
            try:
                self.chart_widgets['📊 Boxplot'].set_figure(
                    viz.plot_recipe_comparison_boxplot(self.recipe_results))
                self.logger.ok("📊 Recipe Boxplot 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Boxplot 비교 오류: {e}")

            try:
                self.chart_widgets['📈 Trend'].set_figure(
                    viz.plot_recipe_comparison_trend(self.recipe_results))
                self.logger.ok("📈 Recipe Trend 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Trend 비교 오류: {e}")

            try:
                self.chart_widgets['🗺️ Heatmap'].set_figure(
                    viz.plot_recipe_comparison_heatmap(self.recipe_results))
                self.logger.ok("🗺️ Recipe Heatmap 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Heatmap 비교 오류: {e}")

        self.statusBar().showMessage(
            f"✅ {len(self.recipes)}개 Recipe | {total}개 데이터 | Step 클릭 → 상세 분석")

    def _build_nav(self):
        while self.nav_layout.count():
            w = self.nav_layout.takeAt(0).widget()
            if w:
                w.deleteLater()
        self.step_buttons.clear()
        self.step_pass_states = {}

        lbl = QLabel("Workflow:")
        lbl.setStyleSheet("font-size: 10pt;")
        self.nav_layout.addWidget(lbl)

        for i, r in enumerate(self.recipes):
            btn = QPushButton(f"Step {r['index']}: {r['short_name']}")
            btn.setProperty("step", True)
            btn.clicked.connect(partial(self._select_step, i))
            self.nav_layout.addWidget(btn)
            self.step_buttons.append(btn)
            if i < len(self.recipes) - 1:
                sep = QLabel(" ▶ ")
                sep.setStyleSheet(f"color: {FG2};")
                self.nav_layout.addWidget(sep)
        self.nav_layout.addStretch()

    def _compute_all_step_pass_states(self):
        """scan complete 후 모든 Step Pass/Fail 일괄 계산 후 버튼 색상 즉시 반영."""
        dev_spec = self.settings.get('spec_deviation', {})
        for i, result in enumerate(self.recipe_results):
            data = result.get('raw_data', [])
            short = result.get('short_name', '')
            ds = dev_spec.get(short, {})
            spec_r = ds.get('spec_range')
            spec_s = ds.get('spec_stddev')
            if not data:
                self.step_pass_states[i] = None
                continue
            dx = compute_deviation_matrix(data, 'X')
            dy = compute_deviation_matrix(data, 'Y')
            sx = compute_statistics(filter_by_method(data, 'X'))
            sy = compute_statistics(filter_by_method(data, 'Y'))
            px = (dx['overall_range'] <= spec_r and dx['overall_stddev'] <= spec_s) if (sx['count'] > 0 and spec_r is not None) else None
            py = (dy['overall_range'] <= spec_r and dy['overall_stddev'] <= spec_s) if (sy['count'] > 0 and spec_r is not None) else None
            if px is None or py is None:
                self.step_pass_states[i] = None
            else:
                self.step_pass_states[i] = px and py
        self._refresh_step_buttons()

    def _select_step(self, idx):
        if idx < 0 or idx >= len(self.recipes):
            return
        self.current_recipe_idx = idx
        for i, btn in enumerate(self.step_buttons):
            is_pass = self.step_pass_states.get(i)  # True/False/None
            # Active step: always accent regardless of pass/fail
            if i == idx:
                btn.setProperty("active_step", True)
                btn.setProperty("step", False)
                btn.setProperty("step_pass", False)
                btn.setProperty("step_fail", False)
            elif is_pass is True:
                btn.setProperty("active_step", False)
                btn.setProperty("step", False)
                btn.setProperty("step_pass", True)
                btn.setProperty("step_fail", False)
            elif is_pass is False:
                btn.setProperty("active_step", False)
                btn.setProperty("step", False)
                btn.setProperty("step_pass", False)
                btn.setProperty("step_fail", True)
            else:  # None = not yet analyzed
                btn.setProperty("active_step", False)
                btn.setProperty("step", True)
                btn.setProperty("step_pass", False)
                btn.setProperty("step_fail", False)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

        recipe = self.recipes[idx]
        self.step_title.setText(f"Step {recipe['index']}: {recipe['name']}")
        self.logger.info(f"Step 전환 → {recipe['name']}")

        if idx < len(self.recipe_results) and self.recipe_results[idx].get('raw_data'):
            result = self.recipe_results[idx]
            self.raw_data = result.get('raw_data', [])
            # 실제 측정 데이터에서 Die 좌표 추출
            self._dynamic_die_positions = extract_die_positions(self.raw_data)
            rd1 = next((rd for rd in recipe.get('rounds', []) if rd['name'] == '1st'), None)
            if rd1:
                self.lot_list = scan_lot_folders(rd1['path'])
            self._display_result(result, recipe)
        else:
            self.statusBar().showMessage(f"데이터 로드 중: {recipe['short_name']}...")

    # ──────────────────────────────────────────────
    # Display Result
    # ──────────────────────────────────────────────
    def _display_result(self, result, recipe):
        raw = result.get('raw_data', [])

        # Die 체크박스 동적 생성 (첫 호출 or Step 전환 시)
        from analyzer import extract_die_number
        from visualizer import _color_from_die
        die_nums_in_data = sorted(set(
            extract_die_number(r.get('site_id', ''))
            for r in raw if extract_die_number(r.get('site_id', '')) is not None))

        if set(die_nums_in_data) != set(self._die_checkboxes.keys()):
            # 기존 체크박스 제거
            while self._die_cb_flow.count():
                item = self._die_cb_flow.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            self._die_checkboxes.clear()

            # 새 체크박스 생성
            for d in die_nums_in_data:
                cb = QCheckBox(f"Die {d + 1}")
                cb.setChecked(True)
                color = _color_from_die(d)
                # matplotlib color (0-1 float) → hex
                r_c, g_c, b_c = [int(c * 255) for c in color[:3]]
                hex_c = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
                cb.setStyleSheet(f"""
                    QCheckBox {{ color: {hex_c}; font-size: 8pt; font-weight: bold; border: none; }}
                    QCheckBox::indicator {{ width: 12px; height: 12px; }}
                    QCheckBox::indicator:unchecked {{ border: 1px solid #585b70; border-radius: 2px;
                                                     background: {BG2}; }}
                    QCheckBox::indicator:checked {{ border: 1px solid {hex_c}; border-radius: 2px;
                                                   background: {hex_c}; }}
                """)
                cb.stateChanged.connect(self._on_die_filter_changed)
                self._die_cb_flow.addWidget(cb)
                self._die_checkboxes[d] = cb

        # 필터 적용: 체크 해제된 Die 제외
        excluded = {d for d, cb in self._die_checkboxes.items() if not cb.isChecked()}
        if excluded:
            data = [r for r in raw
                    if extract_die_number(r.get('site_id', '')) not in excluded]
            excluded_names = ', '.join(f'Die {d + 1}' for d in sorted(excluded))
            count_removed = len(raw) - len(data)
            self.filter_info_label.setText(
                f"⚠ {excluded_names} 제외  |  "
                f"{count_removed}개 제거 → {len(data)}개 분석 중 "
                f"(전체 {len(raw)}개)")
        else:
            data = raw
            self.filter_info_label.setText(f"✅ 전체 Die 분석 중 ({len(raw)}개)")

        self._update_cards(data, recipe)
        self._update_die_avg_tables()    # self._dev_x/y 기반 → Die 필터 적용됨
        self._update_deviation_tables()  # self._dev_x/y 기반 → Die 필터 적용됨
        self._update_raw_table()         # self.raw_data 기반 → Die 필터 미적용 (전체 표시)
        self._update_charts(data, result, recipe)
        self._render_die_position()
        stats = result.get('statistics', {})
        self.statusBar().showMessage(
            f"Step {recipe['index']}: {recipe['short_name']} — "
            f"{len(data)}개 ({len(excluded)}개 Die 제외) | "
            f"이상치: {result.get('outlier_count', 0)}  💡 행 더블클릭 → TIFF")

    def _refresh_step_buttons(self):
        """Step 버튼 색상만 갱신 (재귀 없이). _update_cards에서 호출."""
        active = self.current_recipe_idx
        for i, btn in enumerate(self.step_buttons):
            is_pass = self.step_pass_states.get(i)
            has_data = i in self.step_pass_states  # 한번이라도 계산됐으면 True

            # 모든 property 초기화
            for prop in ('active_step', 'step', 'step_pass', 'step_fail',
                         'step_active_pass', 'step_active_fail'):
                btn.setProperty(prop, False)

            if i == active:
                # 활성 Step: Pass/Fail 색상 + 흰 테두리
                if not has_data:
                    btn.setProperty('active_step', True)   # 파란색 + 흰 테두리
                elif is_pass is True:
                    btn.setProperty('step_active_pass', True)  # 초록 + 흰 테두리
                elif is_pass is False:
                    btn.setProperty('step_active_fail', True)  # 빨간 + 흰 테두리
                else:
                    btn.setProperty('active_step', True)   # 파란색 + 흰 테두리
            else:
                # 비활성 Step: Pass/Fail만 표시
                if not has_data:
                    btn.setProperty('step', True)      # 파란색
                elif is_pass is True:
                    btn.setProperty('step_pass', True) # 초록색
                elif is_pass is False:
                    btn.setProperty('step_fail', True) # 빨간색
                else:
                    btn.setProperty('step', True)      # 파란색

            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def _update_cards(self, data, recipe):
        d_x = filter_by_method(data, 'X')
        d_y = filter_by_method(data, 'Y')
        s_x = compute_statistics(d_x)
        s_y = compute_statistics(d_y)
        dev_x = compute_deviation_matrix(data, 'X')
        dev_y = compute_deviation_matrix(data, 'Y')
        self._dev_x, self._dev_y = dev_x, dev_y

        spec = self.settings.get('spec_limits', {})
        short = recipe.get('short_name', '')
        sp = spec.get(short, {})
        if not sp:
            self.logger.warning(f"spec_limits에 '{short}' 키 없음 → Cpk 계산 불가")
            sp = {'X': {}, 'Y': {}}
        cpk_x = compute_cpk(s_x['mean'], s_x['stdev'],
                            sp.get('X', {}).get('lsl', -5000), sp.get('X', {}).get('usl', 5000))
        cpk_y = compute_cpk(s_y['mean'], s_y['stdev'],
                            sp.get('Y', {}).get('lsl', -5000), sp.get('Y', {}).get('usl', 5000))

        dev_spec = self.settings.get('spec_deviation', {})
        ds = dev_spec.get(short, {})
        if not ds:
            self.logger.warning(f"spec_deviation에 '{short}' 키 없음 → PASS/FAIL 판정 불가")
        spec_r = ds.get('spec_range')
        spec_s = ds.get('spec_stddev')

        def _pass(st, dev):
            if st['count'] == 0 or spec_r is None or spec_s is None:
                return None
            return dev['overall_range'] <= spec_r and dev['overall_stddev'] <= spec_s

        px = _pass(s_x, dev_x)
        py = _pass(s_y, dev_y)
        self.card_x.update_stats(s_x['mean'], dev_x['overall_range'],
                                 dev_x['overall_stddev'], cpk_x, px,
                                 spec_r=spec_r, spec_s=spec_s)
        self.card_y.update_stats(s_y['mean'], dev_y['overall_range'],
                                 dev_y['overall_stddev'], cpk_y, py,
                                 spec_r=spec_r, spec_s=spec_s)

        # Store pass state and refresh nav buttons (no recursion)
        idx = self.current_recipe_idx
        if px is not None and py is not None:
            overall = px and py
        else:
            overall = None
        self.step_pass_states[idx] = overall
        self._refresh_step_buttons()

    # ──────────────────────────────────────────────
    # Tables
    # ──────────────────────────────────────────────
    def _update_summary_table(self, comparison, recipe_results=None):
        from analyzer import (compute_deviation_matrix, compute_statistics,
                              filter_by_method)
        t = self.sum_table
        t.setRowCount(0)

        recipe_results = recipe_results or []
        dev_spec = self.settings.get('spec_deviation', {})

        for i, c in enumerate(comparison):
            row = t.rowCount()
            t.insertRow(row)

            # 기본 통계 컬럼
            vals = [c.get('recipe', ''), c.get('round', ''), str(c.get('data_count', 0)),
                    f"{c.get('mean', 0):.1f}", f"{c.get('stdev', 0):.1f}",
                    f"{c.get('min', 0):.1f}", f"{c.get('max', 0):.1f}",
                    f"{c.get('cv_percent', 0):.1f}", str(c.get('outliers', 0))]
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                t.setItem(row, col, item)

            # X/Y Pass/Fail 계산
            px, py = None, None
            if i < len(recipe_results):
                result = recipe_results[i]
                data = result.get('raw_data', [])
                recipe_name = c.get('recipe', '')
                ds = dev_spec.get(recipe_name, {})
                spec_r = ds.get('spec_range')
                spec_s = ds.get('spec_stddev')
                if data:
                    dx = compute_deviation_matrix(data, 'X')
                    dy = compute_deviation_matrix(data, 'Y')
                    sx = compute_statistics(filter_by_method(data, 'X'))
                    sy = compute_statistics(filter_by_method(data, 'Y'))
                    if sx['count'] > 0 and spec_r is not None:
                        px = dx['overall_range'] <= spec_r and dx['overall_stddev'] <= spec_s
                    if sy['count'] > 0 and spec_r is not None:
                        py = dy['overall_range'] <= spec_r and dy['overall_stddev'] <= spec_s

            # Pass/Fail 셀 (X, Y) — 기호만 표시
            for col_offset, flag in enumerate([px, py]):
                if flag is None:
                    item = QTableWidgetItem('—')
                    item.setBackground(QColor(BG3))
                elif flag:
                    item = QTableWidgetItem('✅')
                    item.setBackground(QColor(GREEN))
                    item.setForeground(QColor(BG))
                else:
                    item = QTableWidgetItem('❌')
                    item.setBackground(QColor(RED))
                    item.setForeground(QColor(BG))
                item.setTextAlignment(Qt.AlignCenter)
                t.setItem(row, 9 + col_offset, item)

            # 종합 결과 — 텍스트만 (배경색으로 구분)
            if px is None or py is None:
                overall_text, overall_bg, overall_fg = '—', QColor(BG3), QColor(FG2)
            elif px and py:
                overall_text, overall_bg, overall_fg = 'PASS', QColor(GREEN), QColor(BG)
            else:
                overall_text, overall_bg, overall_fg = 'FAIL', QColor(RED), QColor(BG)
            item_o = QTableWidgetItem(overall_text)
            item_o.setBackground(overall_bg)
            item_o.setForeground(overall_fg)
            item_o.setTextAlignment(Qt.AlignCenter)
            t.setItem(row, 11, item_o)


    def _fill_die_avg_heatmap(self, table: CopyableTable, die_stats: list):
        table.clear()
        headers = ['Die', 'Avg (µm)', 'StdDev', 'Range']
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        if not die_stats:
            table.setRowCount(1)
            table.setItem(0, 0, QTableWidgetItem("No data"))
            return

        table.setRowCount(len(die_stats))
        avgs = [ds['avg'] for ds in die_stats]
        stds = [ds['stddev'] for ds in die_stats]
        rngs = [ds['range'] for ds in die_stats]
        avg_max = max(abs(v) for v in avgs) if avgs else 1.0
        std_max = max(stds) if stds else 1.0
        rng_max = max(rngs) if rngs else 1.0

        for i, ds in enumerate(die_stats):
            # Die label
            item_die = QTableWidgetItem(ds['die'])
            item_die.setBackground(QColor(BG3))
            table.setItem(i, 0, item_die)
            # Avg — diverging
            bg = _heatmap_diverging(ds['avg'] / avg_max if avg_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['avg']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 1, item)
            # StdDev — single
            bg = _heatmap_single(ds['stddev'] / std_max if std_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['stddev']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 2, item)
            # Range — single
            bg = _heatmap_single(ds['range'] / rng_max if rng_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['range']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(i, 3, item)

    def _update_die_avg_tables(self):
        self._fill_die_avg_heatmap(self.die_x_table, self._dev_x.get('die_stats', []))
        self._fill_die_avg_heatmap(self.die_y_table, self._dev_y.get('die_stats', []))

    def _fill_deviation_table(self, table: CopyableTable, dev_result):
        table.clear()
        die_labels = dev_result.get('die_labels', [])
        repeat_labels = dev_result.get('repeat_labels', [])
        matrix = dev_result.get('matrix', {})
        if not die_labels or not repeat_labels:
            table.setRowCount(1); table.setColumnCount(1)
            table.setItem(0, 0, QTableWidgetItem("No data"))
            return

        table.setColumnCount(len(die_labels) + 1)
        table.setHorizontalHeaderLabels([''] + die_labels)
        table.setRowCount(len(repeat_labels))

        all_vals = [matrix.get(rl, {}).get(dl) for rl in repeat_labels
                    for dl in die_labels if matrix.get(rl, {}).get(dl) is not None]
        v_max = max(abs(v) for v in all_vals) if all_vals else 1.0

        for i, rl in enumerate(repeat_labels):
            item_rl = QTableWidgetItem(rl[:10])
            item_rl.setBackground(QColor(BG3))
            table.setItem(i, 0, item_rl)
            for j, dl in enumerate(die_labels):
                v = matrix.get(rl, {}).get(dl)
                if v is None:
                    item = QTableWidgetItem("—")
                    item.setBackground(QColor(BG2))
                else:
                    item = QTableWidgetItem(f"{v:.3f}")
                    bg = _heatmap_diverging(v / v_max if v_max > 0 else 0)
                    item.setBackground(bg)
                    item.setForeground(_contrast_fg(bg))
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(i, j + 1, item)

    def _update_deviation_tables(self):
        self._fill_deviation_table(self.dev_x_table, self._dev_x)
        self._fill_deviation_table(self.dev_y_table, self._dev_y)

    def _update_raw_table(self):
        t = self.raw_table
        t.setRowCount(0)
        for r in self.raw_data:
            row = t.rowCount()
            t.insertRow(row)
            io = r.get('is_outlier', False)
            vals = [r.get('lot_name', ''), r.get('site_id', ''),
                    r.get('method', ''), f"{r.get('value', 0):.3f}",
                    '✅' if r.get('valid', True) else '❌',
                    '⚠️' if io else '']
            for col, v in enumerate(vals):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignCenter)
                if io:
                    item.setForeground(QColor(RED))
                t.setItem(row, col, item)

    # ──────────────────────────────────────────────
    # Charts — Hybrid: matplotlib + pyqtgraph
    # ──────────────────────────────────────────────
    def _update_charts(self, data, result, recipe):
        import matplotlib.pyplot as plt
        plt.close('all')
        short = recipe.get('short_name', '')
        trend = result.get('trend', [])

        # ─── pyqtgraph 인터랙티브 차트 (GPU 가속) ───
        try:
            trend_x = result.get('trend_x', [])
            trend_y = result.get('trend_y', [])
            dev_spec = self.settings.get('spec_deviation', {})
            ds = dev_spec.get(short, {})
            self._update_lot_trend(trend_x, trend_y, short, ds)
        except Exception as e:
            self.logger.error(f"Lot 트렌드 차트 오류: {e}")

        try:
            x_data = [r for r in data if r.get('method') == 'X']
            self.chart_widgets['📊 분포 X'].set_widget(
                viz_pg.create_histogram_widget(x_data, title=f'{short} X Distribution'))
        except Exception as e:
            self.logger.error(f"분포 X 차트 오류: {e}")

        try:
            y_data = [r for r in data if r.get('method') == 'Y']
            self.chart_widgets['📊 분포 Y'].set_widget(
                viz_pg.create_histogram_widget(y_data, title=f'{short} Y Distribution'))
        except Exception as e:
            self.logger.error(f"분포 Y 차트 오류: {e}")

        try:
            self.chart_widgets['🎯 XY Scatter'].set_widget(
                viz_pg.create_scatter_widget(
                    self._dev_x, self._dev_y, title=f'{short} — XY Scatter'))
        except Exception as e:
            self.logger.error(f"XY Scatter 차트 오류: {e}")

        # ─── Pareto Chart (이상치 분석) ───
        try:
            pareto = compute_pareto_data(data, group_by='die')
            self.chart_widgets['🔍 Pareto'].set_widget(
                viz_pg.create_pareto_widget(pareto, title=f'{short} — Pareto'))
        except Exception as e:
            self.logger.error(f"Pareto 차트 오류: {e}")

        # ─── Correlation Chart (X/Y 상관관계) ───
        try:
            if self._dev_x.get('die_stats') and self._dev_y.get('die_stats'):
                corr = compute_correlation(
                    self._dev_x['die_stats'], self._dev_y['die_stats'])
                self.chart_widgets['🔗 Correlation'].set_widget(
                    viz_pg.create_correlation_widget(
                        corr, title=f'{short} — X/Y Correlation'))
        except Exception as e:
            self.logger.error(f"Correlation 차트 오류: {e}")

        # ─── 3D Surface (OpenGL) ─ X/Y 분리 ───
        for axis_key, dev in [('X', self._dev_x), ('Y', self._dev_y)]:
            try:
                ds = dev.get('die_stats')
                if ds:
                    self.chart_widgets[f'🌐 3D {axis_key}'].set_widget(
                        viz_pg.create_3d_surface_widget(
                            ds, title=f'{short} — 3D {axis_key} Surface'))
            except Exception as e:
                self.logger.error(f"3D {axis_key} Surface 오류: {e}")

        # ─── matplotlib 차트 (Contour/Vector — scipy 보간) ───
        wr = self._get_wafer_radius_um()  # 웨이퍼 반경 (µm)
        dyn = getattr(self, '_dynamic_die_positions', None)

        try:
            if self._dev_x.get('die_stats'):
                self.chart_widgets['Contour X'].set_figure(
                    viz.plot_wafer_contour(self._dev_x['die_stats'],
                                           title=f'{short} — X Wafer Contour',
                                           wafer_radius_um=wr,
                                           dynamic_positions=dyn))
            if self._dev_y.get('die_stats'):
                self.chart_widgets['Contour Y'].set_figure(
                    viz.plot_wafer_contour(self._dev_y['die_stats'],
                                           title=f'{short} — Y Wafer Contour',
                                           wafer_radius_um=wr,
                                           dynamic_positions=dyn))
        except Exception as e:
            self.logger.error(f"Contour 차트 오류: {e}")

        try:
            xy_prod = compute_xy_product(
                self._dev_x.get('die_stats', []), self._dev_y.get('die_stats', []))
            if xy_prod:
                prod_stats = [{'die': d, 'avg': v} for d, v in xy_prod.items()]
                self.chart_widgets['X*Y Offset'].set_figure(
                    viz.plot_wafer_contour(prod_stats, title=f'{short} — X*Y Offset',
                                           wafer_radius_um=wr,
                                           dynamic_positions=dyn))
        except Exception as e:
            self.logger.error(f"X*Y Offset 차트 오류: {e}")

        try:
            if self._dev_x.get('die_stats') and self._dev_y.get('die_stats'):
                scale_pct = self.vector_scale_slider.value()
                self.chart_widgets['↗️ Vector Map'].set_figure(
                    viz.plot_vector_map(self._dev_x['die_stats'], self._dev_y['die_stats'],
                                        title=f'{short} — Vector Map',
                                        wafer_radius_um=wr,
                                        dynamic_positions=dyn,
                                        scale_pct=scale_pct))
        except Exception as e:
            self.logger.error(f"Vector Map 차트 오류: {e}")

    def _render_die_position(self):
        dyn = getattr(self, '_dynamic_die_positions', None)
        self.chart_widgets['Die Position'].set_figure(
            viz.plot_die_position_map(dynamic_positions=dyn,
                                       wafer_radius_um=self._get_wafer_radius_um()))

    def _get_wafer_radius_um(self) -> float:
        """현재 선택된 웨이퍼 반경 (µm)."""
        idx = self.wafer_combo.currentIndex()
        return 100_000 if idx == 0 else 150_000  # 200mm→100mm, 300mm→150mm

    def _on_wafer_size_changed(self, index):
        """웨이퍼 크기 변경 시 설정 저장 + 차트 갱신."""
        size = 200 if index == 0 else 300
        self.settings['wafer_size'] = size
        save_settings(self.settings)
        self.logger.info(f"Wafer 크기 변경: {size}mm (반경 {size // 2}mm)")
        if self.recipe_results and self.current_recipe_idx < len(self.recipe_results):
            result = self.recipe_results[self.current_recipe_idx]
            recipe = self.recipes[self.current_recipe_idx]
            self._display_result(result, recipe)

    def _on_die_filter_changed(self, state):
        """개별 Die 체크박스 변경 → 재분석."""
        if self._die_filter_updating:
            return
        if self.recipe_results and self.current_recipe_idx < len(self.recipe_results):
            result = self.recipe_results[self.current_recipe_idx]
            recipe = self.recipes[self.current_recipe_idx]
            self._display_result(result, recipe)

    def _die_filter_select_all(self):
        """전체 Die 선택."""
        self._die_filter_updating = True
        for cb in self._die_checkboxes.values():
            cb.setChecked(True)
        self._die_filter_updating = False
        self._on_die_filter_changed(None)

    def _die_filter_exclude_stabilization(self):
        """안정화 Die 제외 — 첫 번째 측정 Die 체크 해제."""
        if not self.recipe_results or self.current_recipe_idx >= len(self.recipe_results):
            return
        raw = self.recipe_results[self.current_recipe_idx].get('raw_data', [])
        if not raw:
            return
        from analyzer import extract_die_number
        first_die = extract_die_number(raw[0].get('site_id', ''))
        if first_die is None:
            return

        # 먼저 전체 선택 후, 안정화 Die만 해제
        self._die_filter_updating = True
        for cb in self._die_checkboxes.values():
            cb.setChecked(True)
        if first_die in self._die_checkboxes:
            self._die_checkboxes[first_die].setChecked(False)
        self._die_filter_updating = False
        self._on_die_filter_changed(None)

    # ──────────────────────────────────────────────
    # Lot Trend Filter (Die 필터와 독립)
    # ──────────────────────────────────────────────
    def _update_lot_trend(self, trend_x: list, trend_y: list,
                          short_name: str = '', spec: dict = None):
        """Lot 트렌드 차트 갱신 + Lot 체크박스 동적 생성."""
        self._trend_data_x = trend_x
        self._trend_data_y = trend_y
        self._trend_short_name = short_name
        self._trend_spec = spec

        # Lot 체크박스 동적 생성 (X의 Lot 리스트 기준, X/Y 동일 가정)
        lot_names = [t.get('lot_name', f'Lot{i}') for i, t in enumerate(trend_x)]
        if not lot_names and trend_y:
            lot_names = [t.get('lot_name', f'Lot{i}') for i, t in enumerate(trend_y)]

        if set(lot_names) != set(self._lot_checkboxes.keys()):
            self._lot_filter_updating = True
            while self._lot_cb_flow.count():
                item = self._lot_cb_flow.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            self._lot_checkboxes.clear()

            for name in lot_names:
                cb = QCheckBox(name)
                cb.setChecked(True)
                cb.setStyleSheet(f"""
                    QCheckBox {{ color: {FG}; font-size: 8pt; border: none; }}
                    QCheckBox::indicator {{ width: 12px; height: 12px; }}
                    QCheckBox::indicator:unchecked {{ border: 1px solid #585b70;
                        border-radius: 2px; background: {BG2}; }}
                    QCheckBox::indicator:checked {{ border: 1px solid {ACCENT};
                        border-radius: 2px; background: {ACCENT}; }}
                """)
                cb.stateChanged.connect(self._on_lot_filter_changed)
                self._lot_cb_flow.addWidget(cb)
                self._lot_checkboxes[name] = cb
            self._lot_filter_updating = False

        self._lot_filter_info.setText(f"✅ 전체 Lot ({len(lot_names)}개)")
        self._render_lot_trend_chart()

    def _render_lot_trend_chart(self):
        """현재 체크 상태에 따라 Dual-Panel Lot 트렌드 차트 렌더링."""
        checked = {n for n, cb in self._lot_checkboxes.items() if cb.isChecked()}

        fx = [t for t in self._trend_data_x if t.get('lot_name', '') in checked]
        fy = [t for t in self._trend_data_y if t.get('lot_name', '') in checked]

        # re-index for continuous display
        for i, t in enumerate(fx):
            t['lot_index'] = i
        for i, t in enumerate(fy):
            t['lot_index'] = i

        short = getattr(self, '_trend_short_name', '')
        title = f'{short} Lot Trend' if short else 'Lot Trend'
        spec = getattr(self, '_trend_spec', None)
        self._lot_trend_chart.set_widget(
            viz_pg.create_dual_trend_widget(fx, fy, spec=spec, title=title))

        # 필터 정보 라벨
        total = max(len(self._trend_data_x), len(self._trend_data_y))
        shown = max(len(fx), len(fy))
        excluded = total - shown
        if excluded > 0:
            self._lot_filter_info.setText(
                f"⚠ {excluded}개 Lot 제외 → {shown}개 표시 (전체 {total}개)")
        else:
            self._lot_filter_info.setText(f"✅ 전체 Lot ({total}개)")

    def _on_lot_filter_changed(self, state=None):
        """개별 Lot 체크박스 변경 → 트렌드 재렌더링."""
        if self._lot_filter_updating:
            return
        self._render_lot_trend_chart()

    def _lot_filter_select_all(self):
        """전체 Lot 선택 / 해제 토글."""
        all_checked = all(cb.isChecked() for cb in self._lot_checkboxes.values())
        self._lot_filter_updating = True
        for cb in self._lot_checkboxes.values():
            cb.setChecked(not all_checked)
        self._lot_filter_updating = False
        if not all_checked:
            # 전체 선택 시 — 버튼 텍스트는 유지
            pass
        self._render_lot_trend_chart()

    def _lot_filter_range(self):
        """범위 지정 다이얼로그 — Lot 인덱스 범위로 체크박스 설정."""
        text, ok = QInputDialog.getText(
            self, "Lot 범위 지정",
            "표시할 Lot 범위를 입력하세요:\n\n"
            "  1-5     → 처음 5개 Lot\n"
            "  -3      → 마지막 3개 Lot\n"
            "  3-7     → 3번째 ~ 7번째 Lot\n",
            text="1-5")
        if not ok or not text.strip():
            return

        lot_names = list(self._lot_checkboxes.keys())
        n = len(lot_names)
        if n == 0:
            return

        text = text.strip()
        try:
            if text.startswith('-'):
                # 마지막 N개
                count = int(text[1:])
                start, end = max(0, n - count), n
            elif '-' in text:
                parts = text.split('-')
                start = max(0, int(parts[0]) - 1)
                end = min(n, int(parts[1]))
            else:
                # 단일 숫자 → 처음 N개
                count = int(text)
                start, end = 0, min(n, count)
        except ValueError:
            QMessageBox.warning(self, "입력 오류",
                                "올바른 형식으로 입력하세요.\n예: 1-5, -3, 3-7")
            return

        self._lot_filter_updating = True
        for i, (name, cb) in enumerate(self._lot_checkboxes.items()):
            cb.setChecked(start <= i < end)
        self._lot_filter_updating = False
        self._render_lot_trend_chart()

    def _on_vector_scale_changed(self, value):
        """화살표 배율 슬라이더 변경 시 Vector Map 재렌더링."""
        self.vector_scale_label.setText(f"{value}%")
        if not (self.recipe_results and self.current_recipe_idx < len(self.recipe_results)):
            return
        if not (self._dev_x.get('die_stats') and self._dev_y.get('die_stats')):
            return
        wr = self._get_wafer_radius_um()
        dyn = getattr(self, '_dynamic_die_positions', None)
        recipe = self.recipes[self.current_recipe_idx]
        short = recipe.get('short_name', '')
        try:
            self.chart_widgets['↗️ Vector Map'].set_figure(
                viz.plot_vector_map(self._dev_x['die_stats'], self._dev_y['die_stats'],
                                    title=f'{short} — Vector Map',
                                    wafer_radius_um=wr,
                                    dynamic_positions=dyn,
                                    scale_pct=value))
        except Exception as e:
            self.logger.error(f"Vector Map 재렌더링 오류: {e}")

    # ──────────────────────────────────────────────
    # Repeat Contour Popup
    # ──────────────────────────────────────────────
    def _open_repeat_contour(self, axis: str = 'X'):
        dev = self._dev_x if axis == 'X' else self._dev_y
        matrix = dev.get('matrix', {})
        die_labels = dev.get('die_labels', [])
        repeat_labels = dev.get('repeat_labels', [])
        if not repeat_labels or not die_labels:
            QMessageBox.information(self, "알림", f"{axis} 데이터가 없습니다.")
            return

        from scipy.interpolate import griddata
        from matplotlib.patches import Circle
        from matplotlib.colors import Normalize
        from matplotlib.patheffects import withStroke
        import matplotlib.pyplot as plt
        import numpy as np

        dyn = getattr(self, '_dynamic_die_positions', None)

        n = len(repeat_labels)
        cols = min(5, n)
        rows = math.ceil(n / cols)
        cell = 4.2
        fig, axes = plt.subplots(rows, cols,
                                 figsize=(cell*cols, cell*rows + 0.8), dpi=110)
        fig.patch.set_facecolor('#1e1e2e')
        if rows == 1 and cols == 1: axes = [[axes]]
        elif rows == 1: axes = [axes]
        elif cols == 1: axes = [[ax] for ax in axes]

        # 전역 deviation 범위 (색상 스케일 통일)
        all_vals = [abs(matrix.get(rl, {}).get(dl, 0))
                    for rl in repeat_labels for dl in die_labels
                    if matrix.get(rl, {}).get(dl) is not None]
        vmax_global = max(all_vals) if all_vals else 1.0

        for idx, rl in enumerate(repeat_labels):
            r, c = divmod(idx, cols)
            ax = axes[r][c]
            ax.set_facecolor('#1e1e2e')
            positions, values = [], []
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                pos = get_die_position(dl, dyn)
                if v is not None and pos is not None:
                    positions.append(pos); values.append(v)
            if len(positions) < 3:
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                        transform=ax.transAxes, color='#555', fontsize=12)
                ax.set_xlabel(rl, fontsize=10, fontweight='bold', color='#89b4fa')
                continue

            xs = np.array([p[0] for p in positions], dtype=float)
            ys = np.array([p[1] for p in positions], dtype=float)
            zs = np.array(values, dtype=float)

            # ── 원형 보정: 경계에 가상 포인트 추가 ──
            data_r = float(np.sqrt(xs**2 + ys**2).max()) + 1.5
            # 원 둘레에 36개 가상 포인트 → 부드러운 원형 경계
            n_boundary = 36
            angles = np.linspace(0, 2 * np.pi, n_boundary, endpoint=False)
            bx = data_r * np.cos(angles)
            by = data_r * np.sin(angles)
            # 가상 포인트 값 = 가장 가까운 실제 Die의 값으로 보간
            from scipy.spatial import cKDTree
            tree = cKDTree(np.column_stack([xs, ys]))
            _, nearest_idx = tree.query(np.column_stack([bx, by]))
            bz = zs[nearest_idx]
            # 원본 + 가상 포인트 합치기
            xs_ext = np.concatenate([xs, bx])
            ys_ext = np.concatenate([ys, by])
            zs_ext = np.concatenate([zs, bz])

            grid_res = 400
            pad = data_r * 1.05
            xi2, yi2 = np.meshgrid(
                np.linspace(-pad, pad, grid_res),
                np.linspace(-pad, pad, grid_res))
            zi = griddata((xs_ext, ys_ext), zs_ext, (xi2, yi2), method='cubic')
            # 원형 마스킹
            zi[np.sqrt(xi2**2 + yi2**2) > data_r] = np.nan
            norm = Normalize(vmin=-vmax_global, vmax=vmax_global)
            ax.contourf(xi2, yi2, zi, levels=50, cmap='RdYlGn', norm=norm, extend='both')

            # Die 위치 마커 (빈 원 ○)
            ax.scatter(xs, ys, c='none', s=20, zorder=5,
                       edgecolors='#ccc', linewidths=0.6)

            # Die 값 (외곽선으로 시인성 확보)
            outline_w = withStroke(linewidth=2.5, foreground='#1e1e2e')
            for i, (x, y) in enumerate(zip(xs, ys)):
                val = zs[i]
                txt_color = '#ff6b6b' if abs(val) > vmax_global * 0.65 else '#e0e0e0'
                ax.text(x, y + 0.5, f'{val:.2f}',
                        ha='center', va='bottom', fontsize=5.5,
                        color=txt_color, zorder=6,
                        path_effects=[outline_w])

            # 축 스타일 (레퍼런스와 동일)
            lim = data_r * 1.12
            ax.set_xlim(-lim, lim); ax.set_ylim(-lim, lim)
            ax.set_aspect('equal')
            ax.tick_params(labelsize=6, colors='#666', direction='in',
                           length=3, width=0.5)
            for s in ax.spines.values():
                s.set_color('#363650'); s.set_linewidth(0.5)
            ax.set_xlabel(rl, fontsize=9, fontweight='bold', color='#89b4fa',
                          labelpad=3)

        for idx in range(n, rows*cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)

        fig.suptitle(f'{axis} Offset — Repeat별 Contour Map', fontsize=14,
                     fontweight='bold', color='#cdd6f4')
        fig.tight_layout(rect=[0, 0, 1, 0.96])

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Repeat별 Contour Map — {axis} Offset")
        dlg.resize(1400, 850)
        layout = QVBoxLayout(dlg)
        canvas = FigureCanvasQTAgg(fig)
        toolbar = NavigationToolbar2QT(canvas, dlg)
        layout.addWidget(toolbar)
        layout.addWidget(canvas)
        dlg.show()

    # ──────────────────────────────────────────────
    # TIFF
    # ──────────────────────────────────────────────
    def _find_tiff_for_row(self, lot_name, site_id):
        """site_id를 포함하는 TIFF 파일을 해당 Lot 폴더에서 탐색.
        Debug/Capture 하위폴더는 제외하고 루트 파일만 검색합니다.
        """
        round_path = ''
        if 0 <= self.current_recipe_idx < len(self.recipe_results):
            result = self.recipe_results[self.current_recipe_idx]
            round_path = result.get('round_path', '')

        if not round_path or not os.path.isdir(round_path):
            self.logger.warn(f"TIFF 탐색 실패: round_path 없음")
            return []

        # ① lot_name으로 해당 Lot 폴더 찾기
        lot_folder = None
        for name in os.listdir(round_path):
            full = os.path.join(round_path, name)
            if os.path.isdir(full) and (name == lot_name or lot_name in name
                                         or name in lot_name):
                lot_folder = full
                break

        if not lot_folder:
            lot_folder = round_path
        self.logger.info(f"TIFF 탐색: {os.path.basename(lot_folder)} / {site_id}")

        # ② 루트 폴더의 파일만 검색 (Debug/Capture 하위폴더 제외)
        matched = []
        try:
            for f in os.listdir(lot_folder):
                fp = os.path.join(lot_folder, f)
                if os.path.isfile(fp) and f.lower().endswith(('.tif', '.tiff')) and site_id in f:
                    matched.append(os.path.normpath(fp))
        except OSError:
            pass

        if not matched:
            import re
            site_num = re.sub(r'[^0-9]', '', site_id)
            if site_num:
                try:
                    for f in os.listdir(lot_folder):
                        fp = os.path.join(lot_folder, f)
                        if os.path.isfile(fp) and f.lower().endswith(('.tif', '.tiff')) and site_num in f:
                            matched.append(os.path.normpath(fp))
                except OSError:
                    pass

        if matched:
            self.last_tiff_folder = os.path.normpath(lot_folder)
            self.tiff_path_label.setText(self.last_tiff_folder)
        else:
            self.logger.warn(f"TIFF 없음: {lot_name}/{site_id} in {lot_folder}")

        return matched

    def _on_row_double_click(self, row, col):
        lot_name = self.raw_table.item(row, 0)
        site_id = self.raw_table.item(row, 1)
        if not lot_name or not site_id:
            return
        lot_name, site_id = lot_name.text(), site_id.text()
        tiff_paths = self._find_tiff_for_row(lot_name, site_id)
        if not tiff_paths:
            self.statusBar().showMessage(f"⚠ TIFF 없음: {lot_name}/{site_id} (log 확인)")
            return

        # pspylib 사전 확인
        try:
            import pspylib.tiff.reader  # noqa: F401
        except ImportError:
            msg = "PSPylib 미설치: pip install pspylib-*.whl\n\nTIFF 런더링을 위해 PSPylib가 필요합니다."
            self.logger.error(msg.split('\n')[0])
            QMessageBox.warning(self, "PSPylib 없음", msg)
            return

        self.logger.info(f"TIFF 로드: {lot_name}/{site_id} ({len(tiff_paths)}개)")
        for p in tiff_paths:
            self.logger.info(f"  → {os.path.basename(p)}")
        self.statusBar().showMessage(f"TIFF 로드 중... {len(tiff_paths)}개")
        QApplication.processEvents()

        try:
            from tiff_loader import load_tiff

            results = []
            for tp in tiff_paths:
                try:
                    results.append(load_tiff(tp))
                except Exception as fe:
                    self.logger.warn(f"TIFF 로드 실패 [{os.path.basename(tp)}]: {fe}")

            if not results:
                self.statusBar().showMessage("⚠ TIFF 로드 실패")
                return

            # 모든 TIFF를 서브탭으로 표시
            self._tiff_viewer.set_results(results)
            self._show_tiff()
            self.statusBar().showMessage(f"✅ TIFF {len(results)}개 로드 완료: {lot_name}/{site_id}")

        except Exception as e:
            import traceback
            self.logger.error(f"TIFF 오류: {e}")
            self.logger.info(traceback.format_exc())
            self.statusBar().showMessage(f"⚠ TIFF 오류: {e}")


    def _show_tiff(self):
        """TIFF 탭으로 전환."""
        self._select_chart('🔬 TIFF')

    def _open_tiff_folder(self):
        folder = os.path.normpath(self.last_tiff_folder) if self.last_tiff_folder else ''
        if folder and os.path.isdir(folder):
            os.startfile(folder)
        elif folder:
            self.statusBar().showMessage(
                f"⚠ 폴더 없음: {folder}")
        else:
            self.statusBar().showMessage(
                "⚠ 먼저 '원본 데이터' 탭에서 행을 더블클릭하여 TIFF를 로드하세요.")

    # ──────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────
    def _export_csv(self):
        if not self.raw_data:
            QMessageBox.warning(self, "경고", "먼저 분석을 실행해주세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV", "", "Text (*.txt);;CSV (*.csv)", "Analysis.txt")
        if path:
            export_combined_csv(self.raw_data, path)
            self.logger.ok(f"CSV 저장: {path}")

    def _export_excel(self):
        if not self.raw_data:
            QMessageBox.warning(self, "경고", "먼저 분석을 실행해주세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel", "", "Excel (*.xlsx)", "Report.xlsx")
        if path:
            try:
                stats = compute_repeatability(self.raw_data)
                trend = compute_trend(self.raw_data)
                export_excel_report(self.raw_data, stats, trend, path)
                self.logger.ok(f"Excel 저장: {path}")
            except Exception as e:
                self.logger.error(f"Excel 오류: {e}")

    def _export_pdf(self):
        if not self.recipes:
            QMessageBox.warning(self, "경고", "스캔된 데이터가 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF", "", "PDF (*.pdf)", "Report.pdf")
        if not path:
            return
        self.logger.info("PDF 리포트 생성 중...")

        def run():
            try:
                results = load_all_recipes(self.path_edit.text(), round_name='1st', axis='both')
                comp = compare_recipes(results)
                from pdf_generator import generate_pdf_report
                generate_pdf_report(path, self.path_edit.text(), results, comp,
                                    self.settings.get('spec_limits', {}))
                QTimer.singleShot(0, lambda: self.logger.ok(f"PDF 저장 완료: {path}"))
                os.startfile(path)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.logger.error(f"PDF 오류: {e}"))

        threading.Thread(target=run, daemon=True).start()

    def _open_spec_config(self):
        from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QDialogButtonBox

        dlg = QDialog(self)
        dlg.setWindowTitle("⚙️ Spec 설정 현황")
        dlg.setMinimumSize(600, 480)
        dlg.setStyleSheet(f"background: {BG}; color: {FG};")
        layout = QVBoxLayout(dlg)

        # spec_deviation 테이블
        lbl_dev = QLabel("📊 Deviation Spec (판정 기준)")
        lbl_dev.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {ACCENT};")
        layout.addWidget(lbl_dev)

        dev_spec = self.settings.get('spec_deviation', {})
        t_dev = QTableWidget(len(dev_spec), 3)
        t_dev.setHorizontalHeaderLabels(['Recipe', 'Range (µm)', 'StdDev (µm)'])
        t_dev.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_dev.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (name, ds) in enumerate(dev_spec.items()):
            t_dev.setItem(row, 0, QTableWidgetItem(name))
            t_dev.setItem(row, 1, QTableWidgetItem(str(ds.get('spec_range', '—'))))
            t_dev.setItem(row, 2, QTableWidgetItem(str(ds.get('spec_stddev', '—'))))
        t_dev.resizeRowsToContents()
        layout.addWidget(t_dev)

        # spec_limits 테이블
        lbl_lim = QLabel("📌 Offset Limits (Cpk 기준)")
        lbl_lim.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {ACCENT}; margin-top: 8px;")
        layout.addWidget(lbl_lim)

        spec_lim = self.settings.get('spec_limits', {})
        t_lim = QTableWidget(len(spec_lim), 5)
        t_lim.setHorizontalHeaderLabels(['Recipe', 'X LSL (nm)', 'X USL (nm)', 'Y LSL (nm)', 'Y USL (nm)'])
        t_lim.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_lim.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (name, sp) in enumerate(spec_lim.items()):
            t_lim.setItem(row, 0, QTableWidgetItem(name))
            x = sp.get('X', {})
            y = sp.get('Y', {})
            t_lim.setItem(row, 1, QTableWidgetItem(str(x.get('lsl', '—'))))
            t_lim.setItem(row, 2, QTableWidgetItem(str(x.get('usl', '—'))))
            t_lim.setItem(row, 3, QTableWidgetItem(str(y.get('lsl', '—'))))
            t_lim.setItem(row, 4, QTableWidgetItem(str(y.get('usl', '—'))))
        t_lim.resizeRowsToContents()
        layout.addWidget(t_lim)

        # 파일 경로 안내
        path = os.path.join(os.path.dirname(__file__), 'settings.json')
        lbl_path = QLabel(f"📁 {path}")
        lbl_path.setStyleSheet(f"color: {FG2}; font-size: 8pt; margin-top: 8px;")
        lbl_path.setWordWrap(True)
        layout.addWidget(lbl_path)

        btn = QDialogButtonBox(QDialogButtonBox.Ok)
        btn.accepted.connect(dlg.accept)
        layout.addWidget(btn)
        dlg.exec()


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    window = DataAnalyzerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
