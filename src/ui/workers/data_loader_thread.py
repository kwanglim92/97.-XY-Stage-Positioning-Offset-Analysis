"""
data_loader_thread.py — 백그라운드 데이터 로딩 스레드
"""

from PySide6.QtCore import QThread, Signal
from recipe_scanner import load_all_recipes, compare_recipes


class DataLoaderThread(QThread):
    finished = Signal(object, object, float)
    error = Signal(str)

    def __init__(self, folder, parent=None):
        super().__init__(parent)
        self.folder = folder

    def run(self):
        import time
        t0 = time.perf_counter()
        try:
            results = load_all_recipes(self.folder, round_name='1st', axis='both')
            comparison = compare_recipes(results)
            elapsed = time.perf_counter() - t0
            self.finished.emit(results, comparison, elapsed)
        except Exception as e:
            self.error.emit(str(e))
