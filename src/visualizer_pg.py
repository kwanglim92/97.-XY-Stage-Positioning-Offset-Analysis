"""
visualizer_pg.py — pyqtgraph 기반 인터랙티브 차트 모듈

Matplotlib 대비 개선점:
  - GPU(OpenGL) 가속 렌더링
  - 마우스 휠/드래그 즉시 줌/패닝
  - CrossHair + 호버 데이터 피킹
  - 위젯 인스턴스 재사용 (메모리 효율)
"""

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor

from analyzer import DIE_POSITIONS, get_die_position

# ═══════════════════════════════════════════════
#  Catppuccin Mocha 다크 테마
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

# pyqtgraph global config
pg.setConfigOptions(
    background=BG,
    foreground=FG,
    antialias=True,
)

# Die별 고유 색상 팔레트 (21 Dies)
_DIE_COLORS = [
    '#f38ba8', '#fab387', '#f9e2af', '#a6e3a1', '#94e2d5',
    '#89dceb', '#74c7ec', '#89b4fa', '#b4befe', '#cba6f7',
    '#f5c2e7', '#eba0ac', '#f2cdcd', '#f5e0dc', '#e6c384',
    '#7dc4e4', '#8aadf4', '#c6a0f6', '#ee99a0', '#a6da95',
    '#8bd5ca',
]


def _make_pen(color, width=2, style=None):
    """QPen 생성 헬퍼."""
    pen = pg.mkPen(color=color, width=width)
    if style == 'dash':
        pen.setStyle(Qt.DashLine)
    elif style == 'dot':
        pen.setStyle(Qt.DotLine)
    return pen


def _style_axis(plot_item, title='', x_label='', y_label=''):
    """PlotItem 공통 스타일 설정."""
    title_style = {'color': ACCENT, 'size': '12pt', 'bold': True}
    label_style = {'color': FG2, 'font-size': '10pt'}
    plot_item.setTitle(title, **title_style)
    plot_item.setLabel('bottom', x_label, **label_style)
    plot_item.setLabel('left', y_label, **label_style)
    plot_item.showGrid(x=True, y=True, alpha=0.15)
    plot_item.getViewBox().setBackgroundColor(BG2)

    # 축 스타일
    for axis_name in ('bottom', 'left', 'top', 'right'):
        ax = plot_item.getAxis(axis_name)
        ax.setPen(pg.mkPen(color='#45475a'))
        ax.setTextPen(pg.mkPen(color=FG2))


# ═══════════════════════════════════════════════
#  1. Trend Chart (Lot별 Mean ± 1σ + CrossHair)
# ═══════════════════════════════════════════════

