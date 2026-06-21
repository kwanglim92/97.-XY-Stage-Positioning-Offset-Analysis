"""
chart_widget.py — Matplotlib/pyqtgraph 차트 컨테이너 위젯
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from PySide6.QtCore import QTimer
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT


def sync_canvas_dpi(canvas, fig=None):
    """Matplotlib FigureCanvasQTAgg의 Figure DPI를 화면의 논리 DPI에 맞춘다.

    Cross-display optimization (pattern d): point 단위 폰트가 모든 디스플레이에서
    일관된 물리적 크기로 렌더링되도록 한다. Figure를 교체할 때는 새 fig를 넘기고,
    생략하면 캔버스의 현재 figure를 사용한다. 캔버스가 아직 크기를 갖지 않은 시점
    (w/h == 0)에 호출해도 안전하다(크기 조정은 건너뛴다).
    """
    if canvas is None:
        return
    fig = fig if fig is not None else canvas.figure
    if fig is None:
        return
    target_dpi = canvas.logicalDpiX() or fig.get_dpi()
    fig.set_dpi(target_dpi)
    if fig is not canvas.figure:
        fig.set_canvas(canvas)
        canvas.figure = fig
    w, h = canvas.width(), canvas.height()
    if w > 0 and h > 0:
        fig.set_size_inches(w / target_dpi, h / target_dpi)
    canvas.draw_idle()


class ChartWidget(QWidget):
    """Matplotlib Figure를 인터랙티브 차트로 표시 (줌/패닝/저장)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._canvas = None
        self._toolbar = None
        # 리사이즈가 멈춘 뒤(150ms) 차트를 화면 DPI에 맞춰 재배치/재렌더 — pattern d
        self._resize_debounce = QTimer(self)
        self._resize_debounce.setSingleShot(True)
        self._resize_debounce.setInterval(150)
        self._resize_debounce.timeout.connect(self._relayout_canvas)

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
        sync_canvas_dpi(self._canvas)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._resize_debounce.start()

    def _relayout_canvas(self):
        if not self._canvas:
            return
        try:
            self._canvas.figure.tight_layout()
        except Exception:
            # add_axes 기반 figure 등 tight_layout 미지원 시 방어 (pattern d)
            pass
        sync_canvas_dpi(self._canvas)

    def clear(self):
        if self._canvas:
            self._layout.removeWidget(self._toolbar)
            self._layout.removeWidget(self._canvas)
            self._toolbar.deleteLater()
            self._canvas.deleteLater()
            self._canvas = None
            self._toolbar = None


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
