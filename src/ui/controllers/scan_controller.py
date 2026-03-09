from PySide6.QtWidgets import QFileDialog, QMessageBox
import os
from core.recipe_scanner import scan_recipes
from ui.workers.data_loader_thread import DataLoaderThread
from core.settings import add_recent_folder
from core import compute_deviation_matrix, compute_affine_transform


class ScanMixin:
    def _browse_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Root Data 폴더 선택", self.path_edit.text() or "")
        if path:
            self.path_edit.setText(path)
            self._scan_folder()


    def _scan_folder(self):
        folder = self.path_edit.text()
        if not folder or not os.path.isdir(folder):
            QMessageBox.warning(self, "경고", "유효한 폴더를 선택해주세요.")
            return

        self.main_tabs.setCurrentIndex(0)
        self.logger.section("폴더 스캔 시작")
        self.logger.info(f"경로: {folder}")
        self.statusBar().showMessage("스캔 중...")

        self.recipes = scan_recipes(folder)
        if not self.recipes:
            self.logger.warn("Recipe 구조를 찾지 못했습니다.")
            QMessageBox.information(self, "알림", "Recipe 구조를 찾지 못했습니다.")
            return

        # ─── 표준 Recipe 이름 검증 (Spec 설정 기준) ───
        spec_dev = self.settings.get('spec_deviation', {})
        std_names = list(spec_dev.keys())

        if std_names:
            # 설정의 스펙 이름과 발견된 Recipe의 short_name이 일치하는지 확인
            # (recipe_scanner가 '1. Vision Pattern' 처럼 앞의 숫자를 자른 short_name을 제공함)
            detected = [r['short_name'] for r in self.recipes]
            mismatched = []
            for r in self.recipes:
                is_match = False
                for std in std_names:
                    # 엄격한 일치 (대소문자 무시, 공백 제거)
                    std_clean = std.strip().lower()
                    if std_clean == r['name'].strip().lower() or \
                       std_clean == r['short_name'].strip().lower():
                        is_match = True
                        break

                if not is_match:
                    mismatched.append(r['name'])  # 불일치하면 원본 폴더명을 기록

            if mismatched:
                std_list = '\n'.join(f"  • {s}" for s in std_names)
                det_list = '\n'.join(f"  • {d}" for d in [r['name'] for r in self.recipes])
                mis_list = '\n'.join(f"  ❌ {m}" for m in mismatched)
                
                msg = (f"데이터 폴더명이 설정된 Spec 이름과 일치하지 않습니다.\n"
                       f"정확한 분석 및 Spec 판정을 위해 폴더명을 아래와 같이 변경해 주세요.\n\n"
                       f"【권장 폴더명 (Spec 설정 기준)】\n{std_list}\n\n"
                       f"【현재 감지된 폴더명】\n{det_list}\n\n"
                       f"【불일치 항목】\n{mis_list}")
                
                QMessageBox.critical(self, "❌ 폴더명 불일치 오류", msg)
                self.logger.error("폴더명 불일치로 스캔이 취소되었습니다.")
                return

        self.logger.ok(f"✅ {len(self.recipes)}개 Recipe 발견")
        for r in self.recipes:
            self.logger.info(f"  Step {r['index']}: {r['name']}")

        self.settings = add_recent_folder(self.settings, folder)
        self._save_settings()
        self._build_nav()

        self.logger.info("전체 Recipe 데이터 로드 시작 (1st round)...")
        self._loader_thread = DataLoaderThread(folder)
        self._loader_thread.finished.connect(self._on_scan_complete)
        self._loader_thread.error.connect(
            lambda e: (self.logger.error(f"로드 오류: {e}"),
                       QMessageBox.critical(self, "오류", e)))
        self._loader_thread.start()


    def _on_scan_complete(self, results, comparison, elapsed):
        self.recipe_results = results
        total = sum(len(r.get('raw_data', [])) for r in results)
        self.logger.ok(f"✅ 전체 로드 완료: {total}개 데이터 ({elapsed:.1f}초 소요)")
        self._update_summary_table(comparison, results)

        # 모든 Step Pass/Fail 일괄 계산 → 버튼 색상 즉시 반영
        self._compute_all_step_pass_states()

        # Affine Transform
        self.logger.section("Affine Transform 계통 오차 분석")
        for i, result in enumerate(self.recipe_results):
            data = result.get('raw_data', [])
            dx = compute_deviation_matrix(data, 'X')
            dy = compute_deviation_matrix(data, 'Y')
            if dx['die_stats'] and dy['die_stats']:
                af = compute_affine_transform(dx['die_stats'], dy['die_stats'])
                name = result.get('short_name', f'Step {i+1}')
                self.logger.head(f"[{name}]")
                self.logger.info(f"  Translation: Tx={af['tx']:+.4f} µm, Ty={af['ty']:+.4f} µm")
                self.logger.info(f"  Scaling: Sx={af['sx_ppm']:+.2f} ppm, Sy={af['sy_ppm']:+.2f} ppm")
                self.logger.info(f"  Rotation: θ={af['theta_deg']:+.6f}° ({af['theta_urad']:+.2f} µrad)")
                self.logger.info(f"  Residual RMS: X={af['residual_x']:.4f}, Y={af['residual_y']:.4f}")

        self.main_tabs.setCurrentIndex(1)
        self.data_tabs.setCurrentIndex(0)
        if self.recipe_results:
            self._select_step(0)

        # ─── Recipe 비교 차트 렌더링 ───
        if len(self.recipe_results) >= 2:
            try:
                self.chart_widgets['Boxplot'].set_figure(
                    viz.plot_recipe_comparison_boxplot(self.recipe_results))
                self.logger.ok("📊 Recipe Boxplot 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Boxplot 비교 오류: {e}")

            try:
                self.chart_widgets['Trend'].set_figure(
                    viz.plot_recipe_comparison_trend(self.recipe_results))
                self.logger.ok("📈 Recipe Trend 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Trend 비교 오류: {e}")

            try:
                self.chart_widgets['Heatmap'].set_figure(
                    viz.plot_recipe_comparison_heatmap(self.recipe_results))
                self.logger.ok("🗺️ Recipe Heatmap 비교 차트 생성 완료")
            except Exception as e:
                self.logger.error(f"Heatmap 비교 오류: {e}")

        self.statusBar().showMessage(
            f"✅ {len(self.recipes)}개 Recipe | {total}개 데이터 | Step 클릭 → 상세 분석")