class CrossHairPlotWidget(pg.PlotWidget):
    """마우스 위치 추적 CrossHair가 내장된 PlotWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._v_line = pg.InfiniteLine(angle=90, movable=False,
                                        pen=pg.mkPen(ACCENT, width=1, style=Qt.DotLine))
        self._h_line = pg.InfiniteLine(angle=0, movable=False,
                                        pen=pg.mkPen(ACCENT, width=1, style=Qt.DotLine))
        self.addItem(self._v_line, ignoreBounds=True)
        self.addItem(self._h_line, ignoreBounds=True)

        self._label = pg.TextItem(anchor=(0, 1), color=FG, fill=pg.mkBrush(BG3 + 'CC'))
        self._label.setFont(QFont('Consolas', 9))
        self.addItem(self._label, ignoreBounds=True)

        self._data_points = []  # (x, y, label) 리스트
        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def set_data_points(self, points):
        """CrossHair가 스냅할 데이터 포인트 설정. [(x, y, label), ...]"""
        self._data_points = points

    def _on_mouse_moved(self, pos):
        if not self.sceneBoundingRect().contains(pos):
            return
        mouse_pt = self.plotItem.vb.mapSceneToView(pos)
        mx, my = mouse_pt.x(), mouse_pt.y()
        self._v_line.setPos(mx)
        self._h_line.setPos(my)

        # 가장 가까운 데이터 포인트 찾기
        if self._data_points:
            min_dist = float('inf')
            closest = None
            for x, y, lbl in self._data_points:
                dist = abs(x - mx)  # X축 기준 가장 가까운 점
                if dist < min_dist:
                    min_dist = dist
                    closest = (x, y, lbl)
            if closest:
                self._label.setText(f"{closest[2]}\n{closest[1]:.2f}")
                self._label.setPos(closest[0], closest[1])


def create_trend_widget(trend_data: list, title: str = 'Lot Trend') -> CrossHairPlotWidget:
    """Lot별 측정값 트렌드 차트 — pyqtgraph 인터랙티브 버전.

    Features:
      - Mean ± 1σ 밴드
      - Min/Max 점선
      - Overall Mean 수평선
      - CrossHair 마우스 추적
    """
    w = CrossHairPlotWidget()
    plot = w.plotItem
    _style_axis(plot, title=title, x_label='Lot Index', y_label='HZ1_O (nm)')

    if not trend_data:
        return w

    indices = np.array([t['lot_index'] for t in trend_data], dtype=float)
    means = np.array([t['mean'] for t in trend_data])
    stdevs = np.array([t['stdev'] for t in trend_data])
    labels = [t['lot_name'] for t in trend_data]
    mins = np.array([t['min'] for t in trend_data])
    maxs = np.array([t['max'] for t in trend_data])

    # ±1σ 밴드
    upper = means + stdevs
    lower = means - stdevs
    fill_upper = pg.PlotCurveItem(indices, upper, pen=pg.mkPen(None))
    fill_lower = pg.PlotCurveItem(indices, lower, pen=pg.mkPen(None))
    fill = pg.FillBetweenItem(fill_upper, fill_lower,
                               brush=pg.mkBrush(ACCENT + '25'))
    w.addItem(fill_upper)
    w.addItem(fill_lower)
    w.addItem(fill)

    # Mean line
    w.plot(indices, means, pen=_make_pen(ACCENT, 2),
           symbol='o', symbolBrush=ACCENT, symbolSize=7,
           name='Mean')

    # Min/Max 점선  (pyqtgraph: 't'=triangle-down, 't1'=triangle-up)
    w.plot(indices, mins, pen=_make_pen(RED, 1, 'dot'),
           symbol='t', symbolBrush=RED, symbolSize=5, name='Min')
    w.plot(indices, maxs, pen=_make_pen(GREEN, 1, 'dot'),
           symbol='t1', symbolBrush=GREEN, symbolSize=5, name='Max')

    # Overall Mean
    overall_mean = float(np.mean(means))
    inf_line = pg.InfiniteLine(pos=overall_mean, angle=0,
                                pen=_make_pen('#888888', 1, 'dash'),
                                label=f'Overall: {overall_mean:.1f}',
                                labelOpts={'color': FG2, 'position': 0.05})
    w.addItem(inf_line)

    # Legend
    legend = plot.addLegend(offset=(10, 10), labelTextColor=FG2,
                             brush=pg.mkBrush(BG3 + 'CC'))

    # X축 틱 라벨 설정
    ticks = [(int(idx), lbl) for idx, lbl in zip(indices, labels)]
    plot.getAxis('bottom').setTicks([ticks])

    # CrossHair 데이터 포인트
    pts = [(float(idx), float(m), lbl) for idx, m, lbl in zip(indices, means, labels)]
    w.set_data_points(pts)

    # 자동 범위 + 약간의 여유
    plot.enableAutoRange()

    return w


# ═══════════════════════════════════════════════
#  2. XY Scatter (Die별 색상 + Hover 정보)
# ═══════════════════════════════════════════════

class HoverScatterWidget(pg.PlotWidget):
    """마우스 호버 시 가장 가까운 점의 정보를 표시하는 ScatterPlot."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scatter_items = []  # (ScatterPlotItem, die_label) 리스트
        self._tooltip = pg.TextItem(anchor=(0, 1), color=FG,
                                     fill=pg.mkBrush(BG3 + 'DD'))
        self._tooltip.setFont(QFont('Consolas', 9))
        self._tooltip.setZValue(100)
        self.addItem(self._tooltip, ignoreBounds=True)
        self._tooltip.hide()

        # 강조 원
        self._highlight = pg.ScatterPlotItem(size=16, pen=pg.mkPen('white', width=2),
                                              brush=pg.mkBrush(None))
        self._highlight.setZValue(99)
        self.addItem(self._highlight)

        self.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def add_die_scatter(self, x, y, die_label, color):
        """Die 하나의 산점도를 추가."""
        scatter = pg.ScatterPlotItem(x, y, size=8,
                                      pen=pg.mkPen(None),
                                      brush=pg.mkBrush(color + 'CC'),
                                      name=die_label)
        self.addItem(scatter)
        self._scatter_items.append((scatter, die_label, x, y))

    def _on_mouse_moved(self, pos):
        if not self.sceneBoundingRect().contains(pos):
            self._tooltip.hide()
            self._highlight.setData([], [])
            return
        mouse_pt = self.plotItem.vb.mapSceneToView(pos)
        mx, my = mouse_pt.x(), mouse_pt.y()

        min_dist_sq = float('inf')
        closest = None
        for scatter, die_label, xs, ys in self._scatter_items:
            for x, y in zip(xs, ys):
                d = (x - mx) ** 2 + (y - my) ** 2
                if d < min_dist_sq:
                    min_dist_sq = d
                    closest = (x, y, die_label)

        threshold = 0.3  # 표시 임계 거리 (µm)
        if closest and min_dist_sq < threshold ** 2:
            cx, cy, lbl = closest
            self._tooltip.setText(f"{lbl}\nX: {cx:+.3f} µm\nY: {cy:+.3f} µm")
            self._tooltip.setPos(cx, cy)
            self._tooltip.show()
            self._highlight.setData([cx], [cy])
        else:
            self._tooltip.hide()
            self._highlight.setData([], [])


