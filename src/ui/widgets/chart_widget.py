"""
chart_widget.py — Matplotlib/pyqtgraph 차트 컨테이너 위젯
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT


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
