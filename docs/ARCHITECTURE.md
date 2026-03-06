# 🏗️ 아키텍처 참조 문서

> XY Stage Positioning Offset Analysis Tool — v9.x  
> 최종 업데이트: 2026-03-06

---

## 1. 프로젝트 구조

```
97. XY Stage Positioning Offset Analysis/
├── src/
│   ├── main.py               # GUI 메인 앱 (DataAnalyzerApp + GuideDialog, ~3000 줄)
│   ├── csv_loader.py         # Lot 폴더 탐색, CSV/TXT 배치 로드 + IQR 이상치 탐지
│   ├── recipe_scanner.py     # Recipe 디렉토리 구조 자동 탐지 + 트렌드 계산
│   ├── analyzer.py           # 통계 엔진 (Statistics, Cpk, Deviation Matrix, Affine)
│   ├── visualizer.py         # Matplotlib 정적 차트 (Contour, Vector, Scatter 등)
│   ├── visualizer_pg.py      # pyqtgraph 인터랙티브 차트 (Trend, 분포, 3D)
│   ├── sparkline_delegate.py # QPainter 기반 커스텀 테이블 셀 렌더러 (Sparkline)
│   ├── exporter.py           # CSV / Excel 내보내기
│   ├── pdf_generator.py      # PDF 리포트 생성 (matplotlib PDF 백엔드)
│   ├── tiff_loader.py        # PSPylib 전용 TIFF 바이너리 파서
│   ├── settings.py           # settings.json 로드/저장 유틸리티
│   └── settings.json         # 사용자 설정 (Spec, 창 위치, Recipe 이름 등)
├── docs/
│   ├── SUMMARY_TABLE_GUIDE.md  # Summary 테이블 컬럼 가이드
│   ├── TECH_STACK.md           # 기술 스택 정의
│   ├── ARCHITECTURE.md         # 아키텍처 참조 (이 문서)
│   └── DATA_ANALYSIS_GUIDE.md  # 데이터 해석 가이드 (엔지니어용)
├── data/                     # 실제 측정 데이터 (Recipe별 폴더 구조)
├── test/
├── .gitignore
└── PROJECT_SUMMARY.md        # 프로젝트 개요 (상위 레벨 레퍼런스)
```

---

## 2. 모듈 의존 관계

```
main.py
├── csv_loader.py       (load_lot_folder, batch_load_lots)
├── recipe_scanner.py   (scan_recipes, compute_trend)
├── analyzer.py         (compute_statistics, compute_cpk,
│                        compute_deviation_matrix, detect_outliers,
│                        compute_affine_transform, filter_by_method)
├── visualizer.py       (plot_contour_map, plot_vector_map,
│                        plot_xy_scatter, plot_boxplot 등)
├── visualizer_pg.py    (create_dual_trend_widget,
│                        create_distribution_widget,
│                        create_surface_3d_widget,
│                        create_tiff_widget)
├── sparkline_delegate.py (SparklineTrendDelegate)
├── exporter.py         (export_combined_csv, export_excel_report)
├── pdf_generator.py    (generate_pdf_report)
├── tiff_loader.py      (load_tiff_file)
└── settings.py         (load_settings, save_settings)
```

---

## 3. 데이터 흐름

