"""
회귀 테스트 — 측정 실패 행(NaN)이 코어 분석을 오염시키던 결함.

배경:
    장비는 정렬/패턴인식에 실패한 측정을 `HZ1_O (nm)=NaN, Valid=FALSE`로 기록한다.
    NaN은 모든 비교 연산이 False라 sorted()의 순서를 망가뜨린다. 그 결과
    detect_outliers의 사분위수가 엉뚱한 위치로 가서, 현장 데이터에서

        Global Align    이상치 129건 (실제 0건)   ← 거짓 양성
        Vision Pattern  이상치   0건 (실제 134건) ← 거짓 음성

    처럼 **양방향으로** 틀린 값이 나왔다. 계측 SW에서 이상치 개수가 틀리는 것은
    차트가 깨지는 것보다 위험하다 — 틀린 줄 모르고 그대로 보고되기 때문이다.

    또한 요약 CSV의 비정상 값 경고가 Python logging(stderr)으로만 나가서,
    콘솔이 없는 windowed EXE에서는 현장에서 볼 수 없었다.
"""
import math
import random

import pytest

from core.statistics import detect_outliers
from core.recipe_scanner import summarize_failed_measurements


NAN = float("nan")


def _row(value, valid=True, lot="Lot1", site="0001_X000_Y000", method="X"):
    return {"value": value, "valid": valid, "value_valid": valid,
            "lot_name": lot, "site_id": site, "method": method}


def _rows(values):
    """NaN은 장비가 그렇게 하듯 Valid=FALSE로 표시한다."""
    return [_row(v, valid=not (isinstance(v, float) and math.isnan(v)))
            for v in values]


def _outlier_count(values):
    return sum(1 for r in detect_outliers(_rows(values), method="iqr")
               if r["is_outlier"])


# ──────────────────────────────────────────────────────────────────────────
# detect_outliers — NaN이 기준 계산과 판정을 모두 오염시키면 안 된다
# ──────────────────────────────────────────────────────────────────────────
class TestDetectOutliersIgnoresFailedMeasurements:
    def test_nan_row_is_never_an_outlier(self):
        """측정 실패는 '이상치'가 아니라 '결측'이다."""
        data = [_row(float(v)) for v in range(20)] + [_row(NAN, valid=False)]

        marked = detect_outliers(data, method="iqr")

        nan_row = marked[-1]
        assert nan_row["is_outlier"] is False

    def test_result_is_independent_of_nan_position(self):
        """NaN을 어느 위치에 끼워 넣어도 유효 데이터의 판정은 같아야 한다.

        수정 전에는 정렬 시 NaN이 사분위 인덱스(3n//4)에 앉으면 경계가 nan이 되어
        모든 비교가 False가 됐다 → 이상치 0건.
        현장에서 Vision Pattern의 진짜 이상치 134건이 0건으로 보고된 원인이다.
        (이 데이터에서는 NaN 위치 16에서 재현된다)
        """
        base = [float(v) for v in range(20)] + [100000.0]   # 명백한 이상치 1건
        expected = _outlier_count(base)
        assert expected == 1, "전제: NaN이 없으면 이상치는 1건"

        for pos in range(len(base) + 1):
            polluted = base[:pos] + [NAN] + base[pos:]
            assert _outlier_count(polluted) == expected, f"NaN 위치 {pos}에서 판정이 바뀜"

    def test_no_false_positives_on_tight_distribution(self):
        """좁게 모인 실측 분포에 NaN이 섞여도 정상값이 이상치가 되면 안 된다.

        수정 전에는 NaN이 정렬을 교란해 사분위수가 실제보다 훨씬 좁게 잡혔고,
        경계 안쪽의 정상값들이 무더기로 이상치가 됐다.
        현장에서 Global Align 129건, LLC Translation 200건이 거짓 양성이었다.
        (아래 구성은 수정 전 16건 vs 실제 1건으로 재현된다)
        """
        rnd = random.Random(40)
        values = [rnd.gauss(1000, 50) for _ in range(40)]
        expected = _outlier_count(values)

        polluted = list(values)
        for i in (4, 10, 37):
            polluted.insert(i, NAN)

        assert _outlier_count(polluted) == expected

    def test_zscore_method_also_guarded(self):
        data = [_row(float(v)) for v in range(20)] + [_row(NAN, valid=False)]
        marked = detect_outliers(data, method="zscore", threshold=3)
        assert marked[-1]["is_outlier"] is False

    def test_all_values_failed(self):
        """전부 실패한 경우에도 예외 없이 모두 False."""
        data = [_row(NAN, valid=False) for _ in range(5)]
        marked = detect_outliers(data, method="iqr")
        assert all(r["is_outlier"] is False for r in marked)

    def test_clean_data_is_unaffected(self):
        """정상 데이터만 있으면 기존 동작과 동일해야 한다 (회귀 방지)."""
        data = [_row(float(v)) for v in range(20)] + [_row(99999.0)]
        marked = detect_outliers(data, method="iqr")
        assert sum(1 for r in marked if r["is_outlier"]) == 1


