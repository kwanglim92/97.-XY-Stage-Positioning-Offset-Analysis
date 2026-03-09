import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QFont
import numpy as np

# Theme colors
BG      = '#1e1e2e'
BG2     = '#313244'
BG3     = '#181825'
FG      = '#cdd6f4'
FG2     = '#a6adc8'
ACCENT  = '#89b4fa'
GREEN   = '#a6e3a1'
RED     = '#f38ba8'
ORANGE  = '#fab387'
PURPLE  = '#cba6f7'

pg.setConfigOptions(background=BG, foreground=FG, antialias=True)
from core import compute_trend, filter_valid_only
from charts.interactive_widgets import CrossHairPlotWidget, HoverScatterWidget

_DIE_COLORS = None  # Will be populated by _gen_die_colors

def _gen_die_colors(total=21):
    """Die Position Map / Die 필터와 동일한 HSL 기반 색상 생성."""
    colors = []
    for i in range(total):
        hue = (i % total) * (360.0 / total)
        # HSL → RGB (S=0.6, L=0.5)
        c = (1 - abs(2 * 0.5 - 1)) * 0.6
        x = c * (1 - abs((hue / 60) % 2 - 1))
        m = 0.5 - c / 2
        if hue < 60:    r, g, b = c, x, 0
        elif hue < 120: r, g, b = x, c, 0
        elif hue < 180: r, g, b = 0, c, x
        elif hue < 240: r, g, b = 0, x, c
        elif hue < 300: r, g, b = x, 0, c
        else:            r, g, b = c, 0, x
        colors.append(f'#{int((r+m)*255):02x}{int((g+m)*255):02x}{int((b+m)*255):02x}')
    return colors

_DIE_COLORS = _gen_die_colors(21)



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



def create_dual_trend_widget(x_trend: list, y_trend: list,
                              spec: dict = None,
                              title: str = 'Lot Trend') -> QWidget:
    """X/Y Dual-Panel Lot Trend — Mean ± 1σ 밴드 (Min/Max 제거).

    Args:
        x_trend: compute_trend(x_filtered) 결과
        y_trend: compute_trend(y_filtered) 결과
        spec: {'spec_range': 4.0, 'spec_stddev': 0.8} — Spec 한계선용
        title: 차트 제목
    """
    from PySide6.QtWidgets import QVBoxLayout

    container = QWidget()
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)

    def _make_panel(trend_data, axis_label, color):
        """단일 축 트렌드 패널 생성."""
        w = CrossHairPlotWidget()
        plot = w.plotItem
        _style_axis(plot, title=f'{title} — {axis_label}',
                    x_label='Lot Index', y_label=f'{axis_label} Offset (nm)')

        if not trend_data:
            return w

        indices = np.array([t['lot_index'] for t in trend_data], dtype=float)
        means = np.array([t['mean'] for t in trend_data])
        stdevs = np.array([t['stdev'] for t in trend_data])
        labels = [t['lot_name'] for t in trend_data]

        # ±1σ 밴드
        upper = means + stdevs
        lower = means - stdevs
        fill_upper = pg.PlotCurveItem(indices, upper, pen=pg.mkPen(None))
        fill_lower = pg.PlotCurveItem(indices, lower, pen=pg.mkPen(None))
        fill = pg.FillBetweenItem(fill_upper, fill_lower,
                                   brush=pg.mkBrush(color + '25'))
        w.addItem(fill_upper)
        w.addItem(fill_lower)
        w.addItem(fill)

        # Mean line
        w.plot(indices, means, pen=_make_pen(color, 2),
               symbol='o', symbolBrush=color, symbolSize=7,
               name=f'{axis_label} Mean')

        # Overall Mean
        overall_mean = float(np.mean(means))
        w.addItem(pg.InfiniteLine(
            pos=overall_mean, angle=0,
            pen=_make_pen('#888888', 1, 'dash'),
            label=f'Overall: {overall_mean:.1f}',
            labelOpts={'color': FG2, 'position': 0.05}))

        # Spec 한계선
        if spec:
            spec_range = spec.get('spec_range')
            if spec_range:
                half = spec_range * 1000 / 2  # µm → nm
                for sign, lbl in [(1, f'+{spec_range/2:.1f}µm'),
                                   (-1, f'-{spec_range/2:.1f}µm')]:
                    pos = overall_mean + sign * half
                    w.addItem(pg.InfiniteLine(
                        pos=pos, angle=0,
                        pen=_make_pen(RED, 1.5, 'dash'),
                        label=lbl,
                        labelOpts={'color': RED, 'position': 0.95}))

        # Legend
        plot.addLegend(offset=(10, 10), labelTextColor=FG2,
                       brush=pg.mkBrush(BG3 + 'CC'))

        # X축 틱 라벨
        ticks = [(int(idx), lbl) for idx, lbl in zip(indices, labels)]
        plot.getAxis('bottom').setTicks([ticks])

        # CrossHair 데이터
        pts = [(float(idx), float(m), lbl)
               for idx, m, lbl in zip(indices, means, labels)]
        w.set_data_points(pts)

        plot.enableAutoRange()
        return w

    # X 패널 (상단) — 파란색
    layout.addWidget(_make_panel(x_trend, 'X', ACCENT), 1)
    # Y 패널 (하단) — 빨간색
    layout.addWidget(_make_panel(y_trend, 'Y', RED), 1)

    return container


