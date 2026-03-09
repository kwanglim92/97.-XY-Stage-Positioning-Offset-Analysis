# 🏁 최종 마이그레이션 완료 보고서

> **프로젝트**: XY Stage Positioning Offset Analysis  
> **버전**: v10.0 (Mixin 기반 모듈 아키텍처)  
> **보고서 작성일**: 2026-03-09  
> **기준 커밋**: `25d31e1` — feat(Vector Map): Add colorbar + Show Values toggle

---

## 1. 마이그레이션 개요

### Before (모놀리식 구조)
```
main.py          ← 3,000줄+, UI·로직·차트 모두 혼재
visualizer.py    ← matplotlib 차트 전용 분리 (불완전)
```

### After (모듈화 구조)
```
src/
├── core/           (8개 파일) — 순수 데이터 처리, UI 무관
├── charts/         (6개 파일) — 차트 생성만 담당
├── ui/
│   ├── controllers/ (10개 Mixin 파일) — 기능별 UI 제어
│   ├── widgets/     (5개 파일) — 재사용 UI 부품
│   ├── dialogs/     (3개 파일) — 팝업 창
│   └── workers/     (1개 파일) — 백그라운드 스레드
└── main.py         ← 조립만 담당 (~150줄)
```

---

## 2. 발견 및 수정된 버그 목록

| # | 에러 유형 | 파일 | 원인 | 수정 내용 |
|---|-----------|------|------|-----------|
| 1 | `NameError: QFont` | `charts/interactive_widgets.py` | 분리 시 import 누락 | `from PySide6.QtGui import QFont` 추가 |
| 2 | `NameError: QFont` | `charts/interactive.py` | 동일 | `from PySide6.QtGui import QFont` 추가 |
| 3 | `ImportError: _color_from_die` | `ui/controllers/step_controller.py` | `charts` 패키지 레벨에 미노출 | `from charts.wafer import _color_from_die`로 수정 |
| 4 | `ImportError: _DIE_COLORS` | `ui/controllers/xy_legend_controller.py` | 동일 | `from charts.interactive import _DIE_COLORS`로 수정 |
| 5 | `NameError: viz` | `ui/controllers/scan_controller.py` | import 누락 | `import charts as viz` 추가 |
| 6 | `NameError: _extract_site_data` | `charts/comparison.py` | `basic.py`에서 미import | `from charts.basic import _extract_site_data` 추가 |
| 7 | `NameError: _style_axis` | `charts/interactive_widgets.py` | `interactive.py` 내부 함수를 외부에서 사용 | `_style_axis`, `_make_pen` 로컬 정의 추가 |
| 8 | `NameError: GuideDialog` | `ui/controllers/ui_builder_mixin.py` | import 누락 | `_show_guide_dialog` 내 lazy import 추가 |
| 9 | Vector Map "No data" | `charts/wafer.py` | `extract_die_number("Die5")→None` (형식 불일치) | `die_stats['die']`를 직접 `get_die_position`에 전달하도록 수정 |

---

## 3. 신규 기능 추가

### Vector Map 개선
| 기능 | 설명 |
|------|------|
| **Colorbar** | 화살표 색상(편차 크기 µm) 해석을 위한 컬러바 상시 표시 |
| **"📐 Show Values" 토글** | 클릭 시 각 화살표 시작점에 `0.15µm` 형식으로 편차 크기 레이블 표시 |
| **레이블 위치** | 화살표 끝점(겹침 발생) → 시작점(Die 위치) 고정으로 변경 |

---

## 4. 레거시 파일 정리

### 삭제된 파일

| 파일 | 이유 |
|------|------|
| `src/_test_icons.py` | 아이콘 렌더링 일회성 테스트 스크립트. 기능 구현 완료 후 불필요 |
| `src/sparkline_delegate.py` | Summary 테이블 Spec 게이지 바 위젯. UI 개선 과정에서 제거된 기능으로 어디서도 import하지 않음 |

### 보존된 파일 (사용 중 확인)

| 파일 | 사용처 | 이유 |
|------|--------|------|
| `ui/color_helpers.py` | `ui/controllers/table_controller.py` | 히트맵 셀 배경색 계산에 실사용 중 |

---

## 5. 현재 미커밋 변경사항

> **사용자가 커밋 요청 시 처리할 내용**

| 파일 | 변경 내용 |
|------|-----------|
| `src/charts/wafer.py` | Vector Map 값 레이블 위치를 화살표 끝점 → 시작점으로 수정 |
| `src/main.py` | 불필요한 빈 줄 제거 (사용자 직접 편집) |
| `src/_test_icons.py` | 삭제 |
| `src/sparkline_delegate.py` | 삭제 |

---

## 6. 현재 모듈 구조 최종 현황

