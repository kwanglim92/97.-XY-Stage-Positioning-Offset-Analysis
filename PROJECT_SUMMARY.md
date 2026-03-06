# 📊 XY Stage Positioning Offset Analysis Tool

> **프로젝트**: XY Stage Offset 분석 도구 (PySide6)  
> **버전**: v9.0  
> **최종 업데이트**: 2026-03-04  
> **플랫폼**: Windows / Python 3.11+  

---

## 1. 프로젝트 개요

반도체/MEMS 장비의 XY Stage가 웨이퍼 상의 각 Die 위치로 이동할 때 발생하는 **위치 오프셋(Offset)**을 체계적으로 분석하는 데스크톱 도구입니다.

### 핵심 가치
- **다단계 Recipe 비교**: Vision Pattern, In-Die Align, LLC Translation, Global Align 등 여러 보정 단계를 한 번에 로드하여 비교
- **계통 오차 분리**: Affine Transform을 통해 Stage H/W의 Translation, Scaling, Rotation 오차를 수학적으로 추출
- **X/Y 독립 분석**: X축과 Y축 오프셋을 분리하여 축별 드리프트 감지
- **Die 단위 시각화**: Wafer Contour Map, Vector Map, XY Scatter 등으로 공간적 패턴을 즉시 파악
- **Spec 기반 PASS/FAIL 판정**: `settings.json`의 `spec_deviation` 기준으로 자동 판정

---

## 2. 기술 스택

### 2.1 핵심 스택

| 항목 | 기술 | 비고 |
|---|---|---|
| **언어** | Python 3.11 | |
| **GUI 프레임워크** | PySide6 (Qt 6) | LGPL v3 |
| **테마** | Catppuccin Mocha (다크) | QSS 기반 |
| **차트 (정적)** | Matplotlib 3.x (`QtAgg` 백엔드) | Contour, Vector, Boxplot 등 |
| **차트 (인터랙티브)** | pyqtgraph (OpenGL 가속) | Lot Trend, Distribution, 3D Surface |
| **데이터 처리** | pandas, numpy | |
| **보간** | scipy.interpolate (`griddata`, cubic) | Contour Map |
| **선형대수** | numpy.linalg (`lstsq`) | Affine Transform |
| **TIFF 파싱** | struct 모듈 | PSPylib 바이너리 포맷 |
| **설정 관리** | JSON (`settings.json`) | |
| **리포트** | openpyxl (Excel), Matplotlib PDF | |

### 2.2 외부 의존성 (pip)
```
PySide6
numpy
pandas
scipy
matplotlib
openpyxl
pyqtgraph
PyOpenGL
```

---

## 3. 디자인 시스템 — Catppuccin Mocha 테마

### 3.1 색상 팔레트

모든 프로젝트에서 통일적으로 사용하는 **Catppuccin Mocha** 테마입니다.

```python
# Color Constants (Catppuccin Mocha)
BG      = '#1e1e2e'   # Base      — 메인 배경
BG2     = '#282a3a'   # Mantle    — 카드/패널 배경  (실제 #282a36 변형)
BG3     = '#313244'   # Surface0  — 구분선, 비활성 탭
FG      = '#cdd6f4'   # Text      — 기본 텍스트
FG2     = '#a6adc8'   # Subtext0  — 보조 텍스트
ACCENT  = '#89b4fa'   # Blue      — 강조, 활성 탭, 링크
GREEN   = '#a6e3a1'   # Green     — PASS, 성공
RED     = '#f38ba8'   # Red       — FAIL, 오류, 경고
ORANGE  = '#fab387'   # Peach     — 주의, 보조 강조
PURPLE  = '#cba6f7'   # Mauve     — 특수 강조
```

### 3.2 QSS 스타일 패턴

```css
/* 탭 스타일 */
QTabBar::tab { background: BG3; color: FG2; padding: 8px 16px; border-radius: 4px 4px 0 0; }
QTabBar::tab:selected { background: BG; color: ACCENT; font-weight: bold; }

/* 버튼 스타일 */
QPushButton { background: BG3; color: FG; padding: 6px 12px; border-radius: 4px; }
QPushButton:hover { background: #45475a; }

/* 테이블 스타일 */
QHeaderView::section { background: BG3; color: FG2; padding: 4px; border: none; }
QTableWidget { gridline-color: BG3; selection-background-color: #45475a; }

/* 카드 스타일 (QFrame) */
#statcard { background: BG2; border: 1px solid #585b70; border-radius: 6px; padding: 8px; }
#statcard QLabel { background: transparent; }
```

