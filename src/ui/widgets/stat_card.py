"""
stat_card.py — X/Y 축 통계 요약 카드
"""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from ui.theme import BG2, FG, FG2, BG, GREEN, RED


class StatCard(QFrame):
    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self.setObjectName("statcard")
        self.setStyleSheet(f"""
            #statcard {{ background: {BG2}; border: 1px solid #585b70;
                         border-radius: 6px; padding: 8px; }}
            #statcard QLabel {{ background: transparent; }}
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet(f"font-size: 11pt; font-weight: bold; color: {FG2};")
        layout.addWidget(lbl_title)

        self.lbl_avg = self._row(layout, "Avg (nm):")
        self.lbl_rng, self.lbl_rng_spec = self._row_with_spec(layout, "Dev Range (µm):")
        self.lbl_std, self.lbl_std_spec = self._row_with_spec(layout, "Dev StdDev (µm):")
        self.lbl_cpk = self._row(layout, "Cpk:")

        self.badge = QLabel("—")
        self.badge.setAlignment(Qt.AlignCenter)
        self.badge.setStyleSheet(
            f"background: gray; color: {BG}; font-weight: bold; "
            f"padding: 4px; border-radius: 4px; font-size: 10pt;"
        )
        layout.addWidget(self.badge)

    def _row(self, layout, label_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        val = QLabel("—")
        val.setAlignment(Qt.AlignRight)
        val.setStyleSheet(f"color: {FG}; font-weight: bold; font-size: 12pt;")
        row.addWidget(lbl)
        row.addWidget(val)
        layout.addLayout(row)
        return val

    def _row_with_spec(self, layout, label_text):
        row = QHBoxLayout()
        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"color: {FG2}; font-size: 9pt;")
        val = QLabel("—")
        val.setAlignment(Qt.AlignRight)
        val.setStyleSheet(f"color: {FG}; font-weight: bold; font-size: 12pt;")
        spec_lbl = QLabel("")
        spec_lbl.setAlignment(Qt.AlignRight)
        spec_lbl.setStyleSheet(f"font-size: 9pt; min-width: 90px;")
        row.addWidget(lbl)
        row.addStretch()
        row.addWidget(val)
        row.addWidget(spec_lbl)
        layout.addLayout(row)
        return val, spec_lbl

    def _format_spec_delta(self, value, spec):
        """Spec 대비 표기 생성: 초과=빨강▲, 여유=초록✓"""
        if spec is None or spec == 0:
            return "", ""
        ratio = value / spec * 100
        if value > spec:
            pct = ratio - 100
            text = f"/ {spec}  ▲+{pct:.0f}%"
            color = RED
        else:
            pct = 100 - ratio
            text = f"/ {spec}  ✓{pct:.0f}%"
            color = GREEN
        return text, color

    def update_stats(self, avg, rng, std, cpk, is_pass: bool = None,
                     spec_r=None, spec_s=None):
        self.lbl_avg.setText(f"{avg:.3f}")
        self.lbl_rng.setText(f"{rng:.3f}")
        self.lbl_std.setText(f"{std:.3f}")
        self.lbl_cpk.setText(f"{cpk:.2f}")

        # Spec 대비 표기
        rng_text, rng_color = self._format_spec_delta(rng, spec_r)
        self.lbl_rng_spec.setText(rng_text)
        self.lbl_rng_spec.setStyleSheet(
            f"font-size: 9pt; color: {rng_color}; min-width: 90px;")

        std_text, std_color = self._format_spec_delta(std, spec_s)
        self.lbl_std_spec.setText(std_text)
        self.lbl_std_spec.setStyleSheet(
            f"font-size: 9pt; color: {std_color}; min-width: 90px;")

        if is_pass is None:
            self.badge.setText("—")
            self.badge.setStyleSheet(
                f"background: gray; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )
        elif is_pass:
            self.badge.setText("✅ PASS")
            self.badge.setStyleSheet(
                f"background: {GREEN}; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )
        else:
            self.badge.setText("❌ FAIL")
            self.badge.setStyleSheet(
                f"background: {RED}; color: {BG}; font-weight: bold; "
                f"padding: 4px; border-radius: 4px; font-size: 10pt;"
            )
