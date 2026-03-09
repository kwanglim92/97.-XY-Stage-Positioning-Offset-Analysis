"""
guide_dialog.py — Analysis Guide 도움말 대화상자
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QSplitter, QListWidget,
    QTextBrowser, QDialogButtonBox,
)
from PySide6.QtCore import Qt
from ui.theme import BG, BG2, BG3, FG, FG2, ACCENT, GREEN, RED


class GuideDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Analysis Guide")
        self.resize(1000, 700)
        self.setStyleSheet(f"background: {BG}; color: {FG}; font-family: 'Malgun Gothic', 'Segoe UI', sans-serif;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        splitter = QSplitter(Qt.Horizontal)
        
        # Left Panel (List)
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet(f"""
            QListWidget {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 6px; outline: none; }}
            QListWidget::item {{ padding: 14px 10px; border-bottom: 1px solid {BG3}; border-radius: 4px; margin: 2px; }}
            QListWidget::item:selected {{ background: {ACCENT}; color: {BG}; font-weight: bold; }}
            QListWidget::item:hover:!selected {{ background: {BG3}; }}
        """)
        self.nav_list.setCursor(Qt.PointingHandCursor)
        
        # Guide Contents
        self.contents = {
            "1. 데이터 테이블 & 지표 해석": (
                "<h2>📊 1. 데이터 테이블 & 기초 통계 지표 해석</h2>"
                "<p>XY Stage Positioning 분석의 출발점은 <b>통계 지표가 의미하는 장비 상태를 정확히 파악</b>하는 것입니다. 각 지표는 서로 독립적으로 보지 않고, <b>조합해서 해석</b>할 때 가장 유효합니다.</p>"
                "<table>"
                "<tr><th>지표</th><th>수식 / 정의</th><th>엔지니어 해석 포인트</th></tr>"
                "<tr><td><b>Mean (평균)</b></td><td>Σx / n</td><td>스테이지의 <b>계통 오차(Systematic Error)</b>를 나타냄. 0에서 벗어날수록 기계적 오프셋(Offset)이나 캘리브레이션 오류 의심. X Mean ≠ 0이면 X축 스테이지의 영점이 틀어진 것.</td></tr>"
                "<tr><td><b>StdDev (표준편차, σ)</b></td><td>√(Σ(x-μ)² / n)</td><td>측정 <b>재현성(Repeatability)</b>의 지표. 동일 조건에서 반복 측정했을 때 값이 흩어지는 정도. σ가 크면 스테이지 진동, 인코더 노이즈, 기계적 유격(Backlash) 등을 의심.</td></tr>"
                "<tr><td><b>Range (범위)</b></td><td>Max − Min</td><td>Single Outlier에도 민감하게 반응. Outlier 제거 후에도 Range가 크지 함께 확인해야 함. Out 지표와 교차 분석 필수.</td></tr>"
                "<tr><td><b>CV% (변동계수)</b></td><td>(σ / |μ|) × 100</td><td>Mean이 0에 가까울 때 CV%는 매우 민감하게 반응하므로, Mean이 극소값일 때 단독 해석에 주의.</td></tr>"
                "<tr><td><b>Out (이상치 수)</b></td><td>IQR 기준 탐지</td><td>Q1 − 1.5×IQR ~ Q3 + 1.5×IQR 밖의 데이터 수. Out &gt; 0이면 특정 Lot/시점에 국소적 이벤트(기계 충격, 진동, 첩 오류 등)가 발생했음을 시사.</td></tr>"
                "<tr><td><b>Cpk (공정능력지수)</b></td><td>min[(USL−μ)/3σ, (μ−LSL)/3σ]</td><td><b>1.33 이상이 합격 기준</b>(4σ). Cpk가 낙은데 σ가 작다면 Mean이 규격 중심에서 치우쳐있는 것으로 영점 재조정 필요.</td></tr>"
                "</table>"
                "<h3>포합 해석 사례</h3>"
                "<table>"
                "<tr><th>상황</th><th>엔지니어 해석 및 조치</th></tr>"
                "<tr><td>Mean 작음 + σ 큼</td><td>평균 위치는 맞지만 <b>재현성이 나쁜 상태</b> → 스테이지 진동 또는 인코더 노이즈 조사</td></tr>"
                "<tr><td>σ 작음 + Mean 큼</td><td>정밀하지만 <b>정확하지 않음(Accurate but not precise)</b> → 오프셋 보정(Calibration) 필요</td></tr>"
                "<tr><td>σ, Mean 둘 다 나쁜 경우</td><td>근본적인 <b>스테이지 정렬 실패</b> 검토 필요</td></tr>"
                "</table>"
            ),
            "2. Die & Raw 분산 테이블": (
                "<h2>🔢 2. Die별 평균 & Raw Deviation 분석</h2>"
                "<h3>Die별 평균 (Die Average Heatmap)</h3>"
                "<p>Wafer 전면을 격자로 분할한 <b>각 Die 위치에서의 평균 오차</b>입니다. 색상 히트맵으로 표현되어 공간적 패턴을 직관적으로 파악할 수 있습니다.</p>"
                "<table>"
                "<tr><th>관심 패턴</th><th>시각적 특징</th><th>가능한 원인</th></tr>"
                "<tr><td><b>Edge Effect</b></td><td>Wafer 가장자리 Die만 붉거나 파람색</td><td>첩(Chuck) Edge 홀딩 불균일, 진공 흡착 불량, 가장자리 노광(Exposure) 편차</td></tr>"
                "<tr><td><b>대각선 편차</b></td><td>특정 대각 방향으로 색상이 치우침</td><td>스테이지 Pitch/Yaw 틀어짐, 레일 마모 편차</td></tr>"
                "<tr><td><b>중앙/주변 분리</b></td><td>중앙 정상 + 주변 이상 (또는 반대)</td><td>첩 곡률(Bow/Warp) 문제, 웨이퍼 핀 기준점 오류</td></tr>"
                "<tr><td><b>특정 Die 집중</b></td><td>단 1~2개 Die만 극단적 색상</td><td>해당 위치 인코더 이상, 해당 좌표 기구학적 이물질</td></tr>"
                "</table>"
                "<p><b>해석 방법:</b> StdDev 열과 함께 확인하세요. Avg만 크고 StdDev가 작으면 해당 위치에서의 오차는 <b>일관되고 반복적(즉, 구조적 문제)</b>입니다. Avg와 StdDev가 모두 크면 <b>랜덤한 노이즈</b> 성분이 강한 것입니다.</p>"
                "<hr>"
                "<h3>Raw Deviation (원천 편차 매트릭스)</h3>"
                "<p>통계 처리 없이, <b>개별 측정(Repeat) × Die 위치</b>의 순수 측정값 행렬입니다.</p>"
                "<table>"
                "<tr><th>확인 방향</th><th>해석 내용</th></tr>"
                "<tr><td><b>수평 방향 (행: Repeat)</b></td><td>같은 Repeat 내 Die 간 오차 분포 확인. <b>특정 Repeat에서만 전 Die가 오차가 큰 경우</b> → 해당 측정 시점의 환경(진동, 온도 변화) 의심</td></tr>"
                "<tr><td><b>수직 방향 (열: Die)</b></td><td>동일 Die에서 Repeat 간 오차 변화 확인. <b>Repeat이 반복될수록 오차가 커지는 경우</b> → 해당 위치의 <b>열팔대(Thermal Drift)</b> 또는 <b>기계적 유격 누적</b> 의심</td></tr>"
                "</table>"
            ),
            "3. XY Scatter (산점도) 분석": (
                "<h2>🎯 3. XY Scatter 플롯 심화 해석</h2>"
                "<p>XY Scatter는 <b>X 오차 vs Y 오차</b>를 2D 평면에 표현한 차트로, 스테이지의 <b>동작 특성을 가장 직관적으로 진단</b>할 수 있는 그래프입니다.</p>"
                "<h3>3.1 분포 형태별 엔지니어 해석</h3>"
                "<table>"
                "<tr><th>분포 형태</th><th>시각적 설명</th><th>원인 및 조치</th></tr>"
                "<tr><td><b>Bull's-eye (동심원 집중)</b></td><td>점들이 원점 중심으로 조밀하게 모임</td><td>✅ 정상 상태. 스테이지 정밀도 우수</td></tr>"
                "<tr><td><b>수직·수평 편위</b></td><td>점군이 X 또는 Y 한 방향으로만 치우침</td><td>해당 축 Linear Motor 또는 Encoder 오류, 오프셋 보정 필요</td></tr>"
                "<tr><td><b>사선 형태 (Linear Trend)</b></td><td>45° 또는 임의 각도의 선형 분포</td><td>X-Y 축 간 커플링(Coupling) 발생. 스테이지 <b>직각도(Squareness) 불량</b> 의심</td></tr>"
                "<tr><td><b>다중 군집</b></td><td>2~3개의 점 그룹이 분리되어 존재</td><td>Lot 간 재현 조건 차이(온도, 웨이퍼 로딩 변화) 또는 특정 레시피에만 나타나는 구조적 차이</td></tr>"
                "<tr><td><b>타원형 분포 (Ellipse)</b></td><td>타원형으로 넓게 퍼진 분포</td><td>두 축의 진동 크기가 다름. <b>기계 구동부의 강성(Stiffness) 불균형</b> 의심</td></tr>"
                "<tr><td><b>Outlier 산재</b></td><td>대부분은 집중, 일부가 멀리 떨어짐</td><td>특정 Lot의 이상 이벤트. Raw Data의 Outlier 탭과 교차 확인 필요</td></tr>"
                "</table>"
                "<h3>3.2 Spec Guide Box 해석</h3>"
                "<p>그래프 중앙의 <b>빨간 점선 사각형(Guide Box)</b> = ± Spec Range 한계치입니다.</p>"
                "<ul>"
                "<li>점들의 <b>분포 중심(Centroid)이 박스 안</b>에 있어도 <b>일부 점이 밖</b>에 있으면 → 오차 Range 초과로 FAIL</li>"
                "<li>박스가 매우 <b>좌우 빽빽하게 채워진</b> 경우 → 장비가 Spec 한계선 경계에서 운용 중. <b>Spec 여유도(Spec Margin) 검토 필요</b></li>"
                "<li><b>Log Scale 전환 시</b> → 극단적 Outlier의 영향을 줄이고 전체 분포 패턴 파악에 유리</li>"
                "</ul>"
            ),
            "4. Vector & Wafer Map 이해": (
                "<h2>↗️ 4. Vector Map & Wafer Contour 심화 분석</h2>"
                "<h3>4.1 Vector Map (벡터맵) 패턴 해석</h3>"
                "<p>각 Die 위치에서의 <b>오차 벡터(크기 + 방향)</b>를 화살표로 표현합니다. 단순한 크기미 아니라 <b>방향성 패턴</b>이 핵심입니다.</p>"
                "<table>"
                "<tr><th>벡터 패턴</th><th>엔지니어 해석 및 조치</th></tr>"
                "<tr><td><b>모든 화살표가 같은 방향</b></td><td>고정 오프셋(Constant Offset). Mean 값이 0에서 치우쳐 있는 상태. <b>Calibration으로 즉시 수정 가능</b></td></tr>"
                "<tr><td><b>방사형 (중앙→가장자리로 퍼짐)</b></td><td>스케일 오차(Scale Error). <b>EGA 스케일 파라미터 재보정</b> 필요</td></tr>"
                "<tr><td><b>소용돌이형 (Swirl)</b></td><td>스테이지 회전(Rotation/Theta) 오차. <b>Theta 축 오프셋 조정</b> 필요</td></tr>"
                "<tr><td><b>지역적 불규칙</b></td><td>특정 구역만 벡터 방향·크기 이상 → 해당 영역의 <b>첩(Chuck) 핀 이상</b> 또는 <b>국소 기구 마모</b> 검토</td></tr>"
                "<tr><td><b>랜덤 방향 (무작위)</b></td><td>구조적 패턴 없음 → 측정 재현성 자체가 부족. <b>진동 방지(Isolation)</b>나 측정 환경 개선 검토</td></tr>"
                "</table>"
                "<p><b>Vector Scale 슬라이더 활용:</b> 실제 오차는 수 μm 이내라 육안 관찰이 어렵습니다. 슬라이더로 벡터 길이를 수십~수백 배 증폭하여 패턴을 명확하게 확인하세요. 단, <b>증폭된 길이 자체가 실제 오차 수치가 아님</b>에 유의하세요.</p>"
                "<hr>"
                "<h3>4.2 Wafer Contour (등고선 맵) 해석</h3>"
                "<p>Wafer 전면의 <b>오차 분포를 연속적인 컬러 맵</b>으로 시각화합니다. 측정하지 않은 Die 사이의 값은 보간(Interpolation)으로 채움니다.</p>"
                "<table>"
                "<tr><th>색상</th><th>의미</th></tr>"
                "<tr><td>🔴 붉은 계열</td><td>양(+) 방향의 큰 오차 구역 (High-Deviation Zone)</td></tr>"
                "<tr><td>🔵 청색/녹색 계열</td><td>음(-) 방향 또는 오차가 작은 구역 (Low-Deviation Zone)</td></tr>"
                "</table>"
                "<p><b>색상 전환이 급격한 구역</b> → <b>오차 구대(Gradient)가 급격</b>하게 변화. 해당 위치에 기구학적 변곡점 존재 가능성.</p>"
                "<p><b>X / Y 채널 교차 비교:</b> X 채널은 정상이고 Y만 등고선이 기울어진다면 → Y축 전용 문제(인코더, 레일, 선형 모터) 격리 검토. X와 Y 두 소의 체미럼 판도가 유사하다면 → 공통 원인(기울어진 첩, 하중 편심) 가능성.</p>"
            ),
            "5. Spec 판정과 오류 처리": (
                "<h2>✅ 5. Spec 판정 (PASS/FAIL) 기준 및 설정 로직</h2>"
                "<h3>5.1 판정 흐름</h3>"
                "<table>"
                "<tr><th>단계</th><th>내용</th></tr>"
                "<tr><td>1. 스캔 데이터 수집</td><td>CSV 폴더에서 원시 수치 로드</td></tr>"
                "<tr><td>2. Deviation Matrix 계산</td><td>overall_range, overall_stddev 산출</td></tr>"
                "<tr><td>3. Spec값과 비교</td><td>overall_range ≤ spec_range <b>and</b> overall_stddev ≤ spec_stddev</td></tr>"
                "<tr><td>4. 최종 판정</td><td><b>두 조건 모두 충족</b> → ✅ PASS / <b>하나라도 초과</b> → ❌ FAIL</td></tr>"
                "</table>"
                "<h3>5.2 Spec 설정 값 의미</h3>"
                "<table>"
                "<tr><th>Spec 항목</th><th>의미</th><th>설정 가이드</th></tr>"
                "<tr><td><b>spec_range</b></td><td>허용되는 최대 오차 범위 (μm)</td><td>고객/장비 사양의 Positioning Accuracy 값을 기준으로 설정</td></tr>"
                "<tr><td><b>spec_stddev</b></td><td>허용되는 최대 표준편차 (μm)</td><td>Repeatability 사양 기준으로 설정. 일반적으로 range의 1/3~1/5 수준</td></tr>"
                "</table>"
                "<h3>5.3 폴더명 불일치 에러 (⚠️ 가장 흔한 운영 오류)</h3>"
                "<p>측정 장비에서 내보낸 데이터 폴더 이름은 Spec 설정 이름과 <b>정확히</b> 일치해야 합니다.</p>"
                "<table>"
                "<tr><th>올바른 폴더명 (✅)</th><th>잘못된 폴더명 (❌)</th></tr>"
                "<tr><td>Vision Pattern</td><td>1. Vision Pattern Recognize, VisionPttrn</td></tr>"
                "<tr><td>In-Die Align</td><td>In Die Align, in_die_align</td></tr>"
                "<tr><td>LLC Translation</td><td>LLC Trans, LLCtranslation</td></tr>"
                "<tr><td>Global Align</td><td>4. Global Align, GlobalAlign</td></tr>"
                "</table>"
                "<p>불일치 시 분석이 <b>원천 차단</b>됩니다. 탐색기에서 폴더 이름을 변경 후 재스캔하세요.</p>"
                "<h3>5.4 Cpk와 Spec Range 연계 해석</h3>"
                "<p>Cpk는 <code>spec_limits</code>의 LSL/USL 기준이며, PASS/FAIL 판정은 <code>spec_deviation</code>의 <code>spec_range</code>/<code>spec_stddev</code> 기준입니다. 두 기준이 <b>독립적</b>으로 동작하므로, <b>Cpk가 높아도 Range가 Spec을 초과하면 FAIL</b>이 날 수 있습니다. 반드시 두 지표를 함께 확인하세요.</p>"
            )
        }

        for title in self.contents.keys():
            self.nav_list.addItem(title)
            
        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        # Right Panel (Content)
        self.content_browser = QTextBrowser()
        self.content_browser.setStyleSheet(f"""
            QTextBrowser {{ background: {BG2}; border: 1px solid {BG3}; border-radius: 6px; padding: 24px; font-size: 11pt; }}
        """)
        self.content_browser.setOpenExternalLinks(False)

        splitter.addWidget(self.nav_list)
        splitter.addWidget(self.content_browser)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        layout.addWidget(splitter)
        
        # 버튼 박스
        btn_box = QDialogButtonBox(QDialogButtonBox.Close)
        btn_box.setStyleSheet(f"""
            QPushButton {{ background: {BG3}; color: {FG}; padding: 8px 30px; border-radius: 4px; border: 1px solid {BG3}; font-weight: bold; }}
            QPushButton:hover {{ background: {FG2}; color: {BG}; }}
        """)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.nav_list.setCurrentRow(0)

    def _on_nav_changed(self, idx):
        if idx < 0: return
        itemTitle = self.nav_list.item(idx).text()
        html_body = self.contents.get(itemTitle, "")
        
        css = (
            f"h2 {{ color: {ACCENT}; border-bottom: 2px solid {BG3}; padding-bottom: 12px; margin-bottom: 20px; font-size: 18pt; }}"
            f"h3 {{ color: {ACCENT}; margin-top: 32px; font-size: 14pt; }}"
            f"p {{ line-height: 1.6; margin-bottom: 16px; color: {FG}; }}"
            f"b {{ color: {GREEN}; font-weight: bold; font-size: 11pt; }}"
            f"ul {{ margin-top: 8px; margin-bottom: 16px; margin-left: -10px; }}"
            f"li {{ margin-bottom: 10px; line-height: 1.6; color: {FG}; }}"
            f"hr {{ border: none; border-top: 1px solid {BG3}; margin: 28px 0; }}"
            f"table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}"
            f"th, td {{ border: 1px solid {BG3}; padding: 12px; text-align: left; line-height: 1.4; }}"
            f"th {{ background-color: {BG}; color: {FG}; font-weight: bold; border-bottom: 2px solid {BG3}; }}"
            f"td {{ color: {FG}; }}"
            f"code {{ background-color: rgba(0,0,0,0.3); padding: 4px 6px; border-radius: 4px; color: {RED}; font-family: Consolas, monospace; }}"
        )
        
        full_html = "<html><head><style>" + css + "</style></head><body>" + html_body + "</body></html>"
        self.content_browser.setHtml(full_html)