def create_scatter_widget(x_dev_result: dict, y_dev_result: dict,
                           title: str = 'XY Scatter') -> HoverScatterWidget:
    """X/Y Deviation Die별 산점도 — pyqtgraph 인터랙티브 버전.

    Features:
      - Die별 고유 색상
      - 마우스 호버 → Die명, X/Y 값 표시
      - ±5µm 격자 + Zero 십자선
    """
    w = HoverScatterWidget()
    plot = w.plotItem
    _style_axis(plot, title=title, x_label='X Offset (µm)', y_label='Y Offset (µm)')

    die_labels = x_dev_result.get('die_labels', [])
    repeat_labels = x_dev_result.get('repeat_labels', [])
    x_matrix = x_dev_result.get('matrix', {})
    y_matrix = y_dev_result.get('matrix', {})

    for dl in die_labels:
        idx = int(dl.replace('Die', ''))
        color = _DIE_COLORS[idx % len(_DIE_COLORS)]
        xvals, yvals = [], []
        for rl in repeat_labels:
            xv = x_matrix.get(rl, {}).get(dl)
            yv = y_matrix.get(rl, {}).get(dl)
            if xv is not None and yv is not None:
                xvals.append(xv)
                yvals.append(yv)
        if xvals:
            w.add_die_scatter(np.array(xvals), np.array(yvals), dl, color)

    # Zero 십자선
    w.addItem(pg.InfiniteLine(pos=0, angle=0, pen=_make_pen('#45475a', 1, 'dash')))
    w.addItem(pg.InfiniteLine(pos=0, angle=90, pen=_make_pen('#45475a', 1, 'dash')))

    # ±5µm 범위
    plot.setXRange(-5, 5)
    plot.setYRange(-5, 5)
    plot.setAspectLocked(True)

    # Legend
    plot.addLegend(offset=(10, 10), labelTextColor=FG2,
                    brush=pg.mkBrush(BG3 + 'AA'),
                    colCount=3)

    return w


# ═══════════════════════════════════════════════
#  3. Histogram (히스토그램 + 정규분포 곡선)
# ═══════════════════════════════════════════════

