"""
sparkline_delegate.py — Summary 테이블 Spec 게이지 바 렌더링

QPainter로 셀 내 Spec 대비 사용률 게이지를 그립니다.
- SpecGaugeDelegate: Range/spec 비율을 수평 바로 표시
  0~80% 초록, 80~100% 노랑, 100%+ 빨강
"""

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QFont

# Catppuccin 색상
ACCENT = QColor('#89b4fa')
GREEN = QColor('#a6e3a1')
YELLOW = QColor('#f9e2af')
RED = QColor('#f38ba8')
BG3 = QColor('#45475a')
BG4 = QColor('#313244')
FG = QColor('#cdd6f4')
FG2 = QColor('#a6adc8')


class SpecGaugeDelegate(QStyledItemDelegate):
    """Spec 대비 사용률 게이지 바.

    데이터는 Qt.UserRole에:
      {'range_pct': float, 'std_pct': float}  (퍼센트 비율, 100 = Spec 경계)
    """

    def paint(self, painter: QPainter, option, index):
        # 배경
        painter.fillRect(option.rect, QColor(BG4))

        raw = index.data(Qt.UserRole)
        if not raw or not isinstance(raw, dict):
            painter.setPen(QPen(FG2))
            painter.drawText(option.rect, Qt.AlignCenter, '—')
            return

        range_pct = raw.get('range_pct', 0)
        std_pct = raw.get('std_pct', 0)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(4, 3, -4, -3)
        w = rect.width()
        h = rect.height()

        if w <= 0 or h <= 0:
            painter.restore()
            return

        bar_h = max(h * 0.32, 4)
        gap = max(2, (h - bar_h * 2) / 3)

        # 두 개의 바: Range, StdDev
        bars = [
            ('R', range_pct),
            ('σ', std_pct),
        ]

        for idx, (label, pct) in enumerate(bars):
            y_top = rect.y() + gap + idx * (bar_h + gap)

            # 배경 트랙
            track = QRectF(rect.x() + 12, y_top, w - 12, bar_h)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(BG3))
            painter.drawRoundedRect(track, 2, 2)

            # 게이지 바 (최대 150%까지 표시, 그 이상은 클램프)
            fill_ratio = min(pct / 100.0, 1.5)
            fill_w = max(track.width() * fill_ratio / 1.5, 1)

            # 색상: 0~80% 초록, 80~100% 노랑, 100%+ 빨강
            if pct <= 80:
                bar_color = GREEN
            elif pct <= 100:
                bar_color = YELLOW
            else:
                bar_color = RED

            bar_rect = QRectF(track.x(), y_top, fill_w, bar_h)
            painter.setBrush(bar_color)
            painter.drawRoundedRect(bar_rect, 2, 2)

            # 라벨 (R, σ)
            painter.setPen(QPen(FG2))
            painter.setFont(QFont("Segoe UI", 6))
            painter.drawText(
                QRectF(rect.x(), y_top, 11, bar_h),
                Qt.AlignVCenter | Qt.AlignLeft, label)

            # 퍼센트 텍스트 (바 오른쪽)
            pct_text = f"{pct:.0f}%"
            painter.setPen(QPen(bar_color))
            painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
            text_x = track.x() + fill_w + 2
            remaining = track.right() - text_x
            if remaining > 20:
                painter.drawText(
                    QRectF(text_x, y_top, remaining, bar_h),
                    Qt.AlignVCenter | Qt.AlignLeft, pct_text)
            else:
                # 바 안에 표기
                painter.setPen(QPen(QColor(BG4)))
                painter.drawText(
                    QRectF(track.x(), y_top, fill_w - 2, bar_h),
                    Qt.AlignVCenter | Qt.AlignRight, pct_text)

        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setWidth(max(hint.width(), 100))
        hint.setHeight(max(hint.height(), 28))
        return hint