```
[1] 폴더 선택
    └─ path_edit에 경로 입력
    └─ QThread: ScanWorker 비동기 실행

[2] 폴더 스캔 (ScanWorker)
    └─ recipe_scanner.scan_recipes(folder)
       → recipes[]: [{name, short_name, path, round_paths}, ...]
    └─ 폴더명 검증: short_name ↔ spec_deviation 키 대조
       → 불일치 시 QMessageBox.critical → 스캔 차단

[3] 데이터 로드 (ScanWorker)
    └─ csv_loader.batch_load_lots(recipe_path)
       → raw_data[]: [{lot_name, site_id, method, value, is_outlier, valid}, ...]

[4] 분석 (_on_scan_complete)
    └─ analyzer.filter_by_method(data, 'X') → x_data
    └─ analyzer.filter_by_method(data, 'Y') → y_data
    └─ analyzer.compute_statistics(x_data) → {mean, stdev, min, max, cv_percent, count}
    └─ analyzer.compute_deviation_matrix(data, 'X') → {matrix, overall_range, overall_stddev}
    └─ analyzer.compute_cpk(mean, stdev, lsl, usl) → float
    └─ PASS/FAIL: overall_range ≤ spec_range AND overall_stddev ≤ spec_stddev

[5] UI 업데이트
    ├─ StatCard.update_stats()    — X/Y 카드 수치 갱신
    ├─ _update_summary_table()    — Summary 테이블 갱신
    ├─ _update_die_avg_tables()   — Die 히트맵 갱신
    ├─ _update_deviation_tables() — Raw Deviation 매트릭스 갱신
    └─ _display_charts()          — Matplotlib + pyqtgraph 차트 렌더링

[6] Export (선택)
    ├─ exporter.export_excel_report() → .xlsx
    ├─ exporter.export_combined_csv() → .csv
    └─ pdf_generator.generate_pdf_report() → .pdf
```

---

## 4. UI 레이아웃 구조

```
DataAnalyzerApp (QMainWindow)
│
├─ TopBar (QHBoxLayout)
│   ├─ path_edit (QLineEdit)
│   ├─ btn_browse "Open"
│   └─ btn_scan "🔄 Scan & Analysis"
│
├─ Workflow Nav (QHBoxLayout)
│   └─ step_buttons[]: QPushButton (Recipe별 — PASS🟢/FAIL🔴 표시)
│
└─ QSplitter (Horizontal, 5:5)
    ├─ LEFT PANEL
    │   ├─ StatCard (X)  — Mean, Range, StdDev, Cpk, PASS/FAIL
    │   ├─ StatCard (Y)  — 동일 구조
    │   ├─ btn_spec_config "⚙️ Spec 설정"
    │   ├─ QTabWidget
    │   │   ├─ "시스템 로그" — SystemLog (QTextEdit)
    │   │   └─ "데이터 테이블" — QTabWidget
    │   │       ├─ "Summary"     — CopyableTable
    │   │       ├─ "Die별 평균"  — CopyableTable (X/Y 서브탭)
    │   │       ├─ "Raw Deviation" — CopyableTable (X/Y 서브탭)
    │   │       └─ "원본 데이터" — CopyableTable
    │   └─ Die Filter Panel
    │       ├─ toggle 버튼 (접기/펼치기)
    │       ├─ 전체 선택 / 안정화 Die 제외
    │       └─ Die 체크박스 목록 (Die 1~22)
    │
    └─ RIGHT PANEL (QTabWidget — chart_category_tabs)
        ├─ "기본 분석"
        │   ├─ "Contour X / Y"
        │   ├─ "Die Position Map"
        │   └─ "Vector Map"
        ├─ "인터랙티브"
        │   ├─ "🎯 XY Scatter" + 사이드 범례 패널
        │   ├─ "📈 Lot Trend"  + Lot 필터
        │   ├─ "📊 분포 X/Y"
        │   └─ "🔬 TIFF"
        ├─ "고급 분석"
        │   ├─ "🔍 Pareto"
        │   ├─ "🔗 Correlation"
        │   └─ "🌐 3D Surface X/Y"
        ├─ "비교"
        │   ├─ "📊 Boxplot"
        │   ├─ "📈 Trend"
        │   └─ "🗺️ Heatmap"
        └─ "📤 Export"
            └─ "내보내기"
                ├─ 분석 가이드 보기 버튼 → GuideDialog
                ├─ Excel 내보내기
                ├─ CSV 내보내기
                └─ PDF 보고서
```

---

## 5. 주요 클래스 및 컴포넌트

