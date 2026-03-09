import pyqtgraph as pg
import pyqtgraph.opengl as gl
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSplitter
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



class HoverScatterWidget(pg.PlotWidget):
    """마우스 호버 시 가장 가까운 점의 정보를 표시하는 ScatterPlot.
    
    Die 점 클릭 시 해당 Die만 강조 (나머지 투명화).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scatter_items = []  # (ScatterPlotItem, die_label, x, y) 리스트
        self._die_colors = {}  # {die_label: original_color_hex}
        self._highlighted_dies = set()  # 강조된 Die 세트 (비어있으면 전체 표시)
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
        self._die_colors[die_label] = color

    def highlight_die(self, die_label):
        """외부에서 호출 — Die 토글 (복수 선택 가능)."""
        if die_label in self._highlighted_dies:
            self._highlighted_dies.discard(die_label)
        else:
            self._highlighted_dies.add(die_label)

        if not self._highlighted_dies:
            self._restore_all()
        else:
            self._apply_highlight()

    def _apply_highlight(self):
        """_highlighted_dies에 속한 Die만 강조, 나머지 투명화."""
        for scatter, die_label, _, _ in self._scatter_items:
            if die_label in self._highlighted_dies:
                color = self._die_colors[die_label]
                scatter.setBrush(pg.mkBrush(color + 'CC'))
                scatter.setSize(10)
                scatter.setZValue(10)
            else:
                scatter.setBrush(pg.mkBrush('#555555' + '14'))
                scatter.setSize(6)
                scatter.setZValue(1)

    def _restore_all(self):
        """모든 Die를 원래 상태로 복원."""
        self._highlighted_dies.clear()
        for scatter, die_label, _, _ in self._scatter_items:
            color = self._die_colors[die_label]
            scatter.setBrush(pg.mkBrush(color + 'CC'))
            scatter.setSize(8)
            scatter.setZValue(5)

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
            # 투명화된 Die는 호버 대상 제외
            if self._highlighted_dies and die_label not in self._highlighted_dies:
                continue
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

        self._header = QLabel("TIFF — Double-click row to load")
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
        self._header.setText(f"TIFF — {n} File(s) loaded (Switch tabs)")

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
        self._header.setText("TIFF — Double-click row to load")



def create_tiff_widget() -> MultiTiffViewerWidget:
    """빈 Multi-TIFF Viewer 위젯 생성."""
    return MultiTiffViewerWidget()


# ═══════════════════════════════════════════════
#  5. Pareto Chart (Die별 이상치 막대 + 누적%)
# ═══════════════════════════════════════════════


