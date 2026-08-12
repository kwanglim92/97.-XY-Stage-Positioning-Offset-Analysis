"""
회귀 테스트 — 현장 오류 `could not convert string to float: '□'` 및 관련 견고성.

배경:
    실장비 데이터 스캔 시 요약 CSV의 MEAN/STDEV/MIN/MAX/RANGE 값 셀에 비수치 문자가
    하나 들어 있어 `csv_loader.parse_summary_csv`의 무방비 `float()`가 ValueError를 던졌고,
    Recipe/Lot 루프에 예외 경계가 없어 **Recipe 4개 전체 스캔이 실패**했다.
    화면에는 폰트 글리프가 없어 '□' 한 글자만 보여 원인 추적도 불가능했다.

각 테스트는 수정 전이라면 실패하고, 수정 후 통과하도록 작성되었다.
헤드리스(Qt 불필요) 코어 로직만 대상으로 한다.
"""
import logging
import os

import pytest

from core import csv_loader
from core import recipe_scanner


# ──────────────────────────────────────────────────────────────────────────
# 픽스처 헬퍼 — 실데이터(SmartScan)와 같은 구조의 최소 Lot 폴더를 만든다
# ──────────────────────────────────────────────────────────────────────────

X_UL_CSV = (
    "Lot ID,Lot4\r\n"
    "Recipe ID,03. XY Stage\\1. Vision Pattern Recognize\r\n"
    "Sample ID,Sample10\r\n"
    "\r\n"
    "\r\n"
    "Site ID,Site X,Site Y,Point No,X (um),Y (um),Method ID,State,Valid,"
    "HZ1_O (nm),HZ1_O_Valid\r\n"
    "0001_X000_Y000,0,0,1,4305.72,5726,X,COMPLETED,TRUE,2795.41,TRUE\r\n"
    "0002_X002_Y000,2,0,1,24305.72,5726,X,COMPLETED,TRUE,2888.183,TRUE\r\n"
)


def _summary_csv(mean_value: str = "2369.052") -> str:
    """요약 CSV 본문. mean_value에 비정상 문자를 넣어 현장 오류를 재현한다."""
    return (
        "Lot ID,Lot4\r\n"
        "Sample ID,Sample10\r\n"
        "\r\n"
        "X_UL\r\n"
        "ITEM,HZ1_O (nm),\r\n"
        f"MEAN,{mean_value},\r\n"
        "STDEV,1817.046,\r\n"
        "MIN,-3454.59,\r\n"
        "MAX,3210.449,\r\n"
        "RANGE,6665.039,\r\n"
        "\r\n"
        "Y_UL\r\n"
        "ITEM,HZ1_O (nm),\r\n"
        "MEAN,-467.641,\r\n"
        "STDEV,946.259,\r\n"
        "MIN,-4763.184,\r\n"
        "MAX,2.441,\r\n"
        "RANGE,4765.625,\r\n"
    )


def _write_csv(path, text: str, encoding: str = "utf-8"):
    """실장비 파일과 동일한 바이트로 기록한다.

    write_text()는 Windows에서 '\\n'을 '\\r\\n'으로 변환해 CRLF 원문을 '\\r\\r\\n'으로
    망가뜨린다. 픽스처가 실데이터와 달라지면 테스트가 의미를 잃으므로 바이트로 쓴다.
    """
    path.write_bytes(text.encode(encoding))


def _make_lot(lot_dir, mean_value: str = "2369.052"):
    """Sample 폴더 하나를 만든다 (X_UL 실측 CSV + 요약 CSV)."""
    lot_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(lot_dir / "Sample10_X_UL.csv", X_UL_CSV)
    _write_csv(lot_dir / "Sample10.csv", _summary_csv(mean_value))
    return lot_dir


