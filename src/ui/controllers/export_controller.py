from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QTimer
import os, threading
from core.exporter import export_combined_csv, export_excel_report
from core import compute_repeatability, compute_trend
from core.recipe_scanner import load_all_recipes, compare_recipes
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


class ExportMixin:
    def _export_csv(self):
        if not self.raw_data:
            QMessageBox.warning(self, "경고", "먼저 분석을 실행해주세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "CSV", "", "Text (*.txt);;CSV (*.csv)", "Analysis.txt")
        if path:
            export_combined_csv(self.raw_data, path)
            self.logger.ok(f"CSV 저장: {path}")


    def _export_excel(self):
        if not self.raw_data:
            QMessageBox.warning(self, "경고", "먼저 분석을 실행해주세요.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Excel", "", "Excel (*.xlsx)", "Report.xlsx")
        if path:
            try:
                stats = compute_repeatability(self.raw_data)
                trend = compute_trend(self.raw_data)
                export_excel_report(self.raw_data, stats, trend, path)
                self.logger.ok(f"Excel 저장: {path}")
            except Exception as e:
                self.logger.error(f"Excel 오류: {e}")


    def _export_pdf(self):
        if not self.recipes:
            QMessageBox.warning(self, "경고", "스캔된 데이터가 없습니다.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "PDF", "", "PDF (*.pdf)", "Report.pdf")
        if not path:
            return
        self.logger.info("PDF 리포트 생성 중...")

        def run():
            try:
                results = load_all_recipes(self.path_edit.text(), round_name='1st', axis='both')
                comp = compare_recipes(results)
                from core.pdf_generator import generate_pdf_report
                generate_pdf_report(path, self.path_edit.text(), results, comp,
                                    self.settings.get('spec_limits', {}))
                QTimer.singleShot(0, lambda: self.logger.ok(f"PDF 저장 완료: {path}"))
                os.startfile(path)
            except Exception as e:
                QTimer.singleShot(0, lambda: self.logger.error(f"PDF 오류: {e}"))

        threading.Thread(target=run, daemon=True).start()


