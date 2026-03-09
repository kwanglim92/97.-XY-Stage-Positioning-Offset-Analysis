"""
copyable_table.py — Ctrl+C 복사 지원 읽기전용 QTableWidget
"""

from PySide6.QtWidgets import QTableWidget, QApplication, QAbstractItemView
from PySide6.QtGui import QKeySequence


class CopyableTable(QTableWidget):
    """QTableWidget with Ctrl+C → tab-separated clipboard copy (read-only viewer)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setAlternatingRowColors(False)
        self.horizontalHeader().setStretchLastSection(True)
        # Read-only: block all edit triggers while preserving selection
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self._copy_selection()
        else:
            super().keyPressEvent(event)

    def _copy_selection(self):
        sel = self.selectedRanges()
        if not sel:
            return
        r = sel[0]
        lines = []
        for row in range(r.topRow(), r.bottomRow() + 1):
            cells = []
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                item = self.item(row, col)
                cells.append(item.text() if item else '')
            lines.append('\t'.join(cells))
        QApplication.clipboard().setText('\n'.join(lines))
