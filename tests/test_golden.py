"""알려진 병용금기 조합이 데이터 갱신 후에도 잡히는지 확인 (processed 데이터가 있을 때만 실행)."""
import csv
from pathlib import Path

import pytest

from src.engine import analyze
from src.store import DataStore

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "data/processed/dur_pairs.csv").exists(), reason="processed 데이터 없음")


@pytest.fixture(scope="module")
def store():
    return DataStore(ROOT / "data/processed")


def golden():
    with open(Path(__file__).with_name("golden_ingredient_pairs.csv"), encoding="utf-8") as f:
        return [(r["a"], r["b"], r["memo"]) for r in csv.DictReader(f)]


@pytest.mark.parametrize("a,b,memo", golden())
def test_known_pair_is_detected_in_both_orders(store, a, b, memo):
    for x, y in ((a, b), (b, a)):
        r = analyze(store, [store.resolve_ingredient(x), store.resolve_ingredient(y)])
        assert r.count("dur") >= 1, f"{a} × {b} ({memo}) 가 잡히지 않음 — 데이터/정규화 규칙을 확인하세요"
        assert r.overall == "contraindicated"