| 클래스/컴포넌트 | 위치 | 역할 |
|----------------|------|------|
| `DataAnalyzerApp` | `main.py` | 앱 메인 창 (QMainWindow 상속) |
| `GuideDialog` | `main.py` | 분석 가이드 도움말 팝업 (QDialog) |
| `StatCard` | `main.py` | X/Y 통계 카드 위젯 (QFrame) |
| `CopyableTable` | `main.py` | 드래그 선택 + Ctrl+C 복사 지원 테이블 |
| `ScanWorker` | `main.py` | 비동기 스캔 스레드 (QThread) |
| `ChartWidget` | `main.py` | Matplotlib Figure 임베드 위젯 |
| `InteractiveChartWidget` | `main.py` | pyqtgraph 차트 임베드 위젯 |
| `SparklineTrendDelegate` | `sparkline_delegate.py` | 테이블 셀 내 미니 라인 차트 렌더러 |

---

## 6. 데이터 필드 규칙

### 6.1 `raw_data` 레코드 구조

```python
{
    "lot_name":   str,   # Lot 폴더 이름 (예: "Lot001")
    "site_id":    str,   # Die 위치 ID (예: "Die_1")
    "method":     str,   # "X" 또는 "Y" — 축 구분 (필드명 주의!)
    "value":      float, # HZ1_O 측정값 (nm)
    "is_outlier": bool,  # IQR 기반 이상치 여부
    "valid":      bool,  # 유효 데이터 여부
}
```

> ⚠️ **주의**: `axis` 키는 사용하지 않음. 반드시 `method` 키로 X/Y 필터링.
> ```python
> # 올바른 필터링
> filter_by_method(data, 'X')   # method.upper() == 'X'
> ```

### 6.2 `recipe` 구조

```python
{
    "name":       str,   # 원본 폴더 이름 (예: "1. Vision Pattern Recognize")
    "short_name": str,   # 정규화된 이름 (예: "Vision Pattern")
    "path":       str,   # 절대 경로
    "round_paths": dict, # {"1st": path1, "2nd": path2, ...}
}
```

---

## 7. Spec 검증 로직

```python
# 폴더명 검증 (scan 시점)
for recipe in recipes:
    short = recipe['short_name'].strip().lower()
    matched = any(short == key.strip().lower() for key in spec_deviation.keys())
    if not matched:
        mismatched.append(recipe['name'])

if mismatched:
    QMessageBox.critical(...)  # 분석 차단
    return

# PASS/FAIL 판정 (분석 시점)
pass_x = (dev_x.overall_range <= spec_range) and (dev_x.overall_stddev <= spec_stddev)
pass_y = (dev_y.overall_range <= spec_range) and (dev_y.overall_stddev <= spec_stddev)
overall = pass_x and pass_y
```

---

## 8. 성능 및 비동기 처리

| 작업 | 처리 방식 | 이유 |
|------|-----------|------|
| 폴더 스캔 + 데이터 로드 | `QThread (ScanWorker)` | UI 블로킹 방지 — CSV 파일 수백 개 |
| PDF 생성 | `threading.Thread` | Matplotlib PDF 생성 시간 소요 |
| 차트 렌더링 | 메인 스레드 | Qt 위젯은 메인 스레드에서만 접근 가능 |
| 결과 UI 업데이트 | `QTimer.singleShot(0, ...)` | 스레드 → 메인 스레드 안전한 UI 업데이트 |

---

## 9. 개발 히스토리 요약

| 버전 | 주요 변경 사항 |
|------|---------------|
| v1~5 | 데이터 로딩, 분석 엔진, 시각화, tkinter GUI 초기 개발 |
| v6 | Multi-Recipe Dashboard |
| v7 | Guided Workflow UI + Cpk/Spec 판정 |
| v8 | 레이아웃 개편, System Log, Vector Map, Affine Transform |
| v8b~d | 히트맵, 드래그 복사, Contour 팝업, 텍스트 대비 개선 |
| **v9** | **PySide6 마이그레이션 완료** |
| v9.1 | pyqtgraph 인터랙티브 차트 (Lot Trend, 분포, 3D) |
| v9.2 | X/Y 분리 아키텍처 (독립 축별 드리프트 감지) |
| v9.3 | Spec 대비 카드 + Spec 다이얼로그 + 하드코딩 제거 |
| v9.4 | Die 필터 토글 + XY Scatter 범례 패널 + Log Scale |
| v9.5 | 폴더명 엄격 검증 + 테이블 가운데 정렬 + 분석 가이드 Dialog |