### 3.3 차트 스타일 가이드

| 요소 | 색상 | 용도 |
|---|---|---|
| X축 데이터 라인 | `#89b4fa` (ACCENT) | Lot Trend X, 분포 X |
| Y축 데이터 라인 | `#f38ba8` (RED) | Lot Trend Y, 분포 Y |
| Spec 한계선 | `#cba6f7` (PURPLE), dashed | ±half_range |
| Overall Mean 기준선 | `#a6adc8` (FG2), dashed | 전체 평균 |
| 1σ 영역 | 반투명 fill | Mean ± 1σ 범위 |
| 차트 배경 | `#1e1e2e` (BG) | |
| 그리드 | `#313244` (BG3), 0.3 alpha | |

---

## 4. 프로젝트 구조

```
97. XY Stage Positioning Offset Analysis/
├── src/
│   ├── main.py              # GUI 메인 (DataAnalyzerApp, ~2400행)
│   ├── csv_loader.py        # Lot 폴더 스캔, CSV/TXT 배치 로드
│   ├── recipe_scanner.py    # Recipe 디렉토리 구조 자동 탐지 + 트렌드 계산
│   ├── analyzer.py          # 통계, Cpk, Deviation Matrix, Affine Transform
│   ├── visualizer.py        # Matplotlib 차트 (Contour, Vector, Scatter 등)
│   ├── visualizer_pg.py     # pyqtgraph 인터랙티브 차트 (Trend, 분포, 3D)
│   ├── sparkline_delegate.py # QPainter 기반 커스텀 셀 렌더링
│   ├── exporter.py          # CSV/Excel 내보내기
│   ├── pdf_generator.py     # PDF 리포트 생성
│   ├── tiff_loader.py       # PSPylib TIFF 바이너리 파서
│   ├── settings.py          # 설정 로드/저장 유틸리티
│   └── settings.json        # 사용자 설정 (Spec, 창 위치 등)
├── data/                    # 측정 데이터 (Recipe별 폴더 구조)
├── docs/                    # 가이드 문서
└── PROJECT_SUMMARY.md       # 이 문서
```

---

## 5. 모듈 상세

### 5.1 `csv_loader.py` — 데이터 로딩
- Lot 폴더 단위로 CSV/TXT 파일을 스캔
- `HZ1_O` 컬럼에서 X/Y Offset 값 추출
- 각 레코드에 `method` 키로 X/Y 축 정보 저장 (Method ID 기반)
- Outlier 감지 (IQR 방식) 및 유효성 필터링

### 5.2 `recipe_scanner.py` — Recipe 자동 탐지
- 지정 폴더 하위의 Recipe 디렉토리 구조를 자동으로 스캔
- Step 인덱스, 이름, Round 경로를 구조화하여 반환
- `compute_trend()` — Lot별 Mean/StdDev 트렌드 계산

### 5.3 `analyzer.py` — 분석 엔진

| 함수 | 설명 |
|---|---|
| `compute_statistics` | N, Mean, StdDev, Min, Max, CV% |
| `compute_cpk` | Cpk = min((USL-μ), (μ-LSL)) / (3σ) |
| `compute_deviation_matrix` | Die × Repeat 편차 행렬, overall_range/stddev |
| `compute_affine_transform` | 최소자승법으로 Tx, Ty, Sx(ppm), Sy(ppm), θ(deg) 추출 |
| `filter_by_method` | `method` 필드로 X/Y 필터링 |
| `detect_outliers` | IQR 기반 이상치 검출 |

### 5.4 `visualizer_pg.py` — pyqtgraph 인터랙티브 차트

| 함수 | 설명 |
|---|---|
| `create_dual_trend_widget` | X/Y 분리 Lot Trend (Mean ± 1σ, Spec 라인) |
| `create_distribution_widget` | 히스토그램 + KDE |
| `create_surface_3d_widget` | OpenGL 3D 표면 맵 |

### 5.5 `main.py` — GUI (DataAnalyzerApp)

