from PySide6.QtWidgets import QMessageBox, QFileDialog, QApplication
from PySide6.QtCore import Qt
import os
from core.tiff_loader import load_tiff
from charts import MultiTiffViewerWidget
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED, ORANGE, PURPLE


class TiffMixin:
    def _find_tiff_for_row(self, lot_name, site_id):
        """site_id를 포함하는 TIFF 파일을 해당 Lot 폴더에서 탐색.
        Debug/Capture 하위폴더는 제외하고 루트 파일만 검색합니다.
        """
        round_path = ''
        if 0 <= self.current_recipe_idx < len(self.recipe_results):
            result = self.recipe_results[self.current_recipe_idx]
            round_path = result.get('round_path', '')

        if not round_path or not os.path.isdir(round_path):
            self.logger.warn(f"TIFF 탐색 실패: round_path 없음")
            return []

        # ① lot_name으로 해당 Lot 폴더 찾기
        lot_folder = None
        for name in os.listdir(round_path):
            full = os.path.join(round_path, name)
            if os.path.isdir(full) and (name == lot_name or lot_name in name
                                         or name in lot_name):
                lot_folder = full
                break

        if not lot_folder:
            lot_folder = round_path
        self.logger.info(f"TIFF 탐색: {os.path.basename(lot_folder)} / {site_id}")

        # ② 루트 폴더의 파일만 검색 (Debug/Capture 하위폴더 제외)
        matched = []
        try:
            for f in os.listdir(lot_folder):
                fp = os.path.join(lot_folder, f)
                if os.path.isfile(fp) and f.lower().endswith(('.tif', '.tiff')) and site_id in f:
                    matched.append(os.path.normpath(fp))
        except OSError:
            pass

        if not matched:
            import re
            site_num = re.sub(r'[^0-9]', '', site_id)
            if site_num:
                try:
                    for f in os.listdir(lot_folder):
                        fp = os.path.join(lot_folder, f)
                        if os.path.isfile(fp) and f.lower().endswith(('.tif', '.tiff')) and site_num in f:
                            matched.append(os.path.normpath(fp))
                except OSError:
                    pass

        if matched:
            self.last_tiff_folder = os.path.normpath(lot_folder)
            self.tiff_path_label.setText(self.last_tiff_folder)
        else:
            self.logger.warn(f"TIFF 없음: {lot_name}/{site_id} in {lot_folder}")

        return matched


    def _on_row_double_click(self, row, col):
        lot_name = self.raw_table.item(row, 0)
        site_id = self.raw_table.item(row, 1)
        if not lot_name or not site_id:
            return
        lot_name, site_id = lot_name.text(), site_id.text()
        tiff_paths = self._find_tiff_for_row(lot_name, site_id)
        if not tiff_paths:
            self.statusBar().showMessage(f"⚠ TIFF 없음: {lot_name}/{site_id} (log 확인)")
            return

        # pspylib 사전 확인
        try:
            import pspylib.tiff.reader  # noqa: F401
        except ImportError:
            msg = "PSPylib 미설치: pip install pspylib-*.whl\n\nTIFF 런더링을 위해 PSPylib가 필요합니다."
            self.logger.error(msg.split('\n')[0])
            QMessageBox.warning(self, "PSPylib 없음", msg)
            return

        self.logger.info(f"TIFF 로드: {lot_name}/{site_id} ({len(tiff_paths)}개)")
        for p in tiff_paths:
            self.logger.info(f"  → {os.path.basename(p)}")
        self.statusBar().showMessage(f"TIFF 로드 중... {len(tiff_paths)}개")
        QApplication.processEvents()

        try:
            from core.tiff_loader import load_tiff

            results = []
            for tp in tiff_paths:
                try:
                    results.append(load_tiff(tp))
                except Exception as fe:
                    self.logger.warn(f"TIFF 로드 실패 [{os.path.basename(tp)}]: {fe}")

            if not results:
                self.statusBar().showMessage("⚠ TIFF 로드 실패")
                return

            # 모든 TIFF를 서브탭으로 표시
            self._tiff_viewer.set_results(results)
            self._show_tiff()
            self.statusBar().showMessage(f"✅ TIFF {len(results)}개 로드 완료: {lot_name}/{site_id}")

        except Exception as e:
            import traceback
            self.logger.error(f"TIFF 오류: {e}")
            self.logger.info(traceback.format_exc())
            self.statusBar().showMessage(f"⚠ TIFF 오류: {e}")



    def _show_tiff(self):
        """TIFF 탭으로 전환."""
        self._select_chart('🔬 TIFF')


    def _open_tiff_folder(self):
        folder = os.path.normpath(self.last_tiff_folder) if self.last_tiff_folder else ''
        if folder and os.path.isdir(folder):
            os.startfile(folder)
        elif folder:
            self.statusBar().showMessage(
                f"⚠ 폴더 없음: {folder}")
        else:
            self.statusBar().showMessage(
                "⚠ 먼저 '원본 데이터' 탭에서 행을 더블클릭하여 TIFF를 로드하세요.")

    # ──────────────────────────────────────────────
    # Export
    # ──────────────────────────────────────────────

