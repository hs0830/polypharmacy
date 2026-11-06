"""검증: DUR 원본 병용금기 행을 앱이 실제로 잡는지 표본으로 확인한다.
제품 목록에 없는 제품이 든 행은 '목록에 없음'으로 따로 센다.
"""
from collections import Counter

from .engine import analyze


def verify(store, dur_df, sample=1500, seed=0):
    """반환: dict(sampled, checked, stats, recall, exact_recall, failures)
    stats: detected / possible_only / missed / not_in_list 건수
    """
    df = dur_df
    if sample and len(df) > sample:
        df = df.sample(sample, random_state=seed)
    stats, failures = Counter(), []
    for _, row in df.iterrows():
        a = store.find_by_dur_name(row["제품명A"])
        b = store.find_by_dur_name(row["제품명B"])
        if a is None or b is None or a.label == b.label:
            stats["not_in_list"] += 1
            continue
        r = analyze(store, [a, b])
        if r.of_kind("dur"):
            stats["detected"] += 1
        elif r.of_kind("dur_possible"):
            stats["possible_only"] += 1
        else:
            stats["missed"] += 1
            failures.append(row.to_dict())
    checked = stats["detected"] + stats["possible_only"] + stats["missed"]
    return {
        "sampled": len(df),
        "checked": checked,
        "stats": dict(stats),
        "recall": (stats["detected"] + stats["possible_only"]) / checked if checked else None,
        "exact_recall": stats["detected"] / checked if checked else None,
        "failures": failures,
    }