# ═══════════════════════════════════════════════
#  2. XY Scatter (Die별 색상 + Hover 정보)
# ═══════════════════════════════════════════════


def create_scatter_widget(x_dev_result: dict, y_dev_result: dict,
                           title: str = 'XY Scatter',
                           log_mode: bool = False,
                           spec_range: float = None) -> HoverScatterWidget:
    """X/Y Deviation Die별 산점도 — pyqtgraph 인터랙티브 버전.

    Features:
      - Die별 고유 색상
      - 마우스 호버 → Die명, X/Y 값 표시
      - ±5µm 격자 + Zero 십자선
      - 범례 패널에서 Die 하이라이트 (복수 선택)
      - log_mode: Signed Log 변환 (sign × log₁₀(1 + |value|))
      - spec_range: Range spec 가이드 박스 (±range 사각형)
    """
    def _signed_log(v):
        """Signed Log 변환: 부호 유지 + log 스케일."""
        return np.sign(v) * np.log10(1 + np.abs(v))

    w = HoverScatterWidget()
    plot = w.plotItem

    x_suffix = ' (Signed Log)' if log_mode else ' (µm)'
    _style_axis(plot, title=title,
                x_label=f'X Offset{x_suffix}',
                y_label=f'Y Offset{x_suffix}')

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
            xa = np.array(xvals)
            ya = np.array(yvals)
            if log_mode:
                xa = _signed_log(xa)
                ya = _signed_log(ya)
            w.add_die_scatter(xa, ya, dl, color)

    # Spec Range 가이드 박스
    if spec_range is not None and spec_range > 0:
        sr = spec_range
        if log_mode:
            sr = float(np.sign(sr) * np.log10(1 + abs(sr)))
        from pyqtgraph import QtWidgets, QtCore, QtGui
        rect = QtWidgets.QGraphicsRectItem(-sr, -sr, sr * 2, sr * 2)
        rect.setPen(pg.mkPen('#ff6b6b', width=1.5, style=QtCore.Qt.DashLine))
        rect.setBrush(pg.mkBrush('#ff6b6b08'))  # 매우 미세한 fill
        rect.setZValue(2)  # 데이터(5~10) 뒤, 십자선(기본) 앞
        w.addItem(rect, ignoreBounds=True)

        # 라벨
        spec_label = pg.TextItem(
            f'Spec ±{spec_range}µm', color='#ff6b6b',
            anchor=(1, 1))
        spec_label.setFont(QFont('Consolas', 8))
        spec_label.setPos(sr, sr)
        spec_label.setZValue(2)
        w.addItem(spec_label, ignoreBounds=True)

    # Zero 십자선
    w.addItem(pg.InfiniteLine(pos=0, angle=0, pen=_make_pen('#45475a', 1, 'dash')))
    w.addItem(pg.InfiniteLine(pos=0, angle=90, pen=_make_pen('#45475a', 1, 'dash')))

    # 범위 설정
    if log_mode:
        plot.enableAutoRange()
    else:
        plot.setXRange(-5, 5)
        plot.setYRange(-5, 5)
    plot.setAspectLocked(True)

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


