import pandas as pd

from src.verify import verify
from test_engine import store  # noqa: F401  (합성 데이터 픽스처 재사용)


def test_verify_counts_detected_missed_and_not_in_list(store):
    dur = pd.DataFrame({
        "제품명A": ["엑스정_(10mg)", "없는약_(1mg)", "제트정_(1)"],
        "제품명B": ["와이정_(5mg)", "와이정_(5mg)", "와이정_(5mg)"],
        "성분명A": ["drug-x", "none", "drug-z"], "성분명B": ["drug-y"] * 3,
        "금기사유": ["사유1", "사유2", "사유3"],
    })
    res = verify(store, dur, sample=10)
    assert res["stats"] == {"detected": 1, "not_in_list": 1, "missed": 1}
    assert res["checked"] == 2 and res["recall"] == 0.5
    assert res["failures"][0]["제품명A"] == "제트정_(1)"  # 제트정×와이정 은 DUR 에 없음 -> 실패 목록에 기록


def test_find_by_dur_name_strips_strength_and_ignores_parens(store):
    assert store.find_by_dur_name("엑스정_(10mg)").label == "엑스정"
    assert store.find_by_dur_name("없는약_(1mg)") is None
