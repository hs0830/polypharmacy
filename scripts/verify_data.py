#!/usr/bin/env python3
"""DUR 원본 행이 앱에서 잡히는지 표본 검증 (빌드 후 실행): python scripts/verify_data.py [--sample N]"""
import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.store import DataStore  # noqa: E402
from src.verify import verify  # noqa: E402


def load_dur(path):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없음: {path}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dur", default="data/raw/dur_banned.csv")
    ap.add_argument("--processed", default="data/processed")
    ap.add_argument("--sample", type=int, default=1500)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    store = DataStore(a.processed)
    res = verify(store, load_dur(a.dur), sample=a.sample, seed=a.seed)
    s = res["stats"]
    print(f"표본 {res['sampled']}행 중 제품 목록에 있어 검증한 행: {res['checked']}행 (목록에 없는 행 {s.get('not_in_list', 0)}행 제외)")
    print(f"  정확 일치로 검출 : {s.get('detected', 0)}")
    print(f"  복합제 포함으로 검출: {s.get('possible_only', 0)}")
    print(f"  검출 실패        : {s.get('missed', 0)}")
    if res["recall"] is not None:
        print(f"재현율 {res['recall']:.1%} (정확 일치만 {res['exact_recall']:.1%})")
    if res["failures"]:
        out = Path(a.processed) / "diagnostics"
        out.mkdir(exist_ok=True)
        pd.DataFrame(res["failures"]).to_csv(out / "verify_missed.csv", index=False, encoding="utf-8-sig")
        print(f"실패 {len(res['failures'])}건 -> {out / 'verify_missed.csv'}")
    return 0 if (res["recall"] or 0) >= 0.99 else 1


if __name__ == "__main__":
    sys.exit(main())
