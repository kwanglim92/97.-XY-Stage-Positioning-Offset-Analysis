from ui.widgets.copyable_table import CopyableTable
from PySide6.QtWidgets import QTableWidgetItem, QHeaderView
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from ui.color_helpers import _heatmap_diverging, _heatmap_single, _contrast_fg
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


# ── Summary 테이블 행 레이아웃 — ui_builder_mixin과 공유하는 단일 출처 ──
#  Row 0    : Checklist 그룹 헤더
#  Row 1-4  : Checklist (X/Y Dev Range, X/Y Dev StdDev)
#  Row 5-6  : X / Y Result
#  Row 7    : Statistics 그룹 헤더
#  Row 8-15 : 통계 상세 (R, N, Mean, StdDev, Min, Max, CV%, Outliers)
SUMMARY_ROW_LABELS = [
    'Checklist',                                       # 0
    'X Dev Range (µm)', 'Y Dev Range (µm)',            # 1, 2
    'X Dev StdDev (µm)', 'Y Dev StdDev (µm)',          # 3, 4
    'X Result', 'Y Result',                            # 5, 6
    'Statistics',                                      # 7
    'R', 'N', 'Mean', 'StdDev', 'Min', 'Max', 'CV%', 'Outliers',  # 8-15
]
SUMMARY_GROUP_HEADER_ROWS = (0, 7)
SUMMARY_CHK_ROWS = (1, 2, 3, 4)
ROW_X_RANGE, ROW_Y_RANGE, ROW_X_STD, ROW_Y_STD = 1, 2, 3, 4
ROW_X_RESULT, ROW_Y_RESULT = 5, 6
ROW_R, ROW_N, ROW_MEAN, ROW_STDDEV, ROW_MIN, ROW_MAX, ROW_CV, ROW_OUT = range(8, 16)