# ──────────────────────────────────────────────────────────────────────────
# 원 버그 고정 — 요약 값 셀의 비수치 문자가 예외를 던지면 안 된다
# ──────────────────────────────────────────────────────────────────────────
class TestSummaryValueRobustness:
    # 실데이터 접근이 불가해 '□'의 정체를 확정하지 못했으므로, 원인 분석에서 세운
    # 4가지 가설(H1~H4)을 모두 커버한다. 어느 쪽이 실제였든 통과해야 한다.
    @pytest.mark.parametrize("bad,codepoint", [
        ("﻿", "U+FEFF"),  # H4: 제로폭 — str.strip()이 제거하지 않는다
        ("\x8f", "U+008F"),    # H2: latin-1 폴백이 만든 C1 제어문자
        ("�", "U+FFFD"),  # H3: 이미 깨진 채 기록된 치환 문자
        ("－", "U+FF0D"),  # H1: 장비 SW의 전각 플레이스홀더 '－'
    ])
    def test_bad_value_does_not_raise(self, tmp_path, bad, codepoint):
        p = tmp_path / "Sample10.csv"
        _write_csv(p, _summary_csv(bad))

        result = csv_loader.parse_summary_csv(str(p))  # 수정 전: ValueError

        assert result["x_summary"]["mean"] == 0.0
        # 나머지 값은 정상 파싱되어야 한다 (한 셀 때문에 섹션 전체를 버리지 않는다)
        assert result["x_summary"]["stdev"] == pytest.approx(1817.046)
        assert result["y_summary"]["mean"] == pytest.approx(-467.641)

    @pytest.mark.parametrize("bad,codepoint", [
        ("﻿", "U+FEFF"),
        ("\x8f", "U+008F"),
        ("�", "U+FFFD"),
        ("－", "U+FF0D"),
    ])
    def test_bad_value_is_reported_with_codepoint(self, tmp_path, bad, codepoint):
        """0.0으로 조용히 삼키면 안 된다 — 어떤 문자였는지 식별 가능해야 한다.

        계측 SW이므로 '실제 측정값 0'과 '파싱 실패로 0 대체'는 반드시 구분돼야 하고,
        화면에 '□'로만 보이는 문자도 로그에서는 코드포인트로 특정할 수 있어야 한다.
        """
        p = tmp_path / "Sample10.csv"
        _write_csv(p, _summary_csv(bad))

        result = csv_loader.parse_summary_csv(str(p))

        assert len(result["warnings"]) == 1
        warning = result["warnings"][0]
        assert codepoint in warning
        assert "MEAN" in warning
        assert "Sample10.csv" in warning

    def test_valid_summary_still_parsed(self, tmp_path):
        """방어 로직 추가가 정상 데이터 해석을 바꾸지 않아야 한다."""
        p = tmp_path / "Sample10.csv"
        _write_csv(p, _summary_csv())

        result = csv_loader.parse_summary_csv(str(p))

        assert result["x_summary"] == {
            "mean": pytest.approx(2369.052),
            "stdev": pytest.approx(1817.046),
            "min": pytest.approx(-3454.59),
            "max": pytest.approx(3210.449),
            "range": pytest.approx(6665.039),
        }
        assert result["y_summary"]["range"] == pytest.approx(4765.625)
        assert result["warnings"] == []

    def test_empty_value_is_not_a_warning(self, tmp_path):
        """빈 셀은 원래부터 0.0으로 처리되던 정상 경로 — 경고 대상이 아니다."""
        p = tmp_path / "Sample10.csv"
        _write_csv(p, _summary_csv(""))

        result = csv_loader.parse_summary_csv(str(p))

        assert result["x_summary"]["mean"] == 0.0
        assert result["warnings"] == []


