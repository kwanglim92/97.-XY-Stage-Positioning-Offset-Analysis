"""
system_logger.py — 시스템 로그 관리 (색상별 메시지 출력)
"""

from datetime import datetime
from PySide6.QtWidgets import QTextEdit
from ui.theme import FG2, GREEN, ORANGE, RED, PURPLE, ACCENT


class SystemLogger:
    COLORS = {'info': FG2, 'ok': GREEN, 'warn': ORANGE, 'err': RED, 'head': PURPLE}

    # 엑셀 등에 내보낼 때 쓸 사람이 읽는 구분명
    LEVEL_NAMES = {'info': '정보', 'ok': '완료', 'warn': '경고',
                   'err': '오류', 'head': '항목', 'section': '구분'}

    def __init__(self, text_edit: QTextEdit):
        self._te = text_edit
        self._te.setReadOnly(True)
        # 화면에는 HTML로만 남으므로, 내보내기용 평문 기록을 따로 보관한다.
        self._records = []

    def _append(self, msg: str, tag: str = 'info'):
        ts = datetime.now().strftime('%H:%M:%S')
        color = self.COLORS.get(tag, FG2)
        tc = ACCENT
        self._records.append({'time': ts, 'level': tag, 'message': msg})
        self._te.append(f'<span style="color:{tc}">[{ts}]</span> '
                        f'<span style="color:{color}">{msg}</span>')

    def info(self, m):  self._append(m, 'info')
    def ok(self, m):    self._append(m, 'ok')
    def warn(self, m):  self._append(m, 'warn')
    def error(self, m): self._append(m, 'err')
    def head(self, m):  self._append(m, 'head')

    def section(self, title):
        ts = datetime.now().strftime('%H:%M:%S')
        self._records.append({'time': ts, 'level': 'section', 'message': title})
        self._te.append(f'<br><span style="color:{PURPLE};font-weight:bold">'
                        f'{"═"*50}<br>  {title}<br>{"═"*50}</span>')

    def export_rows(self) -> list:
        """내보내기용 로그 레코드 — [{'time', 'level', 'message'}, ...] (표시명 적용)."""
        return [{'time': r['time'],
                 'level': self.LEVEL_NAMES.get(r['level'], r['level']),
                 'message': r['message']}
                for r in self._records]

    def clear(self):
        self._records.clear()
        self._te.clear()