**레이아웃 구조 (QSplitter 5:5):**
```
┌─────────────────────────────────────────────────────────────┐
│ [📁 폴더] [찾아보기] [🔄 스캔 & 분석]      [Wafer: 300mm] │
├─────────────────────────────────────────────────────────────┤
│ Workflow: [Step 1 ▶ Step 2 ▶ Step 3 ▶ Step 4]              │
├──────────────────────┬──────────────────────────────────────┤
│ Step: 1. Vision Pat. │ 기본 분석 | 인터랙티브 | 고급 분석 | │
│                      │ 비교 | Export                        │
│ ┌─X Offset──────────┐│                                      │
│ │ Avg: 2736.439     ││        (차트 영역)                    │
│ │ Range: 1.313 /1.0 ▲││  Contour X/Y | XY Scatter |         │
│ │ StdDev: 0.253/0.2 ▲││  Vector Map | Die Position |        │
│ │ Cpk: 2.98         ││  Lot Trend | 분포 | 3D Surface |     │
│ │ ❌ FAIL            ││  TIFF                                │
│ └───────────────────┘│                                      │
│ ┌─Y Offset──────────┐│                                      │
│ │ (동일 구조)        ││                                      │
│ └───────────────────┘│                                      │
│ ⚙️ Spec 설정         │                                      │
│──────────────────────│                                      │
│ 📝 시스템 로그        │                                      │
│ 🗄️ 데이터 테이블      │                                      │
│  ├ Summary           │                                      │
│  ├ Die별 평균 (X/Y)   │                                      │
│  ├ Raw Deviation     │                                      │
│  └ 원본 데이터       │                                      │
│──────────────────────│                                      │
│ Die 필터 (체크박스)   │                                      │
└──────────────────────┴──────────────────────────────────────┘
```

**주요 UI 패턴:**
- **StatCard**: X/Y 카드에 Spec 대비 표기 (`value / spec ▲+N%` or `✓N%`)
- **히트맵 테이블**: Die Average — 양방향 Red-Blue / StdDev·Range — Steel Blue
- **Luminance 기반 텍스트 반전**: 배경 밝기에 따라 흰/검 자동 계산
- **드래그 선택 & Ctrl+C 복사**: `CopyableTable` 위젯
- **Sub-Tab 패턴**: '📊 분포', '🌐 3D Surface' — X/Y 서브탭 내장
- **Spec 설정 다이얼로그**: Deviation Spec + Offset Limits 표 형태로 표시

---

## 6. 데이터 흐름

```
📁 Root 폴더 선택
    ↓
recipe_scanner: Recipe 구조 자동 탐지 (Step 번호, 이름, Round)
    ↓
csv_loader: Lot별 CSV/TXT 배치 로드 → records[] (method='X'/'Y')
    ↓
analyzer: compute_statistics(X), compute_statistics(Y) → Mean, StdDev, Cpk
analyzer: compute_deviation_matrix(X/Y) → overall_range, overall_stddev
    ↓
PASS/FAIL 판정: spec_deviation 기준 (settings.json)
    ↓
visualizer: Contour / Vector / Scatter (Matplotlib)
visualizer_pg: Lot Trend / Distribution / 3D (pyqtgraph)
    ↓
GUI 표시: 좌측 Stats+Tables | 우측 Charts
```

---

## 7. Spec 설정 체계

### 7.1 `spec_deviation` — PASS/FAIL 판정 + Trend Spec 라인

Die간 편차(Range, StdDev) 기준입니다. **키는 `recipe.short_name`과 정확히 일치**해야 합니다.

```json
"spec_deviation": {
    "Vision Pattern":  { "spec_range": 1.0, "spec_stddev": 0.2 },
    "In-Die Align":    { "spec_range": 2.0, "spec_stddev": 0.4 },
    "LLC Translation": { "spec_range": 4.0, "spec_stddev": 0.8 },
    "Global Align":    { "spec_range": 6.0, "spec_stddev": 1.2 }
}
```

**사용처:**
- **PASS/FAIL**: `overall_range ≤ spec_range AND overall_stddev ≤ spec_stddev`
- **Trend 차트**: Overall Mean ± `spec_range / 2` 로 Spec 라인 표시
- **카드 표시**: `value / spec ▲+N%` (초과=빨강) 또는 `✓N%` (여유=초록)

### 7.2 `spec_limits` — Cpk 계산용 LSL/USL

절대 오프셋 한계 (nm 단위)입니다.

```json
"spec_limits": {
    "Vision Pattern": { "X": {"lsl": -5000, "usl": 5000}, "Y": {"lsl": -5000, "usl": 5000} }
}
```

> **중요**: 키가 `short_name`과 불일치 시 경고 로그가 출력되며, 판정이 `—` (판정 불가)로 표시됩니다.

---

## 8. 데이터 필드 규칙

### `method` vs `axis`
CSV 로드 시 각 레코드에는 `method` 키가 할당됩니다. **`axis` 키는 사용하지 않습니다.**

