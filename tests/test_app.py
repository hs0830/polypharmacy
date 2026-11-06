"""Streamlit AppTest: 실제 processed 데이터가 있을 때만 실행."""
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

from apphelpers import page_text  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "data/processed/products.csv").exists(), reason="processed 데이터 없음")


def run_app(selected):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.session_state["selected"] = selected
    at.run()
    return at


def test_empty_state_runs_without_exception():
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120).run()
    assert not at.exception


def test_real_dur_pair_is_reported_in_ui():
    import pandas as pd
    p = pd.read_csv(ROOT / "data/processed/products.csv", dtype=str, keep_default_na=False)
    a = p[p.INGR_KEY == "fluorouracil"].ITEM_NAME.iloc[0]
    b = p[p.INGR_KEY == "gimeracil+oteracil+tegafur"].ITEM_NAME.iloc[0]
    at = run_app([{"kind": "product", "value": a, "label": a}, {"kind": "product", "value": b, "label": b}])
    assert not at.exception
    text = page_text(at)
    assert "병용금기 발견" in text and 'class="pp-banner pp-lv-contraindicated"' in text  # 상단 배너
    assert "gimeracil" in text  # DUR 탭 카드의 성분 칩
    assert 'pp-stat-n">1</div><div class="pp-stat-l">DUR 병용금기' in text  # 통계 카드: DUR 병용금기 1건


def test_unresolved_drug_never_shown_as_safe():
    at = run_app([
        {"kind": "ingredient", "value": "warfarin", "label": "w"},
        {"kind": "product", "value": "존재하지않는약", "label": "x"},
    ])
    assert not at.exception
    text = page_text(at)
    assert "성분을 확인하지 못한" in text
    assert "pp-lv-none_found" not in text  # 확인 불가 약이 있으면 '발견 없음' 배너가 나오면 안 된다