# ──────────────────────────────────────────────────────────────────────────
# 오류 격리 — 파일 하나의 문제가 전체 스캔을 무효화하면 안 된다
# ──────────────────────────────────────────────────────────────────────────
class TestLoadIsolation:
    def test_batch_load_survives_corrupt_summary(self, tmp_path):
        """현장 시나리오 그대로: 한 Lot의 요약 CSV가 깨져도 전 Lot 데이터가 나와야 한다."""
        root = tmp_path / "1st"
        _make_lot(root / "Sample1002", mean_value="﻿")
        _make_lot(root / "Sample1003")

        rows = csv_loader.batch_load(str(root))  # 수정 전: ValueError로 전체 실패

        assert len(rows) == 4  # 2 Lot × 2 site
        assert {r["lot_name"] for r in rows} == {"Sample1002", "Sample1003"}

    def test_batch_load_skips_failing_lot_and_reports(self, tmp_path, monkeypatch):
        """Lot 로드가 실제로 예외를 던져도(권한/네트워크 등) 나머지 Lot은 살아야 한다."""
        root = tmp_path / "1st"
        _make_lot(root / "Sample1002")
        _make_lot(root / "Sample1003")

        real_load = csv_loader.load_lot_data

        def flaky(lot_path):
            if os.path.basename(lot_path) == "Sample1002":
                raise OSError("simulated network failure")
            return real_load(lot_path)

        monkeypatch.setattr(csv_loader, "load_lot_data", flaky)

        errors = []
        rows = csv_loader.batch_load(str(root), errors=errors)

        assert len(rows) == 2
        assert {r["lot_name"] for r in rows} == {"Sample1003"}
        assert len(errors) == 1
        assert "Sample1002" in errors[0]

    def test_load_all_recipes_isolates_failing_recipe(self, tmp_path, monkeypatch):
        """한 Recipe가 실패해도 나머지 Recipe 분석 결과는 반환돼야 한다."""
        root = tmp_path / "data"
        _make_lot(root / "1. Vision Pattern" / "1st" / "Sample1002")
        _make_lot(root / "2. In-Die Align" / "1st" / "Sample1002")

        real_load = recipe_scanner.load_recipe_data

        def flaky(recipe, **kwargs):
            if recipe["name"].startswith("1."):
                raise RuntimeError("simulated recipe failure")
            return real_load(recipe, **kwargs)

        monkeypatch.setattr(recipe_scanner, "load_recipe_data", flaky)

        results = recipe_scanner.load_all_recipes(str(root))

        assert len(results) == 2
        failed = [r for r in results if r.get("error")]
        ok = [r for r in results if not r.get("error")]
        assert len(failed) == 1
        assert "simulated recipe failure" in failed[0]["error"]
        assert len(ok) == 1 and ok[0]["raw_data"]


# ──────────────────────────────────────────────────────────────────────────
# 인코딩 — 조용한 mojibake / 파싱 예외 누출 방지
# ──────────────────────────────────────────────────────────────────────────
class TestEncodingHandling:
    def test_cp949_korean_meta_is_parsed(self, tmp_path):
        """사내 장비가 쓰는 cp949 한글 메타가 정상 복원돼야 한다."""
        p = tmp_path / "Sample10_X_UL.csv"
        p.write_bytes(X_UL_CSV.replace("Lot4", "한글로트").encode("cp949"))

        parsed = csv_loader.parse_csv(str(p))

        assert parsed["meta"]["lot_id"] == "한글로트"
        assert len(parsed["data"]) == 2

    def test_latin1_fallback_warns_with_path(self, tmp_path, caplog):
        """latin-1은 어떤 바이트도 통과시키므로, 쓰였다면 반드시 경고가 남아야 한다."""
        p = tmp_path / "Sample10.csv"
        p.write_bytes(
            b"Lot ID,Lot4\r\n\r\nX_UL\r\nITEM,HZ1_O (nm),\r\nMEAN,\x80,\r\n")

        with caplog.at_level(logging.WARNING):
            result = csv_loader.parse_summary_csv(str(p))

        assert "인코딩 폴백" in caplog.text
        assert "Sample10.csv" in caplog.text
        # 폴백이 만든 C1 제어문자가 수치 파싱까지 흘러가도 죽지 않고 식별된다
        assert result["x_summary"]["mean"] == 0.0
        assert "U+0080" in result["warnings"][0]

    def test_utf16_file_does_not_raise(self, tmp_path, caplog):
        """UTF-16 파일은 latin-1 디코드 시 NUL을 남겨 csv.Error를 던지던 경로였다."""
        p = tmp_path / "Sample10_X_UL.csv"
        p.write_bytes(X_UL_CSV.encode("utf-16"))

        with caplog.at_level(logging.WARNING):
            parsed = csv_loader.parse_csv(str(p))  # 수정 전: csv.Error 누출

        assert parsed["data"] == []
        assert csv_loader._is_smartscan_csv(str(p)) is False
