"""
system_logger.py — 시스템 로그 관리 (색상별 메시지 출력)
"""

from datetime import datetime
from PySide6.QtWidgets import QTextEdit
from ui.theme import FG2, GREEN, ORANGE, RED, PURPLE, ACCENT


class SystemLogger:
    COLORS = {'info': FG2, 'ok': GREEN, 'warn': ORANGE, 'err': RED, 'head': PURPLE}

    def __init__(self, text_edit: QTextEdit):
        self._te = text_edit
        self._te.setReadOnly(True)

    def _append(self, msg: str, tag: str = 'info'):
        ts = datetime.now().strftime('%H:%M:%S')
        color = self.COLORS.get(tag, FG2)
        tc = ACCENT
        self._te.append(f'<span style="color:{tc}">[{ts}]</span> '
                        f'<span style="color:{color}">{msg}</span>')

    def info(self, m):  self._append(m, 'info')
    def ok(self, m):    self._append(m, 'ok')
    def warn(self, m):  self._append(m, 'warn')
    def error(self, m): self._append(m, 'err')
    def head(self, m):  self._append(m, 'head')

    def section(self, title):
        self._te.append(f'<br><span style="color:{PURPLE};font-weight:bold">'
                        f'{"═"*50}<br>  {title}<br>{"═"*50}</span>')