```
src/ (총 44개 .py 파일)
│
├── main.py                          ← 앱 진입점, 조립만
│
├── core/                            ← 🧠 분석 엔진
│   ├── statistics.py                ← 통계 계산 (Cpk, IQR, 상관관계 등)
│   ├── die_analysis.py              ← Die 편차 행렬, Affine Transform
│   ├── csv_loader.py                ← CSV 파싱 및 폴더 스캔
│   ├── recipe_scanner.py            ← Recipe별 데이터 로드 전략
│   ├── tiff_loader.py               ← TIFF 파일 파싱
│   ├── exporter.py                  ← Excel/CSV 내보내기
│   ├── pdf_generator.py             ← PDF 보고서 생성
│   └── settings.py                  ← 설정 load/save
│
├── charts/                          ← 📊 차트 생성기
│   ├── interactive.py               ← pyqtgraph 인터랙티브 차트 함수
│   ├── interactive_widgets.py       ← CrossHair, HoverScatter, TiffViewer 위젯
│   ├── wafer.py                     ← Contour, Vector Map, Die Position (matplotlib)
│   ├── basic.py                     ← Boxplot, Trend (matplotlib)
│   ├── comparison.py                ← Recipe 비교 차트 (matplotlib)
│   └── surface3d.py                 ← 3D Surface (OpenGL)
│
└── ui/
    ├── theme.py                     ← 색상 상수 (Catppuccin Mocha)
    ├── color_helpers.py             ← 히트맵 색상 유틸
    ├── controllers/                 ← 🎮 Mixin 기반 UI 제어
    │   ├── ui_builder_mixin.py      ← 전체 레이아웃 구성
    │   ├── chart_controller.py      ← 차트 갱신
    │   ├── step_controller.py       ← 분석 결과 표시
    │   ├── scan_controller.py       ← 폴더 스캔·로드
    │   ├── table_controller.py      ← 데이터 테이블 갱신
    │   ├── card_controller.py       ← StatCard 갱신
    │   ├── die_filter_controller.py ← Die 필터 체크박스
    │   ├── lot_filter_controller.py ← Lot 필터
    │   ├── xy_legend_controller.py  ← XY 범례
    │   ├── tiff_controller.py       ← TIFF 뷰어 제어
    │   └── export_controller.py     ← 내보내기 처리
    ├── widgets/                     ← 🧩 재사용 UI 부품
    │   ├── chart_widget.py          ← matplotlib/pyqtgraph 컨테이너
    │   ├── stat_card.py             ← KPI 카드
    │   ├── copyable_table.py        ← Ctrl+C 복사 가능 테이블
    │   ├── flow_layout.py           ← 자동 줄바꿈 레이아웃
    │   └── system_logger.py         ← 로그 패널
    ├── dialogs/
    │   ├── guide_dialog.py          ← Analysis Guide 팝업
    │   ├── spec_config_dialog.py    ← Spec 설정 팝업
    │   └── repeat_contour_dialog.py ← Repeat 비교 팝업
    └── workers/
        └── data_loader_thread.py    ← 백그라운드 파일 로더
```

---

## 7. 아키텍처 품질 평가

| 항목 | 평가 | 비고 |
|------|------|------|
| 모듈 분리 | ✅ 완료 | core / charts / ui 3계층 명확 |
| 단방향 의존성 | ✅ 준수 | core → UI 방향 import 없음 |
| Mixin 분리 | ✅ 완료 | 10개 Mixin으로 단일 책임 적용 |
| 재사용성 | ✅ 높음 | widgets / dialogs 독립 사용 가능 |
| `__init__.py` API 명시 | ⚠️ 부분 | `charts/__init__.py`가 `*` 전체 노출 — 다음 버전에서 명시적 노출 권장 |
| Smoke Test | ⚠️ 부재 | `tests/test_imports.py` 추가 권장 |
| 디버그 파일 | ✅ 정리 완료 | 모든 debug 스크립트 제거됨 |

---

## 8. 다음 버전 권장 개선사항

```python
# 권장: charts/__init__.py를 명시적 export로 변경
# (현재 from .basic import * 형태 → 아래처럼 명시화)
from .wafer import plot_wafer_contour, plot_vector_map, plot_die_position_map
from .basic import plot_boxplot, plot_trend_chart
from .interactive import create_trend_widget, create_scatter_widget
# _color_from_die 같은 private 함수는 노출 제외
```

```python
# 권장: tests/test_imports.py 추가 (신규 개발 시 즉시 오류 감지)
import core
import charts
from ui.widgets import chart_widget, stat_card
from ui.controllers import chart_controller, scan_controller
print("✅ All imports OK")
```

---

> **결론**: 마이그레이션 완료. 9개 버그 수정, 2개 레거시 파일 제거, Vector Map 기능 3개 개선.  
> 전체 44개 파일이 3계층 의존성 규칙을 준수하는 모듈 구조로 정돈되었습니다.
