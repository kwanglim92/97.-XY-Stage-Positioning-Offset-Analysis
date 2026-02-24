"""
main.py — XY Stage Positioning Offset Analysis (Phase 8)

Layout:
  [Left]  Top:   X/Y Stat Cards (Pass/Fail)
          Bottom: [시스템 로그] | [데이터 테이블]   (rounded nested tabs)
  [Right] Full-height chart tabs (Contour, Vector Map, Scatter, etc.)
"""

import os
import sys
import subprocess
import threading
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from csv_loader import scan_lot_folders, batch_load, get_scan_summary
from analyzer import (compute_statistics, compute_group_statistics,
                      compute_trend, detect_outliers, compute_repeatability,
                      compute_cpk, filter_by_method, filter_valid_only,
                      compute_deviation_matrix, compute_xy_product,
                      compute_affine_transform, DIE_POSITIONS, get_die_position)
from exporter import export_combined_csv, export_excel_report
from settings import load_settings, save_settings, add_recent_folder
from recipe_scanner import (scan_recipes, load_recipe_data,
                            load_all_recipes, compare_recipes)

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import visualizer as viz


# ═══════════════════════════════════════════════════
#  System Logger
# ═══════════════════════════════════════════════════

class SystemLogger:
    """GUI Text widget에 시간 기반 로그를 기록하는 유틸리티."""

    def __init__(self, text_widget: tk.Text):
        self._tw = text_widget
        self._tw.configure(state='disabled')
        self._tw.tag_configure('time', foreground='#89b4fa')
        self._tw.tag_configure('info', foreground='#a6adc8')
        self._tw.tag_configure('ok', foreground='#a6e3a1')
        self._tw.tag_configure('warn', foreground='#fab387')
        self._tw.tag_configure('err', foreground='#f38ba8')
        self._tw.tag_configure('head', foreground='#cba6f7', font=('Consolas', 10, 'bold'))

    def _append(self, text: str, tag: str = 'info'):
        self._tw.configure(state='normal')
        ts = datetime.now().strftime('%H:%M:%S')
        self._tw.insert('end', f'[{ts}] ', 'time')
        self._tw.insert('end', text + '\n', tag)
        self._tw.see('end')
        self._tw.configure(state='disabled')

    def info(self, msg):   self._append(msg, 'info')
    def ok(self, msg):     self._append(msg, 'ok')
    def warn(self, msg):   self._append(msg, 'warn')
    def error(self, msg):  self._append(msg, 'err')
    def head(self, msg):   self._append(msg, 'head')

    def section(self, title):
        self._tw.configure(state='normal')
        self._tw.insert('end', f'\n{"═"*50}\n', 'head')
        self._tw.insert('end', f'  {title}\n', 'head')
        self._tw.insert('end', f'{"═"*50}\n', 'head')
        self._tw.see('end')
        self._tw.configure(state='disabled')


# ═══════════════════════════════════════════════════
#  Main Application
# ═══════════════════════════════════════════════════

class DataAnalyzerApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("📊 XY Stage Offset Analyzer — Workflow")
        self.geometry("1600x950")
        self.minsize(1280, 800)
        self.configure(bg='#1e1e2e')

        # State
        self.settings = load_settings()
        self.folder_path = tk.StringVar(value=self.settings.get('last_folder', ''))
        self.status_text = tk.StringVar(value="폴더를 선택하세요.")

        self.recipes = []
        self.recipe_results = []
        self.current_recipe_idx = -1
        self.raw_data = []
        self.lot_list = []
        self.last_tiff_folder = ''

        # Deviation cache
        self._dev_x = {}
        self._dev_y = {}

        self._setup_styles()
        self._build_ui()
        self._restore_settings()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    def _on_close(self):
        self._save_current_settings()
        import matplotlib.pyplot as plt
        plt.close('all')
        self.destroy()

    def _save_current_settings(self):
        self.settings['last_folder'] = self.folder_path.get()
        self.settings['window_geometry'] = self.geometry()
        save_settings(self.settings)

    def _restore_settings(self):
        geom = self.settings.get('window_geometry', '')
        if geom:
            try: self.geometry(geom)
            except Exception: pass
        if self.folder_path.get() and os.path.isdir(self.folder_path.get()):
            self.after(100, self._scan_folder)

    # ──────────────────────────────────────────────
    # Styles (Rounded Tabs)
    # ──────────────────────────────────────────────

    def _setup_styles(self):
        bg = '#1e1e2e'; bg2 = '#282a3a'; bg3 = '#313244'
        fg = '#cdd6f4'; fg2 = '#a6adc8'
        accent = '#89b4fa'; green = '#a6e3a1'; red = '#f38ba8'

        style = ttk.Style(self)
        style.theme_use('clam')

        style.configure('.', background=bg, foreground=fg, fieldbackground=bg3, font=('Segoe UI', 9))
        style.configure('TFrame', background=bg)
        style.configure('Card.TFrame', background=bg2)
        style.configure('TLabel', background=bg, foreground=fg)
        style.configure('Card.TLabel', background=bg2, foreground=fg)
        style.configure('Title.TLabel', font=('Segoe UI', 16, 'bold'), foreground=accent)
        style.configure('Subtitle.TLabel', font=('Segoe UI', 11, 'bold'), foreground=fg2, background=bg2)
        style.configure('Value.TLabel', font=('Segoe UI', 13, 'bold'), foreground=fg, background=bg2)
        style.configure('Status.TLabel', background=bg3, foreground=fg2, font=('Consolas', 9), padding=(8, 4))
        style.configure('Pass.TLabel', font=('Segoe UI', 10, 'bold'), foreground=bg, background=green, padding=(6, 2))
        style.configure('Fail.TLabel', font=('Segoe UI', 10, 'bold'), foreground=bg, background=red, padding=(6, 2))
        style.configure('Wait.TLabel', font=('Segoe UI', 10, 'bold'), foreground=bg, background='gray', padding=(6, 2))

        style.configure('TButton', background=bg3, foreground=fg, padding=(8, 4))
        style.map('TButton', background=[('active', accent)], foreground=[('active', bg)])
        style.configure('Accent.TButton', background=accent, foreground=bg, font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#74c7ec')])
        style.configure('Step.TButton', background=bg3, foreground=fg, font=('Segoe UI', 9, 'bold'), padding=(10, 6))
        style.configure('ActiveStep.TButton', background=accent, foreground=bg, font=('Segoe UI', 9, 'bold'), padding=(10, 6))

        # ─── Rounded Notebook Tabs ───
        style.element_create('round.tab', 'from', 'clam')
        style.layout('Rounded.TNotebook.Tab', [
            ('Notebook.tab', {'sticky': 'nswe', 'children': [
                ('Notebook.padding', {'side': 'top', 'sticky': 'nswe', 'children': [
                    ('Notebook.label', {'side': 'top', 'sticky': ''})
                ]})
            ]})
        ])
        style.configure('Rounded.TNotebook', background=bg, borderwidth=0, tabmargins=[4, 4, 4, 0])
        style.configure('Rounded.TNotebook.Tab', background=bg3, foreground=fg2,
                         padding=[14, 6], font=('Segoe UI', 9, 'bold'),
                         borderwidth=0, relief='flat')
        style.map('Rounded.TNotebook.Tab',
                  background=[('selected', '#45475a'), ('active', '#3b3d50')],
                  foreground=[('selected', accent), ('active', fg)])

        # Sub-tabs (slightly smaller)
        style.configure('Sub.TNotebook', background=bg2, borderwidth=0, tabmargins=[2, 2, 2, 0])
        style.configure('Sub.TNotebook.Tab', background=bg3, foreground=fg2,
                         padding=[10, 4], font=('Segoe UI', 9),
                         borderwidth=0, relief='flat')
        style.map('Sub.TNotebook.Tab',
                  background=[('selected', '#45475a'), ('active', '#3b3d50')],
                  foreground=[('selected', accent), ('active', fg)])

        # Treeview
        style.configure('Treeview', background=bg2, foreground=fg, fieldbackground=bg2,
                         borderwidth=0, font=('Consolas', 9), rowheight=22)
        style.configure('Treeview.Heading', background=bg3, foreground=accent, font=('Segoe UI', 9, 'bold'))
        style.map('Treeview', background=[('selected', '#45475a')], foreground=[('selected', fg)])
        style.configure('TLabelframe', background=bg, foreground=fg)
        style.configure('TLabelframe.Label', background=bg, foreground=accent, font=('Segoe UI', 9, 'bold'))

        self._colors = {'bg': bg, 'bg2': bg2, 'bg3': bg3, 'fg': fg, 'fg2': fg2,
                        'accent': accent, 'green': green, 'red': red}

    # ──────────────────────────────────────────────
    # Build UI
    # ──────────────────────────────────────────────

    def _build_ui(self):
        # ===== TOP BAR =====
        top = ttk.Frame(self)
        top.pack(fill='x', padx=10, pady=(8, 0))

        ttk.Label(top, text="📁", font=('Segoe UI', 12)).pack(side='left')
        ttk.Entry(top, textvariable=self.folder_path, width=50, font=('Segoe UI', 9)).pack(side='left', padx=4)
        ttk.Button(top, text="찾아보기", command=self._browse_folder).pack(side='left', padx=2)
        ttk.Button(top, text="🔄 스캔 & 분석", style='Accent.TButton', command=self._scan_folder).pack(side='left', padx=8)
        ttk.Button(top, text="📄 PDF", style='Accent.TButton', command=self._export_pdf).pack(side='right', padx=2)
        ttk.Button(top, text="💾 CSV", command=self._export_csv).pack(side='right', padx=2)
        ttk.Button(top, text="📊 Excel", command=self._export_excel).pack(side='right', padx=2)

        # ===== STEP NAV =====
        self.nav_frame = ttk.Frame(self)
        self.nav_frame.pack(fill='x', padx=10, pady=(10, 4))
        self.step_buttons = []

        # ===== MAIN PANED =====
        paned = ttk.PanedWindow(self, orient='horizontal')
        paned.pack(fill='both', expand=True, padx=10, pady=4)

        # ════════════ LEFT PANEL ════════════
        left = ttk.Frame(paned)
        paned.add(left, weight=2)

        self.step_title = ttk.Label(left, text="Step: 폴더를 선택하세요", style='Title.TLabel')
        self.step_title.pack(anchor='w', pady=(0, 6))

        # --- Stat Cards ---
        cards = ttk.Frame(left)
        cards.pack(fill='x', pady=2)
        cards.columnconfigure(0, weight=1); cards.columnconfigure(1, weight=1)

        self.card_x = ttk.Frame(cards, style='Card.TFrame', padding=8)
        self.card_x.grid(row=0, column=0, sticky='nsew', padx=(0, 2))
        ttk.Label(self.card_x, text="X Offset", style='Subtitle.TLabel').pack(anchor='w', pady=(0, 4))
        self.lbl_x_avg = self._stat_row(self.card_x, "Avg (nm):")
        self.lbl_x_rng = self._stat_row(self.card_x, "Dev Range (µm):")
        self.lbl_x_std = self._stat_row(self.card_x, "Dev StdDev (µm):")
        self.lbl_x_cpk = self._stat_row(self.card_x, "Cpk:")
        self.lbl_x_badge = ttk.Label(self.card_x, text="—", style='Wait.TLabel')
        self.lbl_x_badge.pack(pady=(6, 0))

        self.card_y = ttk.Frame(cards, style='Card.TFrame', padding=8)
        self.card_y.grid(row=0, column=1, sticky='nsew', padx=(2, 0))
        ttk.Label(self.card_y, text="Y Offset", style='Subtitle.TLabel').pack(anchor='w', pady=(0, 4))
        self.lbl_y_avg = self._stat_row(self.card_y, "Avg (nm):")
        self.lbl_y_rng = self._stat_row(self.card_y, "Dev Range (µm):")
        self.lbl_y_std = self._stat_row(self.card_y, "Dev StdDev (µm):")
        self.lbl_y_cpk = self._stat_row(self.card_y, "Cpk:")
        self.lbl_y_badge = ttk.Label(self.card_y, text="—", style='Wait.TLabel')
        self.lbl_y_badge.pack(pady=(6, 0))

        ttk.Button(left, text="⚙️ Spec 설정", command=self._open_spec_config).pack(anchor='e', pady=2)

        # --- Bottom: Main Tabs (System Log | Data Table) ---
        self.main_tabs = ttk.Notebook(left, style='Rounded.TNotebook')
        self.main_tabs.pack(fill='both', expand=True, pady=(4, 0))

        # === Tab 1: System Log ===
        log_frame = ttk.Frame(self.main_tabs)
        self.main_tabs.add(log_frame, text=' 📝 시스템 로그 ')
        self.log_text = tk.Text(log_frame, bg='#181825', fg='#cdd6f4',
                                font=('Consolas', 9), wrap='word', borderwidth=0,
                                insertbackground='#cdd6f4')
        log_sb = ttk.Scrollbar(log_frame, orient='vertical', command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_sb.set)
        log_sb.pack(side='right', fill='y')
        self.log_text.pack(fill='both', expand=True)
        self.logger = SystemLogger(self.log_text)

        # === Tab 2: Data Table (hub) ===
        data_frame = ttk.Frame(self.main_tabs)
        self.main_tabs.add(data_frame, text=' 🗄️ 데이터 테이블 ')

        self.data_tabs = ttk.Notebook(data_frame, style='Sub.TNotebook')
        self.data_tabs.pack(fill='both', expand=True)

        # Sub 1: Summary
        tab_sum = ttk.Frame(self.data_tabs)
        self.data_tabs.add(tab_sum, text=' 📊 Summary ')
        cols_s = ('recipe', 'round', 'n', 'mean', 'stdev', 'min', 'max', 'cv', 'out')
        self.sum_tv = ttk.Treeview(tab_sum, columns=cols_s, show='headings')
        for c, t, w in [('recipe', 'Recipe', 120), ('round', 'R', 32), ('n', 'N', 38),
                         ('mean', 'Mean', 75), ('stdev', 'Stdev', 65), ('min', 'Min', 75),
                         ('max', 'Max', 75), ('cv', 'CV%', 48), ('out', 'Out', 36)]:
            self.sum_tv.heading(c, text=t)
            self.sum_tv.column(c, width=w, anchor='e' if c != 'recipe' else 'w')
        ssb = ttk.Scrollbar(tab_sum, orient='vertical', command=self.sum_tv.yview)
        self.sum_tv.configure(yscrollcommand=ssb.set)
        ssb.pack(side='right', fill='y'); self.sum_tv.pack(fill='both', expand=True)

        # Sub 2: Die 평균 (X/Y sub-sub tabs) — Canvas Grid heatmap
        tab_die = ttk.Frame(self.data_tabs)
        self.data_tabs.add(tab_die, text=' 🔢 Die별 평균 ')
        self.die_tabs = ttk.Notebook(tab_die, style='Sub.TNotebook')
        self.die_tabs.pack(fill='both', expand=True)

        die_x_frame = ttk.Frame(self.die_tabs)
        self.die_tabs.add(die_x_frame, text=' X Die Average ')
        self.die_x_canvas, self.die_x_inner = self._make_scrollable_grid(die_x_frame)

        die_y_frame = ttk.Frame(self.die_tabs)
        self.die_tabs.add(die_y_frame, text=' Y Die Average ')
        self.die_y_canvas, self.die_y_inner = self._make_scrollable_grid(die_y_frame)

        # Sub 3: Raw Deviation (X/Y)
        tab_dev = ttk.Frame(self.data_tabs)
        self.data_tabs.add(tab_dev, text=' 🔲 Raw Deviation ')
        self.dev_tabs = ttk.Notebook(tab_dev, style='Sub.TNotebook')
        self.dev_tabs.pack(fill='both', expand=True)

        dev_x_frame = ttk.Frame(self.dev_tabs)
        self.dev_tabs.add(dev_x_frame, text=' X offset ')
        self.dev_x_canvas = tk.Canvas(dev_x_frame, bg=self._colors['bg2'], highlightthickness=0)
        dev_x_sb_h = ttk.Scrollbar(dev_x_frame, orient='horizontal', command=self.dev_x_canvas.xview)
        dev_x_sb_v = ttk.Scrollbar(dev_x_frame, orient='vertical', command=self.dev_x_canvas.yview)
        self.dev_x_canvas.configure(xscrollcommand=dev_x_sb_h.set, yscrollcommand=dev_x_sb_v.set)
        dev_x_sb_v.pack(side='right', fill='y')
        dev_x_sb_h.pack(side='bottom', fill='x')
        self.dev_x_canvas.pack(fill='both', expand=True)
        self.dev_x_inner = ttk.Frame(self.dev_x_canvas)
        self.dev_x_canvas.create_window((0, 0), window=self.dev_x_inner, anchor='nw')
        self.dev_x_inner.bind('<Configure>', lambda e: self.dev_x_canvas.configure(scrollregion=self.dev_x_canvas.bbox('all')))

        dev_y_frame = ttk.Frame(self.dev_tabs)
        self.dev_tabs.add(dev_y_frame, text=' Y offset ')
        self.dev_y_canvas = tk.Canvas(dev_y_frame, bg=self._colors['bg2'], highlightthickness=0)
        dev_y_sb_h = ttk.Scrollbar(dev_y_frame, orient='horizontal', command=self.dev_y_canvas.xview)
        dev_y_sb_v = ttk.Scrollbar(dev_y_frame, orient='vertical', command=self.dev_y_canvas.yview)
        self.dev_y_canvas.configure(xscrollcommand=dev_y_sb_h.set, yscrollcommand=dev_y_sb_v.set)
        dev_y_sb_v.pack(side='right', fill='y')
        dev_y_sb_h.pack(side='bottom', fill='x')
        self.dev_y_canvas.pack(fill='both', expand=True)
        self.dev_y_inner = ttk.Frame(self.dev_y_canvas)
        self.dev_y_canvas.create_window((0, 0), window=self.dev_y_inner, anchor='nw')
        self.dev_y_inner.bind('<Configure>', lambda e: self.dev_y_canvas.configure(scrollregion=self.dev_y_canvas.bbox('all')))

        # Sub 4: Raw Data
        tab_raw = ttk.Frame(self.data_tabs)
        self.data_tabs.add(tab_raw, text=' 📄 원본 데이터 ')
        cols_r = ('lot', 'site', 'axis', 'val', 'v', 'out')
        self.raw_tv = ttk.Treeview(tab_raw, columns=cols_r, show='headings')
        for c, t, w in [('lot', 'Lot', 65), ('site', 'Site', 110), ('axis', 'Axis', 30),
                         ('val', 'HZ1_O', 85), ('v', 'V', 28), ('out', 'Out', 32)]:
            self.raw_tv.heading(c, text=t)
            self.raw_tv.column(c, width=w, anchor='center' if c in ('axis', 'v', 'out') else 'e')
        rsb = ttk.Scrollbar(tab_raw, orient='vertical', command=self.raw_tv.yview)
        self.raw_tv.configure(yscrollcommand=rsb.set)
        rsb.pack(side='right', fill='y'); self.raw_tv.pack(fill='both', expand=True)
        self.raw_tv.tag_configure('outlier', foreground=self._colors['red'])
        self.raw_tv.bind('<Double-1>', self._on_row_double_click)

        # ════════════ RIGHT PANEL (Charts only) ════════════
        right = ttk.Frame(paned)
        paned.add(right, weight=3)

        self.chart_tabs = ttk.Notebook(right, style='Rounded.TNotebook')
        self.chart_tabs.pack(fill='both', expand=True)
        self.chart_frames = {}
        self.chart_content_frames = {}  # inner frames for chart canvas (below toolbar)

        for tname in ['Contour X', 'Contour Y', 'X*Y Offset', 'XY Scatter',
                       '↗️ Vector Map', 'Die Position', '트렌드', '분포', 'TIFF']:
            f = ttk.Frame(self.chart_tabs)
            self.chart_tabs.add(f, text=f' {tname} ')
            self.chart_frames[tname] = f

        # Contour X/Y — add "Repeat별 보기" button
        for axis_name in ('Contour X', 'Contour Y'):
            cf = self.chart_frames[axis_name]
            cbar = ttk.Frame(cf); cbar.pack(fill='x', side='top', pady=2)
            axis = 'X' if 'X' in axis_name else 'Y'
            ttk.Button(cbar, text=f"🗺️ Repeat별 Contour ({axis})",
                       command=lambda a=axis: self._open_repeat_contour(a)).pack(side='left', padx=4)
            content = ttk.Frame(cf)
            content.pack(fill='both', expand=True)
            self.chart_content_frames[axis_name] = content

        # TIFF sub-controls
        tf = self.chart_frames['TIFF']
        tbar = ttk.Frame(tf); tbar.pack(fill='x', pady=2)
        ttk.Button(tbar, text="📂 폴더 열기", command=self._open_tiff_folder).pack(side='left', padx=4)
        self.tiff_path_label = ttk.Label(tbar, text="", foreground=self._colors['fg2'])
        self.tiff_path_label.pack(side='left', padx=8)
        self.tiff_chart_frame = ttk.Frame(tf)
        self.tiff_chart_frame.pack(fill='both', expand=True)

        # Die Position — render once
        self.after(200, self._render_die_position)

        # Boot log
        self.after(50, lambda: self.logger.head("XY Stage Offset Analyzer v8.0 시작"))
        self.after(100, lambda: self.logger.info("폴더를 선택하고 '스캔 & 분석'을 눌러주세요."))

        # Status
        ttk.Label(self, textvariable=self.status_text, style='Status.TLabel').pack(fill='x', side='bottom')

    def _stat_row(self, parent, label):
        f = ttk.Frame(parent, style='Card.TFrame')
        f.pack(fill='x', pady=1)
        ttk.Label(f, text=label, style='Card.TLabel', font=('Segoe UI', 9)).pack(side='left')
        lbl = ttk.Label(f, text="-", style='Value.TLabel')
        lbl.pack(side='right')
        return lbl

    def _make_scrollable_grid(self, parent):
        """Scrollable Canvas + inner Frame 을 생성하여 (canvas, inner_frame) 반환."""
        canvas = tk.Canvas(parent, bg=self._colors['bg2'], highlightthickness=0)
        sb_v = ttk.Scrollbar(parent, orient='vertical', command=canvas.yview)
        sb_h = ttk.Scrollbar(parent, orient='horizontal', command=canvas.xview)
        canvas.configure(xscrollcommand=sb_h.set, yscrollcommand=sb_v.set)
        sb_v.pack(side='right', fill='y')
        sb_h.pack(side='bottom', fill='x')
        canvas.pack(fill='both', expand=True)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor='nw')
        inner.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        return canvas, inner

    # ──────────────────────────────────────────────
    # Color helpers
    # ──────────────────────────────────────────────

    @staticmethod
    def _get_contrast_color(hex_bg: str) -> str:
        """배경 hex색의 밝기(Luminance)를 구해 검정 또는 흰색을 반환."""
        hex_bg = hex_bg.lstrip('#')
        r, g, b = int(hex_bg[0:2], 16), int(hex_bg[2:4], 16), int(hex_bg[4:6], 16)
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        return '#1e1e2e' if luminance > 140 else '#ffffff'

    @staticmethod
    def _heatmap_diverging(ratio: float):
        """ratio ∈ [-1, 1] → (hex_bg). 음수=파란색, 양수=빨간색, 0=거의 흰색."""
        ratio = max(-1.0, min(1.0, ratio))
        if ratio >= 0:
            r = 255; g = int(255 * (1 - ratio)); b = int(235 * (1 - ratio))
        else:
            r = int(255 * (1 + ratio)); g = int(230 * (1 + ratio)); b = 255
        return f'#{r:02x}{g:02x}{b:02x}'

    @staticmethod
    def _heatmap_single(ratio: float):
        """ratio ∈ [0, 1] → (hex_bg). 0=거의 흰색, 1=짙은 Steel Blue."""
        ratio = max(0.0, min(1.0, ratio))
        # From near-white (#f0f4f8) to steel blue (#3a7abd)
        r = int(240 - (240 - 58) * ratio)
        g = int(244 - (244 - 122) * ratio)
        b = int(248 - (248 - 189) * ratio)
        return f'#{r:02x}{g:02x}{b:02x}'

    # ──────────────────────────────────────────────
    # Selectable Grid (drag-select & Ctrl+C copy)
    # ──────────────────────────────────────────────

    def _make_grid_selectable(self, inner_frame, n_rows: int, n_cols: int):
        """inner_frame의 grid Label에 마우스 드래그 선택 + Ctrl+C 복사.
        winfo_containing 방식으로 다른 셀으로 드래그해도 정상 감지."""
        inner_frame._grid_data = {}   # (row, col) -> label widget
        inner_frame._widget_to_rc = {}  # widget id -> (row, col)
        inner_frame._sel_start = None
        inner_frame._sel_end = None
        inner_frame._sel_origbg = {}  # widget id -> original bg color

        for w in inner_frame.winfo_children():
            info = w.grid_info()
            if info:
                r, c = int(info['row']), int(info['column'])
                inner_frame._grid_data[(r, c)] = w
                inner_frame._widget_to_rc[str(w)] = (r, c)
                # Store original bg for restore
                inner_frame._sel_origbg[str(w)] = w.cget('bg') if hasattr(w, 'cget') else ''
                # Click: start selection
                w.bind('<Button-1>', lambda e, fr=inner_frame: self._grid_on_click(fr, e))

        # Motion and Release on toplevel (works across widgets)
        top = inner_frame.winfo_toplevel()
        top.bind('<B1-Motion>', lambda e: self._grid_on_motion(inner_frame, e))
        top.bind('<ButtonRelease-1>', lambda e: None)
        top.bind('<Control-c>', lambda e: self._grid_copy(inner_frame))

        # Store the active frame reference
        if not hasattr(self, '_active_grid_frame'):
            self._active_grid_frame = None

    def _grid_on_click(self, fr, event):
        """Click 시작: 셀 좌표 감지 후 선택 시작."""
        self._active_grid_frame = fr
        w = event.widget
        rc = fr._widget_to_rc.get(str(w))
        if rc:
            fr._sel_start = rc
            fr._sel_end = rc
            self._grid_update_highlight(fr)

    def _grid_on_motion(self, fr, event):
        """드래그: winfo_containing으로 현재 마우스 위치의 셀을 찾아 선택 범위 확장."""
        if self._active_grid_frame is not fr:
            return
        if not fr._sel_start:
            return
        try:
            w = fr.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return
        if w is None:
            return
        rc = fr._widget_to_rc.get(str(w))
        if rc:
            fr._sel_end = rc
            self._grid_update_highlight(fr)

    def _grid_update_highlight(self, fr):
        if not fr._sel_start or not fr._sel_end:
            return
        r1, c1 = fr._sel_start
        r2, c2 = fr._sel_end
        rmin, rmax = min(r1, r2), max(r1, r2)
        cmin, cmax = min(c1, c2), max(c1, c2)

        sel_color = '#f38ba8'  # red highlight

        for (r, c), w in fr._grid_data.items():
            if rmin <= r <= rmax and cmin <= c <= cmax:
                w.configure(highlightbackground=sel_color,
                            highlightcolor=sel_color,
                            highlightthickness=2)
            else:
                w.configure(highlightthickness=0)

    def _grid_copy(self, fr):
        if not hasattr(fr, '_sel_start') or not fr._sel_start or not fr._sel_end:
            return
        r1, c1 = fr._sel_start
        r2, c2 = fr._sel_end
        rmin, rmax = min(r1, r2), max(r1, r2)
        cmin, cmax = min(c1, c2), max(c1, c2)

        lines = []
        for r in range(rmin, rmax + 1):
            row_vals = []
            for c in range(cmin, cmax + 1):
                w = fr._grid_data.get((r, c))
                row_vals.append(w.cget('text') if w else '')
            lines.append('\t'.join(row_vals))

        text = '\n'.join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_text.set(f"📋 {rmax - rmin + 1} × {cmax - cmin + 1} 셀 복사됨")

    # ──────────────────────────────────────────────
    # Deviation Matrix Table (heatmap colored)
    # ──────────────────────────────────────────────


    def _fill_deviation_table(self, inner_frame, dev_result):
        for w in inner_frame.winfo_children():
            w.destroy()

        die_labels = dev_result.get('die_labels', [])
        repeat_labels = dev_result.get('repeat_labels', [])
        matrix = dev_result.get('matrix', {})

        if not die_labels or not repeat_labels:
            tk.Label(inner_frame, text="No data", bg=self._colors['bg2'],
                     fg=self._colors['fg2'], font=('Consolas', 11)).grid(row=0, column=0)
            return

        header_bg = self._colors['bg3']
        header_fg = self._colors['accent']
        cell_font = ('Consolas', 9)

        # Header row
        tk.Label(inner_frame, text="", bg=header_bg, width=9, relief='flat',
                 font=cell_font).grid(row=0, column=0, sticky='nsew')
        for j, dl in enumerate(die_labels):
            tk.Label(inner_frame, text=dl, bg=header_bg, fg=header_fg,
                     font=('Segoe UI', 8, 'bold'), width=8, relief='flat',
                     padx=2).grid(row=0, column=j + 1, sticky='nsew')

        # Collect all values for color normalization
        all_vals = []
        for rl in repeat_labels:
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                if v is not None:
                    all_vals.append(v)

        v_max = max(abs(v) for v in all_vals) if all_vals else 1.0

        # Data rows
        for i, rl in enumerate(repeat_labels):
            tk.Label(inner_frame, text=rl[:10], bg=header_bg, fg=self._colors['fg'],
                     font=('Segoe UI', 8, 'bold'), width=9, anchor='w',
                     relief='flat', padx=4).grid(row=i + 1, column=0, sticky='nsew')
            for j, dl in enumerate(die_labels):
                v = matrix.get(rl, {}).get(dl)
                if v is None:
                    txt = "—"
                    bg_c = self._colors['bg2']
                    fg_c = self._colors['fg2']
                else:
                    txt = f"{v:.3f}"
                    ratio = v / v_max if v_max > 0 else 0
                    bg_c = self._heatmap_diverging(ratio)
                    fg_c = self._get_contrast_color(bg_c)

                tk.Label(inner_frame, text=txt, bg=bg_c, fg=fg_c,
                         font=cell_font, width=8, relief='flat',
                         padx=2, pady=1).grid(row=i + 1, column=j + 1, sticky='nsew')

        # Enable drag-select & copy
        self._make_grid_selectable(inner_frame,
                                   len(repeat_labels) + 1, len(die_labels) + 1)

    # ──────────────────────────────────────────────
    # Folder & Navigation
    # ──────────────────────────────────────────────

    def _browse_folder(self):
        path = filedialog.askdirectory(title="Root Data 폴더 선택",
                                       initialdir=self.folder_path.get() or None)
        if path:
            self.folder_path.set(path)
            self._scan_folder()

    def _scan_folder(self):
        folder = self.folder_path.get()
        if not folder or not os.path.isdir(folder):
            messagebox.showwarning("경고", "유효한 폴더를 선택해주세요.")
            return

        # Switch to log tab during scan
        self.main_tabs.select(0)

        self.logger.section("폴더 스캔 시작")
        self.logger.info(f"경로: {folder}")
        self.status_text.set("스캔 중...")

        self.recipes = scan_recipes(folder)
        if not self.recipes:
            self.logger.warn("Recipe 구조를 찾지 못했습니다.")
            messagebox.showinfo("알림", "Recipe 구조를 찾지 못했습니다.")
            return

        self.logger.ok(f"✅ {len(self.recipes)}개 Recipe 발견")
        for r in self.recipes:
            self.logger.info(f"  Step {r['index']}: {r['name']}")

        self.settings = add_recent_folder(self.settings, folder)
        self._save_current_settings()
        self._build_nav()

        self.logger.info("전체 Recipe 데이터 로드 시작 (1st round)...")

        def run():
            import time
            t0 = time.perf_counter()
            try:
                self.recipe_results = load_all_recipes(folder, round_name='1st', axis='both')
                comparison = compare_recipes(self.recipe_results)

                elapsed = time.perf_counter() - t0
                total = sum(len(r.get('raw_data', [])) for r in self.recipe_results)

                self.after(0, lambda: self._on_scan_complete(comparison, total, elapsed))
            except Exception as e:
                self.after(0, lambda: self.logger.error(f"로드 오류: {e}"))
                self.after(0, lambda: messagebox.showerror("오류", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _on_scan_complete(self, comparison, total, elapsed):
        self.logger.ok(f"✅ 전체 로드 완료: {total}개 데이터 ({elapsed:.1f}초 소요)")
        self._update_summary_table(comparison)

        # Affine Transform for each step
        self.logger.section("Affine Transform 계통 오차 분석")
        for i, result in enumerate(self.recipe_results):
            data = result.get('raw_data', [])
            dx = compute_deviation_matrix(data, 'X')
            dy = compute_deviation_matrix(data, 'Y')
            if dx['die_stats'] and dy['die_stats']:
                af = compute_affine_transform(dx['die_stats'], dy['die_stats'])
                name = result.get('short_name', f'Step {i+1}')
                self.logger.head(f"[{name}]")
                self.logger.info(f"  Translation:  Tx = {af['tx']:+.4f} µm,  Ty = {af['ty']:+.4f} µm")
                self.logger.info(f"  Scaling:      Sx = {af['sx_ppm']:+.2f} ppm,  Sy = {af['sy_ppm']:+.2f} ppm")
                self.logger.info(f"  Rotation:     θ  = {af['theta_deg']:+.6f}° ({af['theta_urad']:+.2f} µrad)")
                self.logger.info(f"  Residual RMS: X = {af['residual_x']:.4f} µm,  Y = {af['residual_y']:.4f} µm")
                self.logger.info(f"  Die 수: {af['n_dies']}")

        # Auto switch to Data tab
        self.main_tabs.select(1)
        self.data_tabs.select(0)  # Summary

        if self.recipe_results:
            self._select_step(0)

        self.status_text.set(f"✅ {len(self.recipes)}개 Recipe | {total}개 데이터 | Step 클릭 → 상세 분석")

    def _build_nav(self):
        for w in self.nav_frame.winfo_children():
            w.destroy()
        self.step_buttons.clear()
        ttk.Label(self.nav_frame, text="Workflow:", font=('Segoe UI', 10)).pack(side='left', padx=(0, 8))
        for i, r in enumerate(self.recipes):
            btn = ttk.Button(self.nav_frame, text=f"Step {r['index']}: {r['short_name']}",
                             style='Step.TButton', command=lambda idx=i: self._select_step(idx))
            btn.pack(side='left')
            self.step_buttons.append(btn)
            if i < len(self.recipes) - 1:
                ttk.Label(self.nav_frame, text=" ▶ ", foreground=self._colors['fg2']).pack(side='left', padx=1)

    def _select_step(self, idx):
        if idx < 0 or idx >= len(self.recipes):
            return
        self.current_recipe_idx = idx
        for i, btn in enumerate(self.step_buttons):
            btn.configure(style='ActiveStep.TButton' if i == idx else 'Step.TButton')

        recipe = self.recipes[idx]
        self.step_title.configure(text=f"Step {recipe['index']}: {recipe['name']}")
        self.logger.info(f"Step 전환 → {recipe['name']}")

        if idx < len(self.recipe_results) and self.recipe_results[idx].get('raw_data'):
            result = self.recipe_results[idx]
            self.raw_data = result.get('raw_data', [])
            rd1 = next((rd for rd in recipe.get('rounds', []) if rd['name'] == '1st'), None)
            if rd1:
                self.lot_list = scan_lot_folders(rd1['path'])
            self._display_result(result, recipe)
        else:
            self.status_text.set(f"데이터 로드 중: {recipe['short_name']}...")
            def run():
                try:
                    result = load_recipe_data(recipe, round_name='1st', axis='both')
                    self.raw_data = result.get('raw_data', [])
                    rd1 = next((rd for rd in recipe.get('rounds', []) if rd['name'] == '1st'), None)
                    if rd1:
                        self.lot_list = scan_lot_folders(rd1['path'])
                    self.after(0, lambda: self._display_result(result, recipe))
                except Exception as e:
                    self.after(0, lambda: messagebox.showerror("오류", str(e)))
            threading.Thread(target=run, daemon=True).start()

    # ──────────────────────────────────────────────
    # Display Result
    # ──────────────────────────────────────────────

    def _display_result(self, result, recipe):
        data = result.get('raw_data', [])
        stats = result.get('statistics', {})

        self._update_cards(data, recipe)
        self._update_die_avg_tables()
        self._update_deviation_tables()
        self._update_raw_table()
        self._update_charts(data, result.get('trend', []), recipe)

        self.status_text.set(
            f"Step {recipe['index']}: {recipe['short_name']} — "
            f"{stats.get('count', 0)}개 | Mean: {stats.get('mean', 0):.1f} | "
            f"이상치: {result.get('outlier_count', 0)}  💡 행 더블클릭 → TIFF")

    def _update_cards(self, data, recipe):
        d_x = filter_by_method(data, 'X')
        d_y = filter_by_method(data, 'Y')
        s_x = compute_statistics(d_x)
        s_y = compute_statistics(d_y)

        dev_x = compute_deviation_matrix(data, 'X')
        dev_y = compute_deviation_matrix(data, 'Y')
        self._dev_x = dev_x
        self._dev_y = dev_y

        spec = self.settings.get('spec_limits', {})
        short = recipe.get('short_name', '')
        sp = spec.get(short, spec.get('default', {'X': {'lsl': -5000, 'usl': 5000}, 'Y': {'lsl': -5000, 'usl': 5000}}))
        cpk_x = compute_cpk(s_x['mean'], s_x['stdev'],
                            sp.get('X', {}).get('lsl', -5000), sp.get('X', {}).get('usl', 5000))
        cpk_y = compute_cpk(s_y['mean'], s_y['stdev'],
                            sp.get('Y', {}).get('lsl', -5000), sp.get('Y', {}).get('usl', 5000))

        dev_spec = self.settings.get('spec_deviation', {})
        ds = dev_spec.get(short, dev_spec.get('default', {'spec_range': 4.0, 'spec_stddev': 0.8}))
        spec_r = ds.get('spec_range', 4.0)
        spec_s = ds.get('spec_stddev', 0.8)

        def _fill(lbl_avg, lbl_rng, lbl_std, lbl_cpk, lbl_badge, st, dev, cp):
            lbl_avg.configure(text=f"{st['mean']:.3f}")
            lbl_rng.configure(text=f"{dev['overall_range']:.3f}")
            lbl_std.configure(text=f"{dev['overall_stddev']:.3f}")
            lbl_cpk.configure(text=f"{cp:.2f}")
            r_ok = dev['overall_range'] <= spec_r
            s_ok = dev['overall_stddev'] <= spec_s
            if st['count'] == 0:
                lbl_badge.configure(text="NO DATA", style='Wait.TLabel')
            elif r_ok and s_ok:
                lbl_badge.configure(text="✅ PASS", style='Pass.TLabel')
            else:
                lbl_badge.configure(text="❌ FAIL", style='Fail.TLabel')

        _fill(self.lbl_x_avg, self.lbl_x_rng, self.lbl_x_std, self.lbl_x_cpk, self.lbl_x_badge, s_x, dev_x, cpk_x)
        _fill(self.lbl_y_avg, self.lbl_y_rng, self.lbl_y_std, self.lbl_y_cpk, self.lbl_y_badge, s_y, dev_y, cpk_y)

    def _update_die_avg_tables(self):
        for inner, stats in [(self.die_x_inner, self._dev_x.get('die_stats', [])),
                             (self.die_y_inner, self._dev_y.get('die_stats', []))]:
            self._fill_die_avg_heatmap(inner, stats)

    def _fill_die_avg_heatmap(self, inner_frame, die_stats: list):
        """Die Average 테이블을 히트맵 색상으로 렌더링 (전체 너비 사용)."""
        for w in inner_frame.winfo_children():
            w.destroy()

        if not die_stats:
            tk.Label(inner_frame, text="No data", bg=self._colors['bg2'],
                     fg=self._colors['fg2'], font=('Consolas', 11)).grid(row=0, column=0)
            return

        header_bg = self._colors['bg3']
        header_fg = self._colors['accent']
        cell_font = ('Consolas', 9)
        header_font = ('Segoe UI', 9, 'bold')
        n_cols = 4

        # Fill available width
        for c in range(n_cols):
            inner_frame.columnconfigure(c, weight=1)

        # Header row
        headers = ['Die', 'Avg (µm)', 'StdDev', 'Range']
        for j, h in enumerate(headers):
            tk.Label(inner_frame, text=h, bg=header_bg, fg=header_fg,
                     font=header_font, relief='flat',
                     padx=6, pady=3).grid(row=0, column=j, sticky='nsew')

        # Normalization bounds
        avgs = [ds['avg'] for ds in die_stats]
        stds = [ds['stddev'] for ds in die_stats]
        rngs = [ds['range'] for ds in die_stats]
        avg_max = max(abs(v) for v in avgs) if avgs else 1.0
        std_max = max(stds) if stds else 1.0
        rng_max = max(rngs) if rngs else 1.0

        # Data rows
        for i, ds in enumerate(die_stats):
            # Die label column (no heatmap)
            tk.Label(inner_frame, text=ds['die'], bg=header_bg,
                     fg=self._colors['fg'], font=('Segoe UI', 9, 'bold'),
                     anchor='w', relief='flat',
                     padx=6, pady=1).grid(row=i + 1, column=0, sticky='nsew')

            # Avg — bidirectional (blue-white-red)
            ratio_avg = ds['avg'] / avg_max if avg_max > 0 else 0
            bg_avg = self._heatmap_diverging(ratio_avg)
            fg_avg = self._get_contrast_color(bg_avg)
            tk.Label(inner_frame, text=f"{ds['avg']:.3f}", bg=bg_avg, fg=fg_avg,
                     font=cell_font, anchor='e', relief='flat',
                     padx=6, pady=1).grid(row=i + 1, column=1, sticky='nsew')

            # StdDev — single direction (white → steel blue)
            ratio_std = ds['stddev'] / std_max if std_max > 0 else 0
            bg_std = self._heatmap_single(ratio_std)
            fg_std = self._get_contrast_color(bg_std)
            tk.Label(inner_frame, text=f"{ds['stddev']:.3f}", bg=bg_std, fg=fg_std,
                     font=cell_font, anchor='e', relief='flat',
                     padx=6, pady=1).grid(row=i + 1, column=2, sticky='nsew')

            # Range — single direction (white → steel blue)
            ratio_rng = ds['range'] / rng_max if rng_max > 0 else 0
            bg_rng = self._heatmap_single(ratio_rng)
            fg_rng = self._get_contrast_color(bg_rng)
            tk.Label(inner_frame, text=f"{ds['range']:.3f}", bg=bg_rng, fg=fg_rng,
                     font=cell_font, anchor='e', relief='flat',
                     padx=6, pady=1).grid(row=i + 1, column=3, sticky='nsew')

        # Enable drag-select & copy
        self._make_grid_selectable(inner_frame, len(die_stats) + 1, n_cols)

    def _update_deviation_tables(self):
        self._fill_deviation_table(self.dev_x_inner, self._dev_x)
        self._fill_deviation_table(self.dev_y_inner, self._dev_y)

    def _update_summary_table(self, comparison):
        self.sum_tv.delete(*self.sum_tv.get_children())
        for c in comparison:
            self.sum_tv.insert('', 'end', values=(
                c.get('recipe', ''), c.get('round', ''), c.get('data_count', 0),
                f"{c.get('mean', 0):.1f}", f"{c.get('stdev', 0):.1f}",
                f"{c.get('min', 0):.1f}", f"{c.get('max', 0):.1f}",
                f"{c.get('cv_percent', 0):.1f}", c.get('outliers', 0)))

    def _update_raw_table(self):
        self.raw_tv.delete(*self.raw_tv.get_children())
        for r in self.raw_data:
            io = r.get('is_outlier', False)
            self.raw_tv.insert('', 'end', values=(
                r.get('lot_name', ''), r.get('site_id', ''),
                r.get('method', ''), f"{r.get('value', 0):.3f}",
                '✅' if r.get('valid', True) else '❌',
                '⚠️' if io else ''), tags=('outlier' if io else 'normal',))

    # ──────────────────────────────────────────────
    # Charts
    # ──────────────────────────────────────────────

    def _update_charts(self, data, trend, recipe):
        import matplotlib.pyplot as plt
        plt.close('all')
        short = recipe.get('short_name', '')

        self._embed('트렌드', viz.plot_trend_chart(trend, title=f'{short} Lot Trend'))
        self._embed('분포', viz.plot_boxplot(data, title=f'{short} Boxplot'))

        # Wafer Contour
        if self._dev_x.get('die_stats'):
            self._embed('Contour X', viz.plot_wafer_contour(
                self._dev_x['die_stats'], title=f'{short} — X Wafer Contour'))
        if self._dev_y.get('die_stats'):
            self._embed('Contour Y', viz.plot_wafer_contour(
                self._dev_y['die_stats'], title=f'{short} — Y Wafer Contour'))

        # X*Y Offset
        xy_prod = compute_xy_product(self._dev_x.get('die_stats', []), self._dev_y.get('die_stats', []))
        if xy_prod:
            prod_stats = [{'die': d, 'avg': v} for d, v in xy_prod.items()]
            self._embed('X*Y Offset', viz.plot_wafer_contour(prod_stats, title=f'{short} — X*Y Offset'))

        # XY Scatter
        self._embed('XY Scatter', viz.plot_xy_scatter(self._dev_x, self._dev_y,
                     title=f'{short} — XY Scatter'))

        # Vector Map
        if self._dev_x.get('die_stats') and self._dev_y.get('die_stats'):
            self._embed('↗️ Vector Map', viz.plot_vector_map(
                self._dev_x['die_stats'], self._dev_y['die_stats'],
                title=f'{short} — Vector Map'))

    def _render_die_position(self):
        self._embed('Die Position', viz.plot_die_position_map())

    def _embed(self, tab_name, fig):
        frame = self.chart_frames.get(tab_name)
        if not frame:
            return
        if tab_name == 'TIFF':
            self._embed_to(self.tiff_chart_frame, fig)
        elif tab_name in self.chart_content_frames:
            self._embed_to(self.chart_content_frames[tab_name], fig)
        else:
            self._embed_to(frame, fig)

    def _embed_to(self, frame, fig):
        for w in frame.winfo_children():
            w.destroy()
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        tb = ttk.Frame(frame)
        tb.pack(side='bottom', fill='x')
        NavigationToolbar2Tk(canvas, tb).update()
        canvas.get_tk_widget().pack(fill='both', expand=True)

    # ──────────────────────────────────────────────
    # Repeat Contour Popup
    # ──────────────────────────────────────────────

    def _open_repeat_contour(self, axis: str = 'X'):
        """Repeat별 Contour Map을 별도 Toplevel 창에 서브플롯으로 표시."""
        dev = self._dev_x if axis == 'X' else self._dev_y
        matrix = dev.get('matrix', {})
        die_labels = dev.get('die_labels', [])
        repeat_labels = dev.get('repeat_labels', [])

        if not repeat_labels or not die_labels:
            messagebox.showinfo("알림", f"{axis} 데이터가 없습니다.")
            return

        win = tk.Toplevel(self)
        win.title(f"Repeat별 Contour Map — {axis} Offset")
        win.geometry("1200x700")
        win.configure(bg='#1e1e2e')

        # Build per-repeat die_stats
        from scipy.interpolate import griddata
        from matplotlib.patches import Circle
        from matplotlib.colors import Normalize
        import matplotlib.pyplot as plt

        n = len(repeat_labels)
        cols = min(5, n)
        rows = math.ceil(n / cols)

        fig, axes = plt.subplots(rows, cols, figsize=(4.5 * cols, 4.5 * rows),
                                  dpi=120)
        fig.patch.set_facecolor('#ffffff')
        if rows == 1 and cols == 1:
            axes = [[axes]]
        elif rows == 1:
            axes = [axes]
        elif cols == 1:
            axes = [[ax] for ax in axes]

        # Global value range for consistent color scale
        all_vals = []
        for rl in repeat_labels:
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                if v is not None:
                    all_vals.append(abs(v))
        vmax_global = max(all_vals) if all_vals else 1.0

        for idx, rl in enumerate(repeat_labels):
            r, c = divmod(idx, cols)
            ax = axes[r][c]

            positions, values = [], []
            for dl in die_labels:
                v = matrix.get(rl, {}).get(dl)
                pos = get_die_position(dl)
                if v is not None and pos is not None:
                    positions.append(pos)
                    values.append(v)

            if len(positions) < 3:
                ax.text(0.5, 0.5, 'N/A', ha='center', va='center',
                        transform=ax.transAxes, fontsize=11)
                ax.set_title(rl, fontsize=10, fontweight='bold')
                continue

            import numpy as np
            xs = np.array([p[0] for p in positions], dtype=float)
            ys = np.array([p[1] for p in positions], dtype=float)
            zs = np.array(values, dtype=float)

            grid_res = 200
            margin = 1.0
            x_range = np.linspace(xs.min() - margin, xs.max() + margin, grid_res)
            y_range = np.linspace(ys.min() - margin, ys.max() + margin, grid_res)
            xi, yi = np.meshgrid(x_range, y_range)
            zi = griddata((xs, ys), zs, (xi, yi), method='cubic')

            wafer_r = max(abs(xs).max(), abs(ys).max()) + margin
            dist = np.sqrt(xi**2 + yi**2)
            zi[dist > wafer_r] = np.nan

            norm = Normalize(vmin=-vmax_global, vmax=vmax_global)
            ax.contourf(xi, yi, zi, levels=50, cmap='RdYlGn', norm=norm, extend='both')
            ax.add_patch(Circle((0, 0), wafer_r, fill=False, edgecolor='#555',
                                linewidth=1.2, linestyle='--'))
            ax.scatter(xs, ys, c='black', s=12, zorder=5, marker='o', edgecolors='white', linewidths=0.3)

            # Annotate die values
            for pi, vi in zip(positions, values):
                ax.annotate(f'{vi:.2f}', (pi[0], pi[1]), fontsize=6,
                            ha='center', va='bottom', color='black', fontweight='bold')

            ax.set_aspect('equal')
            ax.set_title(rl, fontsize=10, fontweight='bold')
            ax.tick_params(labelsize=7)

        # Hide unused subplots
        for idx in range(n, rows * cols):
            r, c = divmod(idx, cols)
            axes[r][c].set_visible(False)

        fig.suptitle(f'{axis} Offset — Repeat별 Contour Map', fontsize=14, fontweight='bold')
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        # Embed in Toplevel
        canvas = FigureCanvasTkAgg(fig, master=win)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

        # Download button
        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill='x', pady=4)

        def save_image():
            path = filedialog.asksaveasfilename(
                parent=win, title="이미지 다운로드",
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("SVG", "*.svg")],
                initialfile=f"Repeat_Contour_{axis}.png")
            if path:
                fig.savefig(path, dpi=300, bbox_inches='tight')
                self.logger.ok(f"이미지 저장: {path}")

        ttk.Button(btn_frame, text="📥 이미지 다운로드", style='Accent.TButton',
                   command=save_image).pack(side='right', padx=8)

    # ──────────────────────────────────────────────
    # TIFF
    # ──────────────────────────────────────────────

    def _find_tiff_for_row(self, lot_name, site_id):
        lot_info = next((l for l in self.lot_list if l['lot_name'] == lot_name), None)
        if not lot_info:
            return []
        return [os.path.join(lot_info['path'], t)
                for t in lot_info.get('tiff_files', []) if site_id in t]

    def _on_row_double_click(self, event):
        sel = self.raw_tv.selection()
        if not sel:
            return
        vals = self.raw_tv.item(sel[0])['values']
        lot_name, site_id = vals[0], vals[1]

        tiff_paths = self._find_tiff_for_row(lot_name, site_id)
        if not tiff_paths:
            self.status_text.set(f"⚠ TIFF 없음: {lot_name}/{site_id}")
            return

        self.last_tiff_folder = os.path.dirname(tiff_paths[0])
        self.tiff_path_label.configure(text=self.last_tiff_folder)
        self.logger.info(f"TIFF 로드: {lot_name}/{site_id} ({len(tiff_paths)}개)")

        def load():
            try:
                from tiff_loader import load_tiff
                results = [load_tiff(tp) for tp in tiff_paths]
                self.after(0, lambda: self._show_tiff_profiles(results, lot_name, site_id))
            except Exception as e:
                self.after(0, lambda: self.logger.error(f"TIFF 오류: {e}"))

        threading.Thread(target=load, daemon=True).start()

    def _show_tiff_profiles(self, tiff_results, lot_name, site_id):
        from matplotlib.figure import Figure
        n = len(tiff_results)
        if n == 0:
            return
        fig = Figure(figsize=(14, 5 * max(1, (n + 1) // 2)))
        rows = max(1, (n + 1) // 2)
        cols = min(n, 2)
        for i, tr in enumerate(tiff_results):
            ax = fig.add_subplot(rows, cols, i + 1)
            profile = tr['data_2d'].flatten()
            info = tr['info']
            scan_size = info.get('scan_size_width', 0) or info.get('scan_size_height', 0)
            if scan_size and scan_size > 0:
                x_axis = [scan_size * j / len(profile) for j in range(len(profile))]
                ax.set_xlabel('Position (μm)')
            else:
                x_axis = list(range(len(profile)))
                ax.set_xlabel('Pixel')
            ax.plot(x_axis, profile, color='#1565C0', linewidth=0.5)
            ax.set_ylabel(f'Z ({info.get("z_unit", "")})')
            ax.set_title(f'{tr["filename"]}\n{info.get("channel_name","")} '
                         f'[{info.get("head_mode","")}]', fontsize=8)
            ax.grid(True, alpha=0.3)
        fig.suptitle(f'{lot_name} / {site_id} — TIFF Profile', fontsize=11, fontweight='bold')
        fig.tight_layout()
        self._embed_to(self.tiff_chart_frame, fig)
        self.chart_tabs.select(self.chart_frames['TIFF'])

    def _open_tiff_folder(self):
        if self.last_tiff_folder and os.path.isdir(self.last_tiff_folder):
            subprocess.Popen(['explorer', self.last_tiff_folder])
        else:
            messagebox.showinfo("알림", "먼저 Raw Data 행을 더블클릭하여 TIFF를 로드하세요.")

    # ──────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────

    def _export_csv(self):
        if not self.raw_data:
            messagebox.showwarning("경고", "먼저 분석을 실행해주세요."); return
        path = filedialog.asksaveasfilename(title="CSV", defaultextension=".txt",
             filetypes=[("Text", "*.txt"), ("CSV", "*.csv")], initialfile="Analysis.txt")
        if path:
            export_combined_csv(self.raw_data, path)
            self.logger.ok(f"CSV 저장: {path}")

    def _export_excel(self):
        if not self.raw_data:
            messagebox.showwarning("경고", "먼저 분석을 실행해주세요."); return
        path = filedialog.asksaveasfilename(title="Excel", defaultextension=".xlsx",
             filetypes=[("Excel", "*.xlsx")], initialfile="Report.xlsx")
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
            messagebox.showwarning("경고", "스캔된 데이터가 없습니다."); return
        path = filedialog.asksaveasfilename(title="PDF", defaultextension=".pdf",
             filetypes=[("PDF", "*.pdf")], initialfile="Report.pdf")
        if not path:
            return
        self.logger.info("PDF 리포트 생성 중...")
        def run():
            try:
                results = load_all_recipes(self.folder_path.get(), round_name='1st', axis='both')
                comp = compare_recipes(results)
                from pdf_generator import generate_pdf_report
                generate_pdf_report(path, self.folder_path.get(), results, comp,
                                    self.settings.get('spec_limits', {}))
                self.after(0, lambda: self.logger.ok(f"PDF 저장 완료: {path}"))
                os.startfile(path)
            except Exception as e:
                self.after(0, lambda: self.logger.error(f"PDF 오류: {e}"))
        threading.Thread(target=run, daemon=True).start()

    def _open_spec_config(self):
        messagebox.showinfo("Spec",
            "settings.json 의 spec_limits / spec_deviation 섹션을 직접 수정하세요.\n\n"
            f"파일 위치:\n{os.path.join(os.path.dirname(__file__), 'settings.json')}")


def main():
    app = DataAnalyzerApp()
    app.mainloop()


if __name__ == '__main__':
    main()
