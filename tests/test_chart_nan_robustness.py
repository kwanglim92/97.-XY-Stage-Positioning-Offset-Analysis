"""
회귀 테스트 — 현장 오류 `분포 X 차트 오류: autodetected range of [nan, nan] is not finite`.

배경:
    장비가 측정 실패 행을 `HZ1_O (nm)=NaN, Valid=FALSE`로 기록한다.
    CSV의 'NaN' 문자열은 float()이 그대로 받아들이므로 파싱 단계에서 걸리지 않고,
    NaN이 하나라도 섞이면 np.histogram/ax.hist의 범위 자동 감지가 통째로 실패한다.

    통계(compute_statistics)와 편차행렬(compute_deviation_matrix)은 Valid 플래그를
    거르지만 분포 차트만 거르지 않아, 차트만 깨졌다.

방어는 2겹이다:
    1겹 filter_valid_only — 측정 실패 행 제외 (다른 분석과 동일한 기준)
    2겹 drop_non_finite   — Valid=TRUE인 채 NaN이 오더라도 차트가 죽지 않게
"""
import logging
import math

import matplotlib
matplotlib.use("Agg")

import pytest

np = pytest.importorskip("numpy")

from core import drop_non_finite, filter_by_method, filter_valid_only
from charts.basic import plot_histogram


def _rows(values, valid=True, method="X"):
    """batch_load()가 만드는 행 구조의 최소 형태."""
    return [{"value": v, "valid": valid, "value_valid": valid, "method": method}
            for v in values]


# ──────────────────────────────────────────────────────────────────────────
# 전제 — NaN이 실제로 히스토그램을 깨뜨린다 (방어가 필요한 이유의 근거)
# ──────────────────────────────────────────────────────────────────────────
def test_numpy_histogram_really_fails_on_a_single_nan():
    """방어를 걷어내면 값 하나가 나머지 전부를 못 쓰게 만든다는 사실을 고정한다."""
    with pytest.raises(ValueError, match="is not finite"):
        np.histogram(np.array([1.0, 2.0, float("nan")]), bins=10)


# ──────────────────────────────────────────────────────────────────────────
# 2겹 — drop_non_finite
# ──────────────────────────────────────────────────────────────────────────
class TestDropNonFinite:
    def test_removes_nan_and_infinities(self):
        vals = [1.0, float("nan"), 2.0, float("inf"), -3.5, float("-inf")]
        assert drop_non_finite(vals) == [1.0, 2.0, -3.5]

    def test_keeps_finite_values_untouched(self):
        vals = [0.0, -1.5, 2.25, 1e300]
        assert drop_non_finite(vals) == vals

    def test_reports_how_many_were_dropped(self, caplog):
        """계측 SW이므로 조용히 버리면 안 된다 - 몇 개를 제외했는지 남아야 한다."""
        with caplog.at_level(logging.WARNING):
            drop_non_finite([1.0, float("nan"), float("nan")], "Vision Pattern X")
        assert "비유한 값 2개 제외" in caplog.text
        assert "Vision Pattern X" in caplog.text

    def test_silent_when_nothing_dropped(self, caplog):
        with caplog.at_level(logging.WARNING):
            drop_non_finite([1.0, 2.0], "ctx")
        assert caplog.text == ""

    def test_empty_input(self):
        assert drop_non_finite([]) == []


# ──────────────────────────────────────────────────────────────────────────
# 1겹 — 분포 차트가 통계와 같은 유효성 기준을 쓰는지
# ──────────────────────────────────────────────────────────────────────────
class TestValidityFilterMatchesStatistics:
    def test_invalid_rows_are_excluded(self):
        """실데이터에서 NaN 행은 항상 Valid=FALSE로 기록된다."""
        data = _rows([1.0, 2.0]) + _rows([float("nan")], valid=False)

        kept = filter_valid_only(filter_by_method(data, "X"))

        assert len(kept) == 2
        assert not any(math.isnan(r["value"]) for r in kept)

    def test_other_axis_is_not_mixed_in(self):
        data = _rows([1.0], method="X") + _rows([2.0], method="Y")
        assert len(filter_valid_only(filter_by_method(data, "X"))) == 1


# ──────────────────────────────────────────────────────────────────────────
# 통합 — 차트 함수가 NaN에도 죽지 않는다 (원 버그 고정)
# ──────────────────────────────────────────────────────────────────────────
class TestHistogramSurvivesNaN:
    def test_plot_histogram_with_nan_does_not_raise(self):
        """수정 전: ValueError - autodetected range of [nan, nan] is not finite."""
        data = _rows([1.0, 2.0, 3.0, 4.0]) + _rows([float("nan")], valid=False)
        fig = plot_histogram(data, title="NaN mixed")
        assert fig is not None

    def test_plot_histogram_all_nan_returns_empty_figure(self):
        """전부 NaN이어도 예외 없이 빈 figure를 돌려준다."""
        data = _rows([float("nan"), float("nan")], valid=False)
        fig = plot_histogram(data, title="all NaN")
        assert fig is not None

    def test_pyqtgraph_histogram_with_nan_does_not_raise(self):
        """실제로 현장에서 깨진 경로(pyqtgraph 위젯)."""
        pytest.importorskip("pyqtgraph")
        QtWidgets = pytest.importorskip("PySide6.QtWidgets")
        import os
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        if QtWidgets.QApplication.instance() is None:
            try:
                QtWidgets.QApplication([])
            except Exception:  # pragma: no cover - 헤드리스 환경에 Qt 플랫폼 없음
                pytest.skip("Qt 플랫폼 플러그인을 사용할 수 없음")

        from charts.interactive import create_histogram_widget
        data = _rows([1.0, 2.0, 3.0, 4.0]) + _rows([float("nan")], valid=False)
        assert create_histogram_widget(data, title="NaN mixed") is not None