def create_histogram_widget(data: list, metric_key: str = 'value',
                             bins: int = 50,
                             title: str = 'Distribution') -> pg.PlotWidget:
    """측정값 히스토그램 + 정규분포 곡선 — pyqtgraph 인터랙티브 버전.

    Features:
      - BarGraphItem 기반 히스토그램
      - 정규분포 곡선 오버레이
      - Mean, ±1σ/±2σ/±3σ 수직선
      - CrossHair 마우스 추적
    """
    w = CrossHairPlotWidget()
    plot = w.plotItem
    _style_axis(plot, title=title, x_label=metric_key, y_label='Density')

    values = np.array([r.get(metric_key, 0) for r in data
                       if isinstance(r.get(metric_key), (int, float))], dtype=float)

    if len(values) == 0:
        return w

    # 히스토그램 계산
    hist, bin_edges = np.histogram(values, bins=bins, density=True)
    bin_width = bin_edges[1] - bin_edges[0]
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # BarGraphItem
    bar = pg.BarGraphItem(x=bin_centers, height=hist, width=bin_width * 0.9,
                           brush=pg.mkBrush(ACCENT + '99'),
                           pen=pg.mkPen(ACCENT, width=0.5))
    w.addItem(bar)

    # 통계
    mean = float(np.mean(values))
    std = float(np.std(values))

    # 정규분포 곡선
    if std > 0:
        x_curve = np.linspace(values.min(), values.max(), 300)
        y_curve = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_curve - mean) / std) ** 2)
        w.plot(x_curve, y_curve, pen=_make_pen(RED, 2),
               name=f'Normal (μ={mean:.1f}, σ={std:.1f})')

    # Mean 수직선
    w.addItem(pg.InfiniteLine(pos=mean, angle=90,
                               pen=_make_pen(RED, 2, 'dash'),
                               label=f'μ={mean:.1f}',
                               labelOpts={'color': RED, 'position': 0.95}))

    # ±1σ, ±2σ, ±3σ 수직선
    sigma_colors = [(ORANGE, '±1σ'), (PURPLE, '±2σ'), ('#585b70', '±3σ')]
    for i, (color, lbl) in enumerate(sigma_colors, 1):
        for sign in [-1, 1]:
            pos = mean + sign * i * std
            w.addItem(pg.InfiniteLine(
                pos=pos, angle=90,
                pen=_make_pen(color, 1, 'dot'),
                label=f'{lbl}' if sign > 0 else None,
                labelOpts={'color': color, 'position': 0.9} if sign > 0 else {}
            ))

    # Legend
    plot.addLegend(offset=(10, 10), labelTextColor=FG2,
                    brush=pg.mkBrush(BG3 + 'CC'))

    # 통계 정보 텍스트
    stats_text = pg.TextItem(
        f"N={len(values)}  μ={mean:.2f}  σ={std:.2f}\n"
        f"Min={values.min():.2f}  Max={values.max():.2f}",
        anchor=(1, 0), color=FG2, fill=pg.mkBrush(BG3 + 'CC'))
    stats_text.setFont(QFont('Consolas', 9))
    stats_text.setPos(values.max(), hist.max())
    w.addItem(stats_text)

    plot.enableAutoRange()
    return w


# ═══════════════════════════════════════════════
#  4. TIFF Profile (ImageView + Line Profile)
# ═══════════════════════════════════════════════