class TableMixin:
    def _update_summary_table(self, comparison, recipe_results=None):
        from core import (compute_deviation_matrix, filter_stabilization_die,
                          compute_statistics, filter_by_method, evaluate_deviation_pass)
        t = self.sum_table
        recipe_results = recipe_results or []
        dev_spec = self.settings.get('spec_deviation', {})
        n = len(comparison)

        # 열 = Recipe 이름
        t.setColumnCount(n)
        t.setHorizontalHeaderLabels([c.get('recipe', f'R{i+1}')
                                     for i, c in enumerate(comparison)])

        # ── 그룹 헤더 행: 셀은 비운 채 빈 아이템으로 채움 ──
        # (텍스트는 수직 헤더 레이블로만 표시)
        for _hdr_row in SUMMARY_GROUP_HEADER_ROWS:
            for c in range(n):
                it = QTableWidgetItem('')
                it.setFlags(Qt.ItemIsEnabled)
                t.setItem(_hdr_row, c, it)


        TOOLTIP_CHK = '체크리스트 기입 항목입니다'

        for col, c in enumerate(comparison):
            recipe_name = c.get('recipe', '')
            ds = dev_spec.get(recipe_name, {})
            spec_r = ds.get('spec_range')
            spec_s = ds.get('spec_stddev')

            result = recipe_results[col] if col < len(recipe_results) else {}
            raw    = result.get('raw_data', []) if result else []
            # 안정화 Die(#1, 첫 측정 site) 제외 — 체크리스트는 Die 필터와 무관하게
            # 항상 21 Die 기준으로 고정 (guide_dialog 5.0 참조).
            data   = filter_stabilization_die(raw)

            x_range = x_std = y_range = y_std = None
            px = py = None

            if data:
                dx = compute_deviation_matrix(data, 'X')
                dy = compute_deviation_matrix(data, 'Y')
                x_range = dx.get('overall_range')
                x_std   = dx.get('overall_stddev')
                y_range = dy.get('overall_range')
                y_std   = dy.get('overall_stddev')
                # PASS/FAIL은 core.evaluate_deviation_pass 단일 출처 사용.
                # 축별 count로 판정하므로 한 축 데이터가 없으면(예: Y 미측정)
                # overall_range=0으로 인한 허위 PASS 대신 None('—')이 된다.
                sx = compute_statistics(filter_by_method(data, 'X'))
                sy = compute_statistics(filter_by_method(data, 'Y'))
                px = evaluate_deviation_pass(sx, dx, spec_r, spec_s)
                py = evaluate_deviation_pass(sy, dy, spec_r, spec_s)

            def _chk_item(val, spec):
                """체크리스트 수치 셀 — 값만, Spec 초과면 빨간 배경, 볼드."""
                if val is None:
                    it = QTableWidgetItem('—')
                    it.setBackground(QColor(BG2)); it.setForeground(QColor(FG2))
                else:
                    it = QTableWidgetItem(f'{val:.3f}')
                    if spec is not None and val > spec:
                        it.setBackground(QColor(RED)); it.setForeground(QColor(BG))
                    else:
                        it.setBackground(QColor(BG2))
                        it.setForeground(QColor(GREEN if (spec and val <= spec) else FG))
                    from PySide6.QtGui import QFont as _QFont
                    f = it.font(); f.setBold(True); it.setFont(f)
                it.setTextAlignment(Qt.AlignCenter)
                it.setToolTip(TOOLTIP_CHK)
                return it

            def _flag_item(flag):
                if flag is None:
                    it = QTableWidgetItem('—')
                    it.setBackground(QColor(BG3)); it.setForeground(QColor(FG2))
                elif flag:
                    it = QTableWidgetItem('PASS')
                    it.setBackground(QColor(GREEN)); it.setForeground(QColor(BG))
                else:
                    it = QTableWidgetItem('FAIL')
                    it.setBackground(QColor(RED)); it.setForeground(QColor(BG))
                it.setTextAlignment(Qt.AlignCenter)
                return it

            def _stat_item(text):
                it = QTableWidgetItem(str(text))
                it.setTextAlignment(Qt.AlignCenter)
                it.setBackground(QColor(BG2)); it.setForeground(QColor(FG))
                return it

            # Checklist (그룹 헤더 다음)
            t.setItem(ROW_X_RANGE, col, _chk_item(x_range, spec_r))
            t.setItem(ROW_Y_RANGE, col, _chk_item(y_range, spec_r))
            t.setItem(ROW_X_STD,   col, _chk_item(x_std,   spec_s))
            t.setItem(ROW_Y_STD,   col, _chk_item(y_std,   spec_s))
            # Result
            t.setItem(ROW_X_RESULT, col, _flag_item(px))
            t.setItem(ROW_Y_RESULT, col, _flag_item(py))
            # 통계 상세 (그룹 헤더 다음)
            t.setItem(ROW_R,      col, _stat_item(c.get('round', '—')))
            t.setItem(ROW_N,      col, _stat_item(c.get('data_count', '—')))
            t.setItem(ROW_MEAN,   col, _stat_item(f"{c.get('mean', 0):.1f}"))
            t.setItem(ROW_STDDEV, col, _stat_item(f"{c.get('stdev', 0):.1f}"))
            t.setItem(ROW_MIN,    col, _stat_item(f"{c.get('min', 0):.1f}"))
            t.setItem(ROW_MAX,    col, _stat_item(f"{c.get('max', 0):.1f}"))
            t.setItem(ROW_CV,     col, _stat_item(f"{c.get('cv_percent', 0):.1f}"))
            t.setItem(ROW_OUT,    col, _stat_item(c.get('outliers', 0)))


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
            item_die.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 0, item_die)
            # Avg — diverging
            bg = _heatmap_diverging(ds['avg'] / avg_max if avg_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['avg']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 1, item)
            # StdDev — single
            bg = _heatmap_single(ds['stddev'] / std_max if std_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['stddev']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignCenter)
            table.setItem(i, 2, item)
            # Range — single
            bg = _heatmap_single(ds['range'] / rng_max if rng_max > 0 else 0)
            item = QTableWidgetItem(f"{ds['range']:.3f}")
            item.setBackground(bg); item.setForeground(_contrast_fg(bg))
            item.setTextAlignment(Qt.AlignCenter)
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
            item_rl.setTextAlignment(Qt.AlignCenter)
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