```python
# 올바른 필터링
filter_by_method(data, 'X')   # r.get('method').upper() == 'X'

# ❌ 잘못된 사용
r.get('axis')                  # 존재하지 않음
```

---

## 9. 플러그인 아키텍처 & 메인 프로젝트 통합 전략

### 9.1 목표

이 프로젝트는 최종적으로 **메인 프로젝트(QC Check MES 등)의 플러그인**으로 통합되어야 합니다.

### 9.2 현재 구조의 플러그인 적합성

| 모듈 | 독립성 | 통합 난이도 |
|---|---|---|
| `csv_loader.py` | ✅ 완전 독립 | 낮음 |
| `recipe_scanner.py` | ✅ 완전 독립 | 낮음 |
| `analyzer.py` | ✅ 완전 독립 | 낮음 |
| `visualizer.py / visualizer_pg.py` | ✅ plt 인스턴스 독립 | 낮음 |
| `settings.py / settings.json` | ⚠️ 파일 경로 하드코딩 | 중간 |
| `main.py` (GUI) | ❌ 단독 실행 전제 | 높음 — 위젯 추출 필요 |

### 9.3 플러그인 통합 로드맵

#### Phase P1: 위젯 분리
```
src/
├── main.py              → 앱 진입점 (단독 실행용)
├── xy_offset_plugin.py  → [NEW] 플러그인 진입점 (QWidget)
├── widgets/
│   ├── stat_card.py     → StatCard 위젯 추출
│   ├── nav_bar.py       → Step Navigation 바 추출
│   └── spec_dialog.py   → Spec 설정 다이얼로그 추출
```

#### Phase P2: 인터페이스 정의
```python
class XYOffsetPlugin(QWidget):
    """메인 앱에서 탭/도킹 패널로 삽입 가능한 플러그인 위젯."""
    
    # Signal: 분석 완료 시 결과 전달
    analysis_complete = Signal(dict)  # {recipe, pass_x, pass_y, stats}
    
    def load_data(self, folder: str) -> None: ...
    def get_results(self) -> list[dict]: ...
    def set_spec(self, spec_deviation: dict, spec_limits: dict) -> None: ...
```

#### Phase P3: 설정 통합
- `settings.json` → 메인 앱의 설정 관리 시스템으로 위임
- Spec 값을 메인 앱의 DB/Config에서 동적으로 주입

#### Phase P4: 데이터 연동
- CSV 로더 → 메인 앱의 데이터 파이프라인에서 데이터 전달
- 분석 결과 → 메인 앱의 대시보드/리포트에 통합

### 9.4 통합 시 유의사항

> **테마 통일**: 메인 프로젝트도 Catppuccin Mocha 테마를 사용해야 시각적 일관성 유지
> 
> **pyqtgraph 충돌**: 메인 앱이 Matplotlib만 사용 중이면 pyqtgraph 의존성 추가 필요
> 
> **QThread 관리**: 플러그인의 비동기 작업이 메인 앱의 이벤트 루프와 충돌하지 않도록 주의

---

## 10. 실행 방법

```bash
cd "c:\Users\Spare\Desktop\03. Program\97. XY Stage Positioning Offset Analysis\src"
python main.py
```

### 의존성 설치
```bash
pip install PySide6 numpy pandas scipy matplotlib openpyxl pyqtgraph PyOpenGL
```

---

## 11. 개발 히스토리

| Phase | 내용 | 상태 |
|---|---|---|
| 1~5 | 데이터 로딩, 분석 엔진, 시각화, tkinter GUI | ✅ |
| 6 | Multi-Recipe Dashboard | ✅ |
| 7 | Guided Workflow UI + Cpk/Spec | ✅ |
| 8 | 레이아웃 개편 + System Log + Vector Map + Affine | ✅ |
| 8b~8d | 히트맵, 드래그 복사, Contour 팝업, 텍스트 대비 | ✅ |
| **9** | **PySide6 마이그레이션 완료** | ✅ |
| 9.1 | pyqtgraph 인터랙티브 차트 (Lot Trend, 분포, 3D) | ✅ |
| 9.2 | X/Y 분리 아키텍처 (독립 축별 드리프트 감지) | ✅ |
| 9.3 | Spec 대비 카드 표기 + Spec 다이얼로그 + 하드코딩 제거 | ✅ |

---

*이 문서는 프로젝트의 현재 상태, 기술 스택 표준, 플러그인 통합 전략을 정리한 레퍼런스입니다.*
