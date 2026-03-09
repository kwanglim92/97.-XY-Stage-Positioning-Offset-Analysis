import os
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox
from ui.theme import BG, FG, ACCENT, FG2

class SpecConfigDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings or {}
        self.setWindowTitle("⚙️ Spec Configuration")
        self.setMinimumSize(600, 480)
        self.setStyleSheet(f"background: {BG}; color: {FG};")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # spec_deviation 테이블
        lbl_dev = QLabel("Deviation Spec")
        lbl_dev.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {ACCENT};")
        layout.addWidget(lbl_dev)

        dev_spec = self.settings.get('spec_deviation', {})
        t_dev = QTableWidget(len(dev_spec), 3)
        t_dev.setHorizontalHeaderLabels(['Recipe', 'Range (µm)', 'StdDev (µm)'])
        t_dev.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_dev.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (name, ds) in enumerate(dev_spec.items()):
            t_dev.setItem(row, 0, QTableWidgetItem(name))
            t_dev.setItem(row, 1, QTableWidgetItem(str(ds.get('spec_range', '—'))))
            t_dev.setItem(row, 2, QTableWidgetItem(str(ds.get('spec_stddev', '—'))))
        t_dev.resizeRowsToContents()
        layout.addWidget(t_dev)

        # spec_limits 테이블
        lbl_lim = QLabel("Offset Limits (Cpk)")
        lbl_lim.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {ACCENT}; margin-top: 8px;")
        layout.addWidget(lbl_lim)

        spec_lim = self.settings.get('spec_limits', {})
        t_lim = QTableWidget(len(spec_lim), 5)
        t_lim.setHorizontalHeaderLabels(['Recipe', 'X LSL (nm)', 'X USL (nm)', 'Y LSL (nm)', 'Y USL (nm)'])
        t_lim.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t_lim.setEditTriggers(QTableWidget.NoEditTriggers)
        for row, (name, sp) in enumerate(spec_lim.items()):
            t_lim.setItem(row, 0, QTableWidgetItem(name))
            x = sp.get('X', {})
            y = sp.get('Y', {})
            t_lim.setItem(row, 1, QTableWidgetItem(str(x.get('lsl', '—'))))
            t_lim.setItem(row, 2, QTableWidgetItem(str(x.get('usl', '—'))))
            t_lim.setItem(row, 3, QTableWidgetItem(str(y.get('lsl', '—'))))
            t_lim.setItem(row, 4, QTableWidgetItem(str(y.get('usl', '—'))))
        t_lim.resizeRowsToContents()
        layout.addWidget(t_lim)

        # 파일 경로 안내
        import __main__
        if hasattr(__main__, '__file__'):
            path = os.path.join(os.path.dirname(os.path.abspath(__main__.__file__)), 'settings.json')
        else:
            path = "settings.json (경로 불명확)"
            
        lbl_path = QLabel(f"📁 {path}")
        lbl_path.setStyleSheet(f"color: {FG2}; font-size: 8pt; margin-top: 8px;")
        lbl_path.setWordWrap(True)
        layout.addWidget(lbl_path)

        btn = QDialogButtonBox(QDialogButtonBox.Ok)
        btn.accepted.connect(self.accept)
        layout.addWidget(btn)