# ──────────────────────────────────────────────────────────────────────────
# 어떤 데이터가 실제로 문제인지 구별할 수 있어야 한다
# ──────────────────────────────────────────────────────────────────────────
class TestSummarizeFailedMeasurements:
    def test_no_failures(self):
        assert summarize_failed_measurements(
            [_row(1.0), _row(2.0)]) == {"count": 0}

    def test_counts_and_groups_by_lot_and_die(self):
        data = [
            _row(1.0),
            _row(NAN, valid=False, lot="Lot508", site="0009_X000_Y004"),
            _row(NAN, valid=False, lot="Lot508", site="0009_X000_Y004"),
            _row(NAN, valid=False, lot="Lot61", site="0010_X000_Y006"),
        ]

        s = summarize_failed_measurements(data)

        assert s["count"] == 3
        assert s["by_lot"][0] == ("Lot508", 2)
        assert s["by_site"][0] == ("0009_X000_Y004", 2)
        assert "측정 실패 3건" in s["text"]
        assert "Lot508" in s["text"] and "0009_X000_Y004" in s["text"]

    def test_catches_non_finite_even_when_flagged_valid(self):
        """Valid=TRUE인데 값만 NaN인 장비/버전도 놓치지 않는다."""
        s = summarize_failed_measurements([_row(1.0), _row(NAN, valid=True)])
        assert s["count"] == 1

    def test_catches_invalid_even_when_value_is_finite(self):
        s = summarize_failed_measurements([_row(1.0), _row(2.0, valid=False)])
        assert s["count"] == 1


# ──────────────────────────────────────────────────────────────────────────
# 경고가 UI까지 전달되는가 (stderr에만 남으면 EXE에서 볼 수 없다)
# ──────────────────────────────────────────────────────────────────────────
class TestWarningsReachTheCaller:
    def test_batch_load_propagates_summary_warnings(self, tmp_path):
        from test_csv_loader_robustness import _make_lot

        root = tmp_path / "1st"
        _make_lot(root / "Lot1204", mean_value="�")   # 현장에서 확인된 문자
        _make_lot(root / "Lot1205")

        from core.csv_loader import batch_load
        warnings = []
        rows = batch_load(str(root), warnings=warnings)

        assert len(rows) == 4                     # 데이터는 정상 로드
        assert len(warnings) == 1                 # 손상된 Lot 하나만 경고
        assert "Lot1204" in warnings[0]
        assert "U+FFFD" in warnings[0]

    def test_load_recipe_data_exposes_quality_info(self, tmp_path):
        from test_csv_loader_robustness import _make_lot
        from core.recipe_scanner import scan_recipes, load_recipe_data

        root = tmp_path / "data"
        _make_lot(root / "Vision Pattern" / "1st" / "Lot501", mean_value="�")

        recipe = scan_recipes(str(root))[0]
        result = load_recipe_data(recipe, round_name="1st")

        assert result["data_warnings"], "요약 CSV 경고가 UI까지 전달돼야 한다"
        assert "U+FFFD" in result["data_warnings"][0]
        assert "failed_measurements" in result
