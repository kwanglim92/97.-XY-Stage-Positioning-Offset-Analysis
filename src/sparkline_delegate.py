"""
sparkline_delegate.py — Summary 테이블 Sparkline 렌더링

QPainter로 셀 내 미니 트렌드 차트를 그립니다.
- SparklineTrendDelegate: Lot별 Mean 값의 미니 라인 차트
"""

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath

# Catppuccin 색상
ACCENT = QColor('#89b4fa')
GREEN = QColor('#a6e3a1')
RED = QColor('#f38ba8')
BG3 = QColor('#45475a')
FG2 = QColor('#a6adc8')


class SparklineTrendDelegate(QStyledItemDelegate):
    """Lot별 Mean 트렌드를 미니 라인 차트로 렌더링.

    데이터는 Qt.UserRole에 [float, ...] 리스트로 저장합니다.
    """

    def paint(self, painter: QPainter, option, index):
        # 배경 그리기
        super().paint(painter, option, index)

        data = index.data(Qt.UserRole)
        if not data or not isinstance(data, list) or len(data) < 2:
            # 데이터 없으면 '—' 표시
            painter.setPen(QPen(FG2))
            painter.drawText(option.rect, Qt.AlignCenter, '—')
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # 그리기 영역 (패딩 적용)
        rect = option.rect.adjusted(4, 3, -4, -3)
        w = rect.width()
        h = rect.height()

        if w <= 0 or h <= 0:
            painter.restore()
            return

        # 값 범위 계산
        min_val = min(data)
        max_val = max(data)
        val_range = max_val - min_val
        if val_range == 0:
            val_range = 1.0  # 평탄한 경우

        n = len(data)
        step_x = w / (n - 1) if n > 1 else w

        # 포인트 계산 (Y축 반전: 위가 큰 값)
        points = []
        for i, val in enumerate(data):
            x = rect.x() + i * step_x
            y = rect.y() + h - ((val - min_val) / val_range) * h
            points.append((x, y))

        # 그래디언트 영역 (반투명 채우기)
        fill_path = QPainterPath()
        fill_path.moveTo(points[0][0], rect.y() + h)
        for x, y in points:
            fill_path.lineTo(x, y)
        fill_path.lineTo(points[-1][0], rect.y() + h)
        fill_path.closeSubpath()

        fill_color = QColor(ACCENT)
        fill_color.setAlpha(40)
        painter.fillPath(fill_path, fill_color)

        # 트렌드 라인
        line_path = QPainterPath()
        line_path.moveTo(points[0][0], points[0][1])
        for x, y in points[1:]:
            line_path.lineTo(x, y)

        pen = QPen(ACCENT, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(line_path)

        # 마지막 포인트 강조 (현재 값)
        last_x, last_y = points[-1]
        painter.setBrush(ACCENT)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(QRectF(last_x - 2, last_y - 2, 4, 4))

        painter.restore()

    def sizeHint(self, option, index):
        hint = super().sizeHint(option, index)
        hint.setWidth(max(hint.width(), 80))
        hint.setHeight(max(hint.height(), 24))
        return hint