class TiffViewerWidget(QWidget):
    """TIFF 데이터를 2D Image + Line Profile로 표시하는 통합 위젯.

    Features:
      - pg.ImageView: 실시간 줌/패닝, 컬러맵 조정, ROI
      - pg.PlotWidget: 선택된 행의 프로파일 라인
      - ROI 드래그 → 프로파일 자동 업데이트
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._info_label = QLabel("TIFF 데이터 없음")
        self._info_label.setStyleSheet(f"color: {FG2}; font-size: 9pt; padding: 4px;")
        layout.addWidget(self._info_label)

        splitter = QSplitter(Qt.Vertical)
        layout.addWidget(splitter)

        # 2D Image View
        self._image_view = pg.ImageView()
        self._image_view.ui.roiBtn.hide()   # ROI 버튼 숨김 (커스텀 ROI 사용)
        self._image_view.ui.menuBtn.hide()  # 메뉴 버튼 숨김
        # 다크테마 적용
        self._image_view.getView().setBackgroundColor(BG2)
        splitter.addWidget(self._image_view)

        # Line Profile Plot
        self._profile_plot = pg.PlotWidget()
        _style_axis(self._profile_plot.plotItem,
                     title='Line Profile', x_label='Position', y_label='Z')
        splitter.addWidget(self._profile_plot)

        splitter.setSizes([400, 200])

        self._data_2d = None
        self._roi = None

    def set_data(self, data_2d: np.ndarray, info: dict = None, title: str = None):
        """TIFF 2D 데이터를 설정하고 표시."""
        self._data_2d = data_2d
        h, w = data_2d.shape if data_2d.ndim == 2 else (1, len(data_2d))

        # 메타 정보
        z_unit = info.get('z_unit', '') if info else ''
        channel = info.get('channel_name', '') if info else ''
        mode = info.get('head_mode', '') if info else ''
        if title is None:
            title = f'{channel} [{mode}]' if channel else 'TIFF Data'
        self._info_label.setText(
            f"📐 {title}  |  {w}×{h} px  |  Z unit: {z_unit}")

        if h == 1 or w == 1:
            # 1D Profile
            self._image_view.hide()
            profile = data_2d.flatten()
            scan_size = None
            if info:
                scan_size = info.get('scan_size_width', 0) if w > 1 else info.get('scan_size_height', 0)

            if scan_size and scan_size > 0:
                x_axis = np.linspace(0, scan_size, len(profile))
                self._profile_plot.plotItem.setLabel('bottom', 'Position (μm)')
            else:
                x_axis = np.arange(len(profile))
                self._profile_plot.plotItem.setLabel('bottom', 'Pixel')

            self._profile_plot.clear()
            self._profile_plot.plot(x_axis, profile,
                                     pen=_make_pen(ACCENT, 1))
            self._profile_plot.plotItem.setTitle(f'{title} — Profile')
        else:
            # 2D Image + Profile
            self._image_view.show()
            self._image_view.setImage(data_2d.T, autoRange=True, autoLevels=True)

            # ROI 라인 (가운데 행)
            mid_row = h // 2
            if self._roi is not None:
                self._image_view.getView().removeItem(self._roi)

            self._roi = pg.LineSegmentROI(
                [[0, mid_row], [w - 1, mid_row]],
                pen=pg.mkPen(ACCENT, width=2))
            self._image_view.getView().addItem(self._roi)
            self._roi.sigRegionChanged.connect(self._update_profile_from_roi)

            # 초기 프로파일
            self._profile_plot.clear()
            self._profile_plot.plot(data_2d[mid_row, :],
                                     pen=_make_pen(ACCENT, 1))
            self._profile_plot.plotItem.setTitle(
                f'H-Profile (row={mid_row})')
            self._profile_plot.plotItem.setLabel('bottom', 'X (px)')
            self._profile_plot.plotItem.setLabel('left', f'Z ({z_unit})')

    def _update_profile_from_roi(self):
        """ROI 드래그 시 프로파일 업데이트."""
        if self._data_2d is None or self._roi is None:
            return
        try:
            # ROI에서 프로파일 데이터 추출
            data = self._roi.getArrayRegion(
                self._data_2d.T, self._image_view.getImageItem())
            if data is not None and len(data) > 0:
                self._profile_plot.clear()
                self._profile_plot.plot(data, pen=_make_pen(ACCENT, 1))
        except Exception:
            pass

    def clear(self):
        """위젯 초기화."""
        self._image_view.clear()
        self._profile_plot.clear()
        self._data_2d = None
        self._info_label.setText("TIFF 데이터 없음")


from PySide6.QtWidgets import QTabWidget


class MultiTiffViewerWidget(QWidget):
    """복수 TIFF를 서브탭으로 표시하는 통합 위젯.

    각 TIFF 파일별 독립된 TiffViewerWidget 서브탭을 생성하여
    X/Y 결과를 번갈아 비교할 수 있습니다.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header = QLabel("🔬 TIFF — 더블클릭으로 로드")
        self._header.setStyleSheet(
            f"color: {FG2}; font-size: 9pt; padding: 4px; background: {BG3};")
        layout.addWidget(self._header)

        self._tab_widget = QTabWidget()
        self._tab_widget.setStyleSheet(f"""
            QTabBar::tab {{
                background: {BG3}; color: {FG2}; padding: 6px 14px;
                border-top-left-radius: 4px; border-top-right-radius: 4px;
                font-size: 9pt; margin-right: 2px;
            }}
            QTabBar::tab:selected {{ background: #45475a; color: {ACCENT}; font-weight: bold; }}
        """)
        layout.addWidget(self._tab_widget)

        self._viewers = []

    def set_results(self, tiff_results: list):
        """복수 TIFF 결과를 서브탭으로 표시.

        Args:
            tiff_results: [{'filename': ..., 'data_2d': ndarray, 'info': dict}, ...]
        """
        self.clear()

        n = len(tiff_results)
        self._header.setText(f"🔬 TIFF — {n}개 파일 로드됨 (탭으로 전환)")

        for i, tr in enumerate(tiff_results):
            data2d = tr.get('data_2d')
            if data2d is None:
                continue

            viewer = TiffViewerWidget()
            info = tr.get('info', {})
            filename = tr.get('filename', f'TIFF {i+1}')
            channel = info.get('channel_name', '')
            mode = info.get('head_mode', '')
            title = f"{filename}\n{channel} [{mode}]"

            viewer.set_data(data2d, info, title)

            # 탭 이름: 순번 + 파일명 (간결하게)
            tab_name = f"[{i+1}] {filename}"
            if len(tab_name) > 35:
                tab_name = f"[{i+1}] ...{filename[-28:]}"

            self._tab_widget.addTab(viewer, tab_name)
            self._viewers.append(viewer)

    def clear(self):
        """모든 서브탭 제거."""
        while self._tab_widget.count() > 0:
            w = self._tab_widget.widget(0)
            self._tab_widget.removeTab(0)
            w.deleteLater()
        self._viewers.clear()
        self._header.setText("🔬 TIFF — 더블클릭으로 로드")


