#!/usr/bin/env python3
"""접수된 문제 신고 보기: python scripts/show_feedback.py [--all] [--csv 파일]"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.feedback import load_reports  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/feedback")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--csv")
    a = ap.parse_args()
    reps = load_reports(a.dir)
    if not reps:
        print("접수된 신고가 없습니다.")
        return 0
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["id", "time", "type", "message", "contact", "drugs", "result", "error"])
            for r in reps:
                c = r.get("context", {})
                w.writerow([r["id"], r["time"], r["type"], r["message"], r.get("contact", ""),
                            " | ".join(c.get("drugs", [])), c.get("result", ""), c.get("error", "")])
        print(f"{len(reps)}건 -> {a.csv}")
        return 0
    for r in (reps if a.all else reps[-20:]):
        c = r.get("context", {})
        print(f"[{r['time']}] {r['id']} · {r['type']}")
        print("  " + r["message"].replace("\n", "\n  "))
        if r.get("contact"):
            print(f"  연락처: {r['contact']}")
        if c.get("drugs"):
            print(f"  약: {', '.join(c['drugs'])}")
        if c.get("result"):
            print(f"  결과 요약: {c['result']}")
        if c.get("error"):
            print("  오류:\n    " + c["error"].strip().replace("\n", "\n    "))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
