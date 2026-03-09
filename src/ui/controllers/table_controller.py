from ui.widgets.copyable_table import CopyableTable
from PySide6.QtWidgets import QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from ui.color_helpers import _heatmap_diverging, _heatmap_single, _contrast_fg
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


class TableMixin:
    def _update_summary_table(self, comparison, recipe_results=None):
        from core import (compute_deviation_matrix, compute_statistics,
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
                item.setTextAlignment(Qt.AlignCenter)
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