def create_tiff_widget() -> MultiTiffViewerWidget:
    """빈 Multi-TIFF Viewer 위젯 생성."""
    return MultiTiffViewerWidget()


# ═══════════════════════════════════════════════
#  5. Pareto Chart (Die별 이상치 막대 + 누적%)
# ═══════════════════════════════════════════════

def create_pareto_widget(pareto_data: list,
                         title: str = 'Pareto') -> pg.PlotWidget:
    """Die/Lot별 이상치 빈도 파레토 차트.

    Features:
      - 내림차순 막대 그래프 (좌축: 이상치 개수)
      - 누적 % 곡선 (우축: 0~100%)
      - 80% 기준선 (빨간 점선)
      - 호버 시 라벨 표시

    Args:
        pareto_data: compute_pareto_data() 결과
            [{'label': 'Die5', 'count': 12, 'percent': 30.0, 'cumulative': 30.0}, ...]
    """
    widget = CrossHairPlotWidget()
    plot = widget.getPlotItem()
    _style_axis(plot, title=title, x_label='', y_label='이상치 수')

    if not pareto_data:
        # 이상치 없는 경우 안내 텍스트 표시
        text = pg.TextItem("이상치가 없습니다 (Outlier = 0)", color=FG2,
                           anchor=(0.5, 0.5))
        text.setFont(pg.QtGui.QFont('', 12))
        plot.addItem(text)
        text.setPos(0.5, 0.5)
        plot.setXRange(0, 1)
        plot.setYRange(0, 1)
        return widget

    n = len(pareto_data)
    labels = [d['label'] for d in pareto_data]
    counts = [d['count'] for d in pareto_data]
    cum_pcts = [d['cumulative'] for d in pareto_data]

    # ─── 막대 그래프 (좌축) ───
    x_pos = list(range(n))
    bar_colors = [pg.mkColor(c) for c in _DIE_COLORS[:n]]

    # 그라데이션 색상 적용
    brushes = []
    for i, c in enumerate(bar_colors):
        c.setAlpha(200)
        brushes.append(c)

    bar = pg.BarGraphItem(x=x_pos, height=counts, width=0.6,
                          brushes=brushes,
                          pen=pg.mkPen('#45475a', width=1))
    plot.addItem(bar)

    # X축 라벨 설정
    x_axis = plot.getAxis('bottom')
    x_axis.setTicks([[(i, labels[i]) for i in range(n)]])

    # 좌축 범위
    max_count = max(counts) if counts else 1
    plot.setYRange(0, max_count * 1.15)
    plot.setXRange(-0.5, n - 0.5)

    # ─── 누적 % 곡선 (우축) ───
    # ViewBox 오버레이로 우축 추가
    right_vb = pg.ViewBox()
    plot.scene().addItem(right_vb)
    plot.getAxis('right').linkToView(right_vb)
    right_vb.setXLink(plot)
    plot.getAxis('right').setLabel('누적 %', color=ORANGE)
    plot.getAxis('right').setStyle(showValues=True)
    plot.showAxis('right')

    # ViewBox 크기 동기화
    def update_views():
        right_vb.setGeometry(plot.vb.sceneBoundingRect())
        right_vb.linkedViewChanged(plot.vb, right_vb.XAxis)

    plot.vb.sigResized.connect(update_views)

    # 누적% 곡선
    cum_curve = pg.PlotCurveItem(
        x=x_pos, y=cum_pcts,
        pen=_make_pen(ORANGE, width=3),
        name='누적 %')
    right_vb.addItem(cum_curve)

    # 누적% 포인트
    cum_scatter = pg.ScatterPlotItem(
        x=x_pos, y=cum_pcts, size=8,
        pen=pg.mkPen(ORANGE, width=1),
        brush=pg.mkBrush(ORANGE))
    right_vb.addItem(cum_scatter)

    # 80% 기준선
    threshold_line = pg.InfiniteLine(
        pos=80.0, angle=0,
        pen=pg.mkPen(RED, width=2, style=pg.QtCore.Qt.DashLine),
        label='80%', labelOpts={'color': RED, 'position': 0.05})
    right_vb.addItem(threshold_line)

    right_vb.setYRange(0, 105)

    # ─── CrossHair 데이터 설정 ───
    snap_points = []
    for i, d in enumerate(pareto_data):
        label = f"{d['label']}: {d['count']}건 ({d['percent']}%)\n누적: {d['cumulative']}%"
        snap_points.append((i, counts[i], label))
    widget.set_data_points(snap_points)

    update_views()
    return widget


