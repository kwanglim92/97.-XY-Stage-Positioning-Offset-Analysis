"""
flow_layout.py — 가로 줄바꿈 레이아웃 (Die 체크박스용)
"""

from PySide6.QtWidgets import QLayout
from PySide6.QtCore import Qt, QRect, QSize


class FlowLayout(QLayout):
    """가로로 배치하다 넘치면 다음 줄로 넘기는 레이아웃."""

    def __init__(self, parent=None, margin=0, spacing=-1):
        super().__init__(parent)
        self.setContentsMargins(margin, margin, margin, margin)
        if spacing >= 0:
            self._spacing = spacing
        else:
            self._spacing = 4
        self._items = []

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, index):
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index):
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self):
        return Qt.Orientations()

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, width):
        return self._do_layout(QRect(0, 0, width, 0), test_only=True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        m = self.contentsMargins()
        size += QSize(m.left() + m.right(), m.top() + m.bottom())
        return size

    def _do_layout(self, rect, test_only=False):
        m = self.contentsMargins()
        effective = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y = effective.x(), effective.y()
        line_height = 0
        for item in self._items:
            w = item.widget()
            if w is None:
                continue
            space = self._spacing
            next_x = x + w.sizeHint().width() + space
            if next_x - space > effective.right() and line_height > 0:
                x = effective.x()
                y += line_height + space
                next_x = x + w.sizeHint().width() + space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, w.sizeHint().width(), w.sizeHint().height()))
            x = next_x
            line_height = max(line_height, w.sizeHint().height())
        return y + line_height - rect.y() + m.bottom()
