"""병용금기/상호작용 분석.

원칙: 성분 불명은 '판단 불가'로 따로 보고, '안전'이라 단정하지 않고, 점수는 만들지 않으며, DUR 비고는 함께 전달한다.
"""
from itertools import combinations

from .models import Drug, Finding, Report

# 중복 경고에서 제외할 성분
IGNORED_SHARED = {"purified water", "water", "sodium chloride", "glucose", "dextrose"}

OVERALL_TEXT = {
    "contraindicated": "식약처 DUR 병용금기 조합이 발견되었습니다.",
    "warning": "금기로 확정되지는 않았지만 확인이 필요한 항목(복합제 포함 가능성·성분 중복)이 있습니다.",
    "caution": "DUR 병용금기는 발견되지 않았지만, 참고 상호작용이 있거나 성분을 확인하지 못한 약이 있습니다.",
    "none_found": "등록된 자료에서 발견된 상호작용이 없습니다. 이것이 안전을 의미하지는 않습니다.",
}


def _pair(a, b):
    return (a, b) if a <= b else (b, a)


def analyze(store, drugs):
    # 중복 선택은 1개만 분석
    uniq, ignored, seen = [], [], set()
    for d in drugs:
        if d.label in seen:
            ignored.append(d.label)
            continue
        seen.add(d.label)
        uniq.append(d)

    resolved = [d for d in uniq if d.resolved]
    unresolved = [d for d in uniq if not d.resolved]
    findings = []

    dur_within = {d.label: store.dur_keys_within(d.components) for d in resolved}

    for a, b in combinations(resolved, 2):
        # 1) DUR 병용금기 (정확 일치, 두 표기 모두 조회)
        exact_pairs, seen_rows = set(), set()
        for ka in (a.ingr_key,) + a.alt_keys:
            for kb in (b.ingr_key,) + b.alt_keys:
                pr = _pair(ka, kb)
                exact_pairs.add(pr)
                for row in store.dur_index.get(pr, []):
                    sig = (pr, row["reason"], row["note"])
                    if sig in seen_rows:
                        continue
                    seen_rows.add(sig)
                    findings.append(Finding(
                        kind="dur", severity="contraindicated", drug_a=a.label, drug_b=b.label,
                        title=f"{ka} × {kb}", reason=row["reason"], note=row["note"],
                        notice_no=row["notice_no"], apply_date=row["apply_date"],
                    ))

        # 2) 복합제가 금기 성분을 포함하는 경우
        reported = set()
        for k1 in dur_within[a.label]:
            for k2 in dur_within[b.label]:
                p = _pair(k1, k2)
                if p in exact_pairs or p in reported:
                    continue
                for row in store.dur_index.get(p, []):
                    reported.add(p)
                    findings.append(Finding(
                        kind="dur_possible", severity="warning", drug_a=a.label, drug_b=b.label,
                        title=f"{p[0]} × {p[1]}",
                        reason=row["reason"], note=row["note"],
                        notice_no=row["notice_no"], apply_date=row["apply_date"],
                    ))

        # 3) 성분 중복
        shared = (set(a.components) & set(b.components)) - IGNORED_SHARED
        if shared:
            findings.append(Finding(
                kind="duplicate", severity="warning", drug_a=a.label, drug_b=b.label,
                title="동일 성분 중복: " + ", ".join(sorted(shared)),
                reason="같은 성분이 두 약에 모두 들어 있어 과량 복용 위험이 있습니다.",
            ))

        # 4) DrugBank 참고 상호작용
        details = []
        for c1 in a.components:
            for c2 in b.components:
                n1, al1 = store.alias_of(c1)
                n2, al2 = store.alias_of(c2)
                if n1 == n2:
                    continue
                descs = store.db_index.get((n1, n2), []) + store.db_index.get((n2, n1), [])
                for desc in dict.fromkeys(descs):
                    details.append((c1, c2, desc, al1 or al2))
        if details:
            findings.append(Finding(
                kind="drugbank", severity="info", drug_a=a.label, drug_b=b.label,
                title=f"{len(details)}건", reason="DrugBank 기반 참고 정보 (심각도 정보 없음)", details=details,
            ))

    if any(f.severity == "contraindicated" for f in findings):
        overall = "contraindicated"
    elif any(f.severity == "warning" for f in findings):
        overall = "warning"
    elif findings or unresolved:
        overall = "caution"
    else:
        overall = "none_found"

    return Report(
        drugs=uniq, unresolved=unresolved, findings=findings,
        overall=overall, overall_text=OVERALL_TEXT[overall], ignored_duplicates=ignored,
    )