# ═══════════════════════════════════════════════
#  6. Correlation Chart (X/Y Die avg 상관)
# ═══════════════════════════════════════════════

def create_correlation_widget(corr_data: dict,
                              title: str = 'X-Y Correlation') -> pg.PlotWidget:
    """X/Y Die별 평균 편차 상관관계 산점도.

    Features:
      - Die별 색상 산점도
      - 선형 회귀선 + R² 표시
      - Zero 십자선 (원점 기준)
      - 호버 시 Die 정보

    Args:
        corr_data: compute_correlation() 결과
            {'pearson_r', 'r_squared', 'slope', 'intercept', 'points', 'n'}
    """
    widget = CrossHairPlotWidget()
    plot = widget.getPlotItem()
    _style_axis(plot, title=title, x_label='X Deviation (µm)', y_label='Y Deviation (µm)')

    points = corr_data.get('points', [])
    if not points:
        text = pg.TextItem("상관관계 데이터 없음", color=FG2,
                           anchor=(0.5, 0.5))
        text.setFont(pg.QtGui.QFont('', 12))
        plot.addItem(text)
        text.setPos(0.5, 0.5)
        return widget

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    die_labels = [p[2] for p in points]

    # Zero 십자선
    plot.addItem(pg.InfiniteLine(pos=0, angle=0,
                 pen=pg.mkPen('#45475a', width=1, style=pg.QtCore.Qt.DashLine)))
    plot.addItem(pg.InfiniteLine(pos=0, angle=90,
                 pen=pg.mkPen('#45475a', width=1, style=pg.QtCore.Qt.DashLine)))

    # Die별 색상 산점도
    n = len(points)
    spots = []
    for i, (x, y, die) in enumerate(points):
        color_idx = i % len(_DIE_COLORS)
        spots.append({
            'pos': (x, y),
            'size': 12,
            'pen': pg.mkPen(_DIE_COLORS[color_idx], width=1),
            'brush': pg.mkBrush(_DIE_COLORS[color_idx]),
            'data': die,
        })

    scatter = pg.ScatterPlotItem(spots=spots)
    plot.addItem(scatter)

    # 회귀선
    slope = corr_data.get('slope', 0)
    intercept = corr_data.get('intercept', 0)
    r_sq = corr_data.get('r_squared', 0)
    pearson_r = corr_data.get('pearson_r', 0)

    if xs:
        x_min, x_max = min(xs), max(xs)
        margin = (x_max - x_min) * 0.1 or 0.5
        rx = [x_min - margin, x_max + margin]
        ry = [slope * x + intercept for x in rx]

        plot.plot(rx, ry, pen=_make_pen(ACCENT, width=2, style=pg.QtCore.Qt.DashLine))

    # R² 텍스트 표시
    info_text = pg.TextItem(
        f"R² = {r_sq:.4f}\nr = {pearson_r:.4f}\ny = {slope:.3f}x + {intercept:.3f}",
        color=ACCENT, anchor=(0, 0))
    info_text.setFont(pg.QtGui.QFont('', 10))
    plot.addItem(info_text)

    # 텍스트 위치: 좌상단
    if xs and ys:
        info_text.setPos(min(xs), max(ys))

    # CrossHair 데이터
    snap_points = []
    for i, (x, y, die) in enumerate(points):
        label = f"Die {die}\nX: {x:.3f} µm\nY: {y:.3f} µm"
        snap_points.append((x, y, label))
    widget.set_data_points(snap_points)

    return widget


