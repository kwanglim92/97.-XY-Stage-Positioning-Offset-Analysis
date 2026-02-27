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
    QMessageBox, QFrame, QDialog,
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
)
from exporter import export_combined_csv, export_excel_report
from settings import load_settings, save_settings, add_recent_folder
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
            self._layout.removeWidget(self._toolbar)
            self._layout.removeWidget(self._canvas)
            self._toolbar.deleteLater()
            self._canvas.deleteLater()
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
            #statcard {{ background: {BG2}; border-radius: 6px; padding: 8px; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {FG2};")
        layout.addWidget(lbl_title)

        self.lbl_avg = self._row(layout, "Avg (nm):")
        self.lbl_rng = self._row(layout, "Dev Range (µm):")
        self.lbl_std = self._row(layout, "Dev StdDev (µm):")
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

    def update_stats(self, avg, rng, std, cpk, is_pass: bool = None):
        self.lbl_avg.setText(f"{avg:.3f}")
        self.lbl_rng.setText(f"{rng:.3f}")
        self.lbl_std.setText(f"{std:.3f}")
        self.lbl_cpk.setText(f"{cpk:.2f}")
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
        self.main_tabs.addTab(data_widget, "🗄️ 데이터 테이블")

        # Sub 1: Summary
        self.sum_table = CopyableTable()
        cols_s = ['Recipe', 'R', 'N', 'Mean', 'Stdev', 'Min', 'Max', 'CV%', 'Out', 'X', 'Y', '결과']
        self.sum_table.setColumnCount(len(cols_s))
        self.sum_table.setHorizontalHeaderLabels(cols_s)
        hdr = self.sum_table.horizontalHeader()
        # 좁은 컬럼: R(1), Out(8), X(9), Y(10), 결과(11)
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

        def _add_chart(category, name, widget):
            if category not in self._inner_tabs:
                inner = QTabWidget()
                inner.setDocumentMode(True)
                self._inner_tabs[category] = inner
                self.chart_category_tabs.addTab(inner, category)
            self._inner_tabs[category].addTab(widget, name)
            self.chart_widgets[name] = widget

        # 기본 분석 (matplotlib)
        for name in ['Contour X', 'Contour Y', 'X*Y Offset',
                      '↗️ Vector Map', 'Die Position']:
            _add_chart('기본 분석', name, ChartWidget())

        # 인터랙티브 (pyqtgraph)
        for name in ['📈 트렌드', '🎯 XY Scatter', '📊 분포']:
            _add_chart('인터랙티브', name, InteractiveChartWidget())

        # TIFF
        tiff_cw = InteractiveChartWidget()
        tiff_viewer = viz_pg.create_tiff_widget()
        tiff_cw.set_widget(tiff_viewer)
        _add_chart('인터랙티브', '🔬 TIFF', tiff_cw)
        self._tiff_viewer = tiff_viewer

        # 고급 분석 (pyqtgraph — Phase 2)
        for name in ['🔍 Pareto', '🔗 Correlation']:
            _add_chart('고급 분석', name, InteractiveChartWidget())
        _add_chart('고급 분석', '🌐 3D Surface', InteractiveChartWidget())

        # 비교 (matplotlib — Recipe Comparison)
        _add_chart('비교', '📊 Recipe 비교', ChartWidget())

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

        # Contour X/Y — add Repeat별 Contour button in toolbar area
        for axis_name in ('Contour X', 'Contour Y'):
            cw = self.chart_widgets[axis_name]
            axis = 'X' if 'X' in axis_name else 'Y'
            btn = QPushButton(f"🗺️ Repeat별 Contour ({axis})")
            btn.clicked.connect(partial(self._open_repeat_contour, axis))
            cw.layout().insertWidget(0, btn)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 5)
        splitter.setStretchFactor(1, 5)

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
                self._main_splitter.setSizes([total * 4 // 9, total * 5 // 9])

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
            ds = dev_spec.get(short, dev_spec.get('default',
                 {'spec_range': 4.0, 'spec_stddev': 0.8}))
            spec_r = ds.get('spec_range', 4.0)
            spec_s = ds.get('spec_stddev', 0.8)
            if not data:
                self.step_pass_states[i] = None
                continue
            dx = compute_deviation_matrix(data, 'X')
            dy = compute_deviation_matrix(data, 'Y')
            sx = compute_statistics(filter_by_method(data, 'X'))
            sy = compute_statistics(filter_by_method(data, 'Y'))
            px = (dx['overall_range'] <= spec_r and dx['overall_stddev'] <= spec_s) if sx['count'] > 0 else None
            py = (dy['overall_range'] <= spec_r and dy['overall_stddev'] <= spec_s) if sy['count'] > 0 else None
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
        data = result.get('raw_data', [])
        self._update_cards(data, recipe)
        self._update_die_avg_tables()
        self._update_deviation_tables()
        self._update_raw_table()
        self._update_charts(data, result.get('trend', []), recipe)
        stats = result.get('statistics', {})
        self.statusBar().showMessage(
            f"Step {recipe['index']}: {recipe['short_name']} — "
            f"{stats.get('count', 0)}개 | Mean: {stats.get('mean', 0):.1f} | "
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
        sp = spec.get(short, spec.get('default',
             {'X': {'lsl': -5000, 'usl': 5000}, 'Y': {'lsl': -5000, 'usl': 5000}}))
        cpk_x = compute_cpk(s_x['mean'], s_x['stdev'],
                            sp.get('X', {}).get('lsl', -5000), sp.get('X', {}).get('usl', 5000))
        cpk_y = compute_cpk(s_y['mean'], s_y['stdev'],
                            sp.get('Y', {}).get('lsl', -5000), sp.get('Y', {}).get('usl', 5000))

        dev_spec = self.settings.get('spec_deviation', {})
        ds = dev_spec.get(short, dev_spec.get('default', {'spec_range': 4.0, 'spec_stddev': 0.8}))
        spec_r, spec_s = ds.get('spec_range', 4.0), ds.get('spec_stddev', 0.8)

        def _pass(st, dev):
            if st['count'] == 0:
                return None
            return dev['overall_range'] <= spec_r and dev['overall_stddev'] <= spec_s

        px = _pass(s_x, dev_x)
        py = _pass(s_y, dev_y)
        self.card_x.update_stats(s_x['mean'], dev_x['overall_range'],
                                 dev_x['overall_stddev'], cpk_x, px)
        self.card_y.update_stats(s_y['mean'], dev_y['overall_range'],
                                 dev_y['overall_stddev'], cpk_y, py)

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
                ds = dev_spec.get(recipe_name, dev_spec.get('default',
                     {'spec_range': 4.0, 'spec_stddev': 0.8}))
                spec_r = ds.get('spec_range', 4.0)
                spec_s = ds.get('spec_stddev', 0.8)
                if data:
                    dx = compute_deviation_matrix(data, 'X')
                    dy = compute_deviation_matrix(data, 'Y')
                    sx = compute_statistics(filter_by_method(data, 'X'))
                    sy = compute_statistics(filter_by_method(data, 'Y'))
                    if sx['count'] > 0:
                        px = dx['overall_range'] <= spec_r and dx['overall_stddev'] <= spec_s
                    if sy['count'] > 0:
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
    def _update_charts(self, data, trend, recipe):
        import matplotlib.pyplot as plt
        plt.close('all')
        short = recipe.get('short_name', '')

        # ─── pyqtgraph 인터랙티브 차트 (GPU 가속) ───
        try:
            self.chart_widgets['📈 트렌드'].set_widget(
                viz_pg.create_trend_widget(trend, title=f'{short} Lot Trend'))
        except Exception as e:
            self.logger.error(f"트렌드 차트 오류: {e}")

        try:
            self.chart_widgets['📊 분포'].set_widget(
                viz_pg.create_histogram_widget(data, title=f'{short} Distribution'))
        except Exception as e:
            self.logger.error(f"분포 차트 오류: {e}")

        try:
            self.chart_widgets['🎯 XY Scatter'].set_widget(
                viz_pg.create_scatter_widget(
                    self._dev_x, self._dev_y, title=f'{short} — XY Scatter'))
        except Exception as e:
            self.logger.error(f"XY Scatter 차트 오류: {e}")

        # ─── matplotlib 차트 (Contour/Vector — scipy 보간) ───
        try:
            if self._dev_x.get('die_stats'):
                self.chart_widgets['Contour X'].set_figure(
                    viz.plot_wafer_contour(self._dev_x['die_stats'],
                                           title=f'{short} — X Wafer Contour'))
            if self._dev_y.get('die_stats'):
                self.chart_widgets['Contour Y'].set_figure(
                    viz.plot_wafer_contour(self._dev_y['die_stats'],
                                           title=f'{short} — Y Wafer Contour'))
        except Exception as e:
            self.logger.error(f"Contour 차트 오류: {e}")

        try:
            xy_prod = compute_xy_product(
                self._dev_x.get('die_stats', []), self._dev_y.get('die_stats', []))
            if xy_prod:
                prod_stats = [{'die': d, 'avg': v} for d, v in xy_prod.items()]
                self.chart_widgets['X*Y Offset'].set_figure(
                    viz.plot_wafer_contour(prod_stats, title=f'{short} — X*Y Offset'))
        except Exception as e:
            self.logger.error(f"X*Y Offset 차트 오류: {e}")

        try:
            if self._dev_x.get('die_stats') and self._dev_y.get('die_stats'):
                self.chart_widgets['↗️ Vector Map'].set_figure(
                    viz.plot_vector_map(self._dev_x['die_stats'], self._dev_y['die_stats'],
                                        title=f'{short} — Vector Map'))
        except Exception as e:
            self.logger.error(f"Vector Map 차트 오류: {e}")

    def _render_die_position(self):
        self.chart_widgets['Die Position'].set_figure(viz.plot_die_position_map())

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
        import matplotlib.pyplot as plt
        import numpy as np

        n = len(repeat_labels)
        cols = min(5, n)
        rows = math.ceil(n / cols)
        fig, axes = plt.subplots(rows, cols, figsize=(4.5*cols, 4.5*rows), dpi=120)
        fig.patch.set_facecolor('#ffffff')
        if rows == 1 and cols == 1: axes = [[axes]]
        elif rows == 1: axes = [axes]
        elif cols == 1: axes = [[ax] for ax in axes]

        all_vals = [abs(matrix.get(rl, {}).get(dl, 0))
                    for rl in repeat_labels for dl in die_labels
                    if matrix.get(rl, {}).get(dl) is not None]
        vmax_global = max(all_vals) if all_vals else 1.0

        for idx, rl in enumerate(repeat_labels):
            r, c = divmod(idx, cols)
            ax = axes[r][c]
            positions, values = [], []
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                pos = get_die_position(dl)
                if v is not None and pos is not None:
                    positions.append(pos); values.append(v)
            if len(positions) < 3:
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                        transform=ax.transAxes)
                ax.set_title(rl, fontsize=10, fontweight='bold')
                continue

            xs = np.array([p[0] for p in positions], dtype=float)
            ys = np.array([p[1] for p in positions], dtype=float)
            zs = np.array(values, dtype=float)
            margin = 1.0
            xi2, yi2 = np.meshgrid(
                np.linspace(xs.min()-margin, xs.max()+margin, 200),
                np.linspace(ys.min()-margin, ys.max()+margin, 200))
            zi = griddata((xs, ys), zs, (xi2, yi2), method='cubic')
            wafer_r = max(abs(xs).max(), abs(ys).max()) + margin
            zi[np.sqrt(xi2**2 + yi2**2) > wafer_r] = np.nan
            norm = Normalize(vmin=-vmax_global, vmax=vmax_global)
            ax.contourf(xi2, yi2, zi, levels=50, cmap='RdYlGn', norm=norm, extend='both')
            ax.add_patch(Circle((0, 0), wafer_r, fill=False, edgecolor='#555',
                                linewidth=1.2, linestyle='--'))
            ax.scatter(xs, ys, c='black', s=12, zorder=5)
            ax.set_aspect('equal')
            ax.set_title(rl, fontsize=10, fontweight='bold')

        for idx in range(n, rows*cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)

        fig.suptitle(f'{axis} Offset — Repeat별 Contour Map', fontsize=14, fontweight='bold')
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        dlg = QDialog(self)
        dlg.setWindowTitle(f"Repeat별 Contour Map — {axis} Offset")
        dlg.resize(1200, 700)
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
        QMessageBox.information(self, "Spec",
            "settings.json 의 spec_limits / spec_deviation 섹션을 직접 수정하세요.\n\n"
            f"파일 위치:\n{os.path.join(os.path.dirname(__file__), 'settings.json')}")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(DARK_STYLE)
    window = DataAnalyzerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
