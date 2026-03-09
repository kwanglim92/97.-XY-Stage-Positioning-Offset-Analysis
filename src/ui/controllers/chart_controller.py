from PySide6.QtCore import QTimer
import charts as viz
import charts as viz_pg
from core import compute_deviation_matrix, compute_xy_product, extract_die_positions
from core import compute_statistics, filter_by_method
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


class ChartMixin:
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
            self.chart_widgets['Distribution X'].set_widget(
                viz_pg.create_histogram_widget(x_data, title=f'{short} X Distribution'))
        except Exception as e:
            self.logger.error(f"분포 X 차트 오류: {e}")

        try:
            y_data = [r for r in data if r.get('method') == 'Y']
            self.chart_widgets['Distribution Y'].set_widget(
                viz_pg.create_histogram_widget(y_data, title=f'{short} Y Distribution'))
        except Exception as e:
            self.logger.error(f"분포 Y 차트 오류: {e}")

        # Spec Range 가이드 박스용 스펙 가져오기
        dev_spec = self.settings.get('spec_deviation', {})
        ds = dev_spec.get(short, {})
        self._xy_spec_range = ds.get('spec_range', None)

        try:
            self.chart_widgets['XY Scatter'].set_widget(
                viz_pg.create_scatter_widget(
                    self._dev_x, self._dev_y, title=f'{short} — XY Scatter',
                    log_mode=self._xy_log_mode,
                    spec_range=self._xy_spec_range))
            self._rebuild_xy_legend()
        except Exception as e:
            self.logger.error(f"XY Scatter 차트 오류: {e}")

        # 후속 차트 (Pareto, Correlation, 3D, Contour, Vector)
        self._update_charts_remaining(data, result, recipe)


    def _update_charts_remaining(self, data, result, recipe):
        """_update_charts에서 분리된 후속 차트 갱신."""
        import matplotlib.pyplot as plt
        short = recipe.get('short_name', '')

        # ─── Pareto Chart (이상치 분석) ───
        try:
            pareto = compute_pareto_data(data, group_by='die')
            self.chart_widgets['Pareto'].set_widget(
                viz_pg.create_pareto_widget(pareto, title=f'{short} — Pareto'))
        except Exception as e:
            self.logger.error(f"Pareto 차트 오류: {e}")

        # ─── Correlation Chart (X/Y 상관관계) ───
        try:
            if self._dev_x.get('die_stats') and self._dev_y.get('die_stats'):
                corr = compute_correlation(
                    self._dev_x['die_stats'], self._dev_y['die_stats'])
                self.chart_widgets['Correlation'].set_widget(
                    viz_pg.create_correlation_widget(
                        corr, title=f'{short} — X/Y Correlation'))
        except Exception as e:
            self.logger.error(f"Correlation 차트 오류: {e}")

        # ─── 3D Surface (OpenGL) ─ X/Y 분리 ───
        for axis_key, dev in [('X', self._dev_x), ('Y', self._dev_y)]:
            try:
                ds = dev.get('die_stats')
                if ds:
                    self.chart_widgets[f'3D {axis_key}'].set_widget(
                        viz_pg.create_3d_surface_widget(
                            ds, title=f'{short} — 3D {axis_key} Surface'))
            except Exception as e:
                self.logger.error(f"3D {axis_key} Surface 오류: {e}")

        # ─── matplotlib 차트 (Contour/Vector — scipy 보간) ───
        wr = self._get_wafer_radius_um()
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
                self.chart_widgets['Vector Map'].set_figure(
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
            self.chart_widgets['Vector Map'].set_figure(
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

