from PySide6.QtWidgets import QWidget, QHBoxLayout, QCheckBox, QLabel
from PySide6.QtCore import Qt, QSize
import visualizer as viz
from analyzer import extract_die_positions


class XYLegendMixin:
    def _toggle_xy_log_scale(self):
        """🎯 XY Scatter Log 스케일 토글."""
        self._xy_log_mode = self._xy_log_btn.isChecked()
        if self.recipe_results and self.current_recipe_idx < len(self.recipe_results):
            short = self.recipes[self.current_recipe_idx].get('short_name', '')
            try:
                self.chart_widgets['XY Scatter'].set_widget(
                    viz_pg.create_scatter_widget(
                        self._dev_x, self._dev_y,
                        title=f'{short} — XY Scatter',
                        log_mode=self._xy_log_mode,
                        spec_range=getattr(self, '_xy_spec_range', None)))
                self._rebuild_xy_legend()
            except Exception as e:
                self.logger.error(f"XY Scatter Log 토글 오류: {e}")


    def _rebuild_xy_legend(self):
        """XY Scatter 사이드 범례 패널 재구성."""
        from visualizer_pg import _DIE_COLORS

        # 기존 버튼 제거
        while self._xy_legend_btn_layout.count() > 0:
            item = self._xy_legend_btn_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        self._xy_legend_buttons.clear()
        self._xy_highlighted_dies = set()

        # scatter 위젯에서 Die 목록 가져오기
        scatter_w = self._xy_scatter_chart.get_widget()
        if scatter_w is None or not hasattr(scatter_w, '_scatter_items'):
            return

        for scatter, die_label, _, _ in scatter_w._scatter_items:
            idx = int(die_label.replace('Die', ''))
            color = _DIE_COLORS[idx % len(_DIE_COLORS)]

            btn = QPushButton(f"■ {die_label}")
            btn.setFixedHeight(28)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(f"""
                QPushButton {{ background: transparent; color: {color};
                              border: 1px solid transparent; border-radius: 3px;
                              font-size: 9pt; font-weight: bold; text-align: left;
                              padding-left: 4px; }}
                QPushButton:hover {{ border-color: {color}; background: {color}22; }}
            """)
            btn.clicked.connect(partial(self._xy_legend_on_die_click, die_label, color))
            self._xy_legend_btn_layout.addWidget(btn)
            self._xy_legend_buttons[die_label] = btn

        self._xy_legend_btn_layout.addStretch()


    def _xy_legend_on_die_click(self, die_label, color):
        """사이드 범례 Die 버튼 클릭 → 하이라이트 토글 (복수 선택)."""
        scatter_w = self._xy_scatter_chart.get_widget()
        if scatter_w is None or not hasattr(scatter_w, 'highlight_die'):
            return

        # scatter 위젯 내부에서 set 토글 + 시각 반영
        scatter_w.highlight_die(die_label)

        # 범례 상태 동기화
        if die_label in self._xy_highlighted_dies:
            self._xy_highlighted_dies.discard(die_label)
        else:
            self._xy_highlighted_dies.add(die_label)
        self._xy_legend_update_styles()


    def _xy_legend_reset(self):
        """전체 표시 — 모든 Die 복원."""
        scatter_w = self._xy_scatter_chart.get_widget()
        if scatter_w and hasattr(scatter_w, '_restore_all'):
            scatter_w._restore_all()
        self._xy_highlighted_dies = set()
        self._xy_legend_update_styles()


    def _xy_legend_update_styles(self):
        """범례 버튼 스타일 갱신 — 하이라이트된 Die 강조."""
        from visualizer_pg import _DIE_COLORS
        for die_label, btn in self._xy_legend_buttons.items():
            idx = int(die_label.replace('Die', ''))
            color = _DIE_COLORS[idx % len(_DIE_COLORS)]

            if not self._xy_highlighted_dies:
                # 전체 표시
                btn.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: {color};
                                  border: 1px solid transparent; border-radius: 3px;
                                  font-size: 9pt; font-weight: bold; text-align: left;
                                  padding-left: 4px; }}
                    QPushButton:hover {{ border-color: {color}; background: {color}22; }}
                """)
            elif die_label in self._xy_highlighted_dies:
                # 강조
                btn.setStyleSheet(f"""
                    QPushButton {{ background: {color}33; color: {color};
                                  border: 2px solid {color}; border-radius: 3px;
                                  font-size: 9pt; font-weight: bold; text-align: left;
                                  padding-left: 4px; }}
                """)
            else:
                # 비활성
                btn.setStyleSheet(f"""
                    QPushButton {{ background: transparent; color: #555;
                                  border: 1px solid transparent; border-radius: 3px;
                                  font-size: 9pt; text-align: left;
                                  padding-left: 4px; }}
                    QPushButton:hover {{ border-color: #555; }}
                """)


    # ──────────────────────────────────────────────
    # _update_charts 후속 — Pareto / Correlation / 3D / Contour / Vector
    # ──────────────────────────────────────────────