# ═══════════════════════════════════════════════
#  7. 3D Wafer Surface (pyqtgraph.opengl)
# ═══════════════════════════════════════════════

def create_3d_surface_widget(die_stats: list,
                              title: str = '3D Surface') -> QWidget:
    """Die별 평균 편차를 3D 표면 맵으로 시각화.

    Features:
      - scipy griddata 보간 → GLSurfacePlotItem
      - Die 위치 ScatterPlot 마커
      - 마우스 회전/줌/패닝
      - 컬러맵: RdYlGn_r 스타일

    Args:
        die_stats: [{'die': 1, 'avg': 0.5, ...}, ...]
    """
    from PySide6.QtWidgets import QVBoxLayout, QLabel

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    # 제목
    title_label = QLabel(f"  🌐 {title}")
    title_label.setStyleSheet(f"color: {FG}; font-size: 10pt; font-weight: bold; "
                               f"background: {BG2}; padding: 4px;")
    layout.addWidget(title_label)

    if not die_stats:
        info = QLabel("Die 데이터 없음")
        info.setStyleSheet(f"color: {FG2}; font-size: 11pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    try:
        import pyqtgraph.opengl as gl
        from scipy.interpolate import griddata
    except ImportError as e:
        info = QLabel(f"3D 표시 불가: {e}\npip install PyOpenGL scipy")
        info.setStyleSheet(f"color: {RED}; font-size: 10pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    # Die 위치 매핑
    from analyzer import DIE_POSITIONS, get_die_position

    xs, ys, zs = [], [], []
    for ds in die_stats:
        pos = get_die_position(ds['die'])
        if pos:
            xs.append(pos[0])
            ys.append(pos[1])
            zs.append(ds['avg'])

    if len(xs) < 4:
        info = QLabel("3D 보간에 최소 4개 Die 필요")
        info.setStyleSheet(f"color: {FG2}; font-size: 11pt; padding: 40px;")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info, 1)
        return container

    # 보간 그리드
    import numpy as np

    xi = np.linspace(min(xs) - 1, max(xs) + 1, 50)
    yi = np.linspace(min(ys) - 1, max(ys) + 1, 50)
    Xi, Yi = np.meshgrid(xi, yi)
    Zi = griddata((xs, ys), zs, (Xi, Yi), method='cubic')

    # NaN → 0 (보간 범위 밖)
    Zi = np.nan_to_num(Zi, nan=0.0)

    # 색상 맵 생성 (RdYlGn_r 스타일)
    z_min, z_max = np.nanmin(zs), np.nanmax(zs)
    z_range = z_max - z_min if z_max != z_min else 1.0

    # normalize Zi for colormap
    Zi_norm = (Zi - z_min) / z_range
    Zi_norm = np.clip(Zi_norm, 0, 1)

    # RGBA 색상 배열
    colors = np.zeros((*Zi.shape, 4), dtype=np.float32)
    # 파란색(낮은 값) → 초록 → 빨강(높은 값)
    colors[..., 0] = Zi_norm  # R
    colors[..., 1] = 1.0 - np.abs(Zi_norm - 0.5) * 2  # G (중간에서 최대)
    colors[..., 2] = 1.0 - Zi_norm  # B
    colors[..., 3] = 0.85  # Alpha

    # GLViewWidget 생성
    view = gl.GLViewWidget()
    view.setBackgroundColor(BG)
    view.setCameraPosition(distance=20, elevation=30, azimuth=45)

    # Surface
    surface = gl.GLSurfacePlotItem(
        x=xi, y=yi, z=Zi,
        colors=colors,
        shader='shaded',
        smooth=True)
    view.addItem(surface)

    # 그리드
    grid = gl.GLGridItem()
    grid.setSize(max(xs) - min(xs) + 4, max(ys) - min(ys) + 4, 0)
    grid.setSpacing(1, 1, 1)
    grid.translate(np.mean(xs), np.mean(ys), z_min - 0.5)
    view.addItem(grid)

    # Die 마커 (scatter)
    die_points = np.array([[x, y, z + 0.1] for x, y, z in zip(xs, ys, zs)])
    scatter = gl.GLScatterPlotItem(
        pos=die_points,
        size=8,
        color=(1, 1, 1, 1),
        pxMode=True)
    view.addItem(scatter)

    layout.addWidget(view, 1)
    return container

