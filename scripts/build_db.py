#!/usr/bin/env python3
"""원본 CSV -> 앱용 정제 데이터(data/processed) 빌드.

입력(data/raw): item_list.csv, ingredients.csv(선택), dur_banned.csv, db_drug_interactions.csv
원칙: 성분은 DUR 의 (제품명-영문 성분명)을 기준으로 삼고, 못 찾은 제품도 버리지 않고 표시하며, 복합제는 성분 목록을 유지한다.
산출물: products.csv, dur_pairs.csv, drugbank_pairs.csv.gz, 사전·진단 파일
"""
import argparse
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.normalize import (  # noqa: E402
    SYNONYMS,
    ingredient_key,
    key_components,
    ko_lookup,
    korean_parens,
    loose_name,
    norm_name,
    paren_ingredient_lists,
    parse_korean_ingredients,
    strip_strength_suffix,
)

ING_TEXT_COLUMNS = ["MAIN_ITEM_INGR", "MAIN_INGR"]


def load_csv(path):
    for enc in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False, dtype=str, keep_default_na=False)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"인코딩을 알 수 없음: {path}")


def _ko(s):
    return re.sub(r"\s+", "", str(s))


def clean_text(s):
    """e약은요 본문의 HTML 태그/엔티티 정리 (문단은 줄바꿈 유지)."""
    s = str(s or "")
    s = re.sub(r"</p>|<br\s*/?>|</li>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)  # 태그를 먼저 제거 (이스케이프된 본문은 보존)
    s = html.unescape(s)
    s = re.sub(r"[ \t\u00a0]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s


EASY_FIELDS = {  # 출력 컬럼 <- e약은요 필드
    "efcy": "efcyqesitm",
    "use_method": "usemethodqesitm",
    "warn": "atpnwarnqesitm",
    "atpn": "atpnqesitm",
    "intrc": "intrcqesitm",
    "se": "seqesitm",
    "deposit": "depositmethodqesitm",
    "image": "itemimage",
}


def build_drug_info(easy_path, out):
    """e약은요 CSV -> drug_info.csv (ITEM_SEQ 키). 행 수 반환."""
    easy = load_csv(easy_path)
    low = {c.lower(): c for c in easy.columns}
    if "itemseq" not in low:
        raise ValueError("e약은요 CSV 에 itemSeq 컬럼이 없습니다.")
    df = pd.DataFrame({"ITEM_SEQ": easy[low["itemseq"]].str.strip()})
    for outc, src in EASY_FIELDS.items():
        df[outc] = easy[low[src]].map(clean_text) if src in low else ""
    df = df[df["ITEM_SEQ"] != ""].drop_duplicates("ITEM_SEQ")
    df.to_csv(out / "drug_info.csv", index=False, encoding="utf-8-sig")
    return len(df)


def build(item_path, dur_path, ddi_path, out_dir, ingredients_path=None, manual_path=None, synonyms_path=None,
          easy_path=None):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    notes = []

    # 수기 동의어는 키를 만들기 전에 적용
    n_syn = 0
    if synonyms_path and Path(synonyms_path).exists():
        syn = load_csv(synonyms_path)
        for f_, t_ in zip(syn["from"], syn["to"]):
            if f_.strip() and t_.strip():
                SYNONYMS[f_.strip().lower()] = t_.strip().lower()
                n_syn += 1

    # --- 입력 ---
    items = load_csv(item_path)
    if "ITEM_NAME" not in items.columns:
        raise ValueError("item_list.csv 에 ITEM_NAME 컬럼이 없습니다.")
    for c in ("ENTP_NAME",):
        if c not in items.columns:
            items[c] = ""
    items["ITEM_NAME"] = items["ITEM_NAME"].str.strip()
    items = items[items["ITEM_NAME"] != ""].copy()
    has_seq = "ITEM_SEQ" in items.columns and (items["ITEM_SEQ"].str.strip() != "").any()
    items = items.drop_duplicates(subset=["ITEM_SEQ"] if has_seq else ["ITEM_NAME"]).reset_index(drop=True)

    dur = load_csv(dur_path)

    # 제품별 한글 성분: ingredients.csv 또는 목록 API
    ko_lists = {}
    src_label = "없음"
    if ingredients_path and Path(ingredients_path).exists():
        ing = load_csv(ingredients_path)
        name_col = next((c for c in ("MTRAL_NM", "MTRAL_NAME") if c in ing.columns), None)
        if has_seq and "ITEM_SEQ" in ing.columns and name_col:
            for seq, grp in ing.groupby("ITEM_SEQ"):
                names = [_ko(x) for x in grp[name_col] if _ko(x)]
                ko_lists[seq] = list(dict.fromkeys(names))
            src_label = f"ingredients.csv ({len(ko_lists)}개 제품)"
        else:
            notes.append("ingredients.csv 를 무시함: ITEM_SEQ 또는 MTRAL_NM 컬럼이 없습니다.")
    ing_col = next((c for c in ING_TEXT_COLUMNS if c in items.columns and (items[c].str.strip() != "").any()), None)

    def ko_list_for(row):
        if has_seq and row["ITEM_SEQ"] in ko_lists:
            return ko_lists[row["ITEM_SEQ"]]
        if ing_col:
            return [_ko(x) for x in parse_korean_ingredients(row[ing_col])]
        return []

    if ing_col and src_label == "없음":
        src_label = f"목록 API 컬럼 {ing_col}"
    elif ing_col:
        src_label += f" + {ing_col}"

    # --- DUR: 제품명 -> 성분키 ---
    dur["keyA"] = dur["성분명A"].map(ingredient_key)
    dur["keyB"] = dur["성분명B"].map(ingredient_key)
    dp = pd.concat([
        dur[["제품명A", "keyA"]].set_axis(["name", "key"], axis=1),
        dur[["제품명B", "keyB"]].set_axis(["name", "key"], axis=1),
    ]).drop_duplicates()
    dp["base"] = dp["name"].map(strip_strength_suffix)
    dp["exact"] = dp["base"].map(norm_name)
    dp["loose"] = dp["base"].map(loose_name)
    exact_map = dp.groupby("exact")["key"].agg(set).to_dict()
    loose_map = dp.groupby("loose")["key"].agg(set).to_dict()

    # 괄호의 한글 성분 -> 영문 키 (모호하면 제외)
    paren_votes = defaultdict(set)
    for base, key in zip(dp["base"], dp["key"]):
        for k in korean_parens(base):
            paren_votes[k].add(key)
    paren_dict = {
        k: next(iter(v)) for k, v in paren_votes.items()
        if len(v) == 1 and len(key_components(next(iter(v)))) == 1
    }

    # 수기 사전 (우선순위 가장 낮음)
    manual_dict = {}
    if manual_path and Path(manual_path).exists():
        man = load_csv(manual_path)
        for ko, en in zip(man["ko"], man["en"]):
            if _ko(ko) and en.strip():
                manual_dict[_ko(ko)] = ingredient_key(en)

    # --- API 영문 성분 (ITEM_INGR_NAME) ---
    has_api_en = "ITEM_INGR_NAME" in items.columns and (items["ITEM_INGR_NAME"].str.strip() != "").any()
    if has_api_en:
        src_label = (src_label + " + " if src_label != "없음" else "") + "목록 API ITEM_INGR_NAME(영문)"

    def api_english(row):
        """(성분키, 상태). 상태: ok | empty | count_mismatch"""
        if not has_api_en:
            return "", "empty"
        parts = [x for x in re.split(r"[/+;|]", row["ITEM_INGR_NAME"]) if x.strip()]
        if not parts:
            return "", "empty"
        cnt = str(row.get("ITEM_INGR_CNT", "")).strip()
        if cnt.isdigit() and int(cnt) > 0 and len(parts) != int(cnt):
            return "", "count_mismatch"  # 성분 개수가 안 맞으면 확정하지 않는다
        key = ingredient_key("+".join(parts))
        return (key, "ok") if key else ("", "empty")

    # --- 1차 매핑 ---
    rows = []
    learn_votes = defaultdict(set)
    name_votes = defaultdict(lambda: {"keys": set(), "entp": set()})  # 제품명 괄호의 한글 성분명 -> 영문 성분키
    for _, r in items.iterrows():
        name = r["ITEM_NAME"]
        cand, src = exact_map.get(norm_name(name)), "dur_exact"
        if not cand:
            cand, src = loose_map.get(loose_name(name)), "dur_loose"
        kl = ko_list_for(r)
        akey, astat = api_english(r)
        rows.append({"ko": kl, "cand": cand, "src": src if cand else None, "akey": akey, "astat": astat})
        # 한글 -> 영문 학습 (단일 성분 제품만)
        single = None
        if cand and len(cand) == 1:
            single = next(iter(cand))
        elif akey:
            single = akey
        if single and len(kl) == 1 and len(key_components(single)) == 1:
            learn_votes[kl[0]].add(single)
        # 제품명 괄호에서도 학습 (제조사 2곳 이상에서 쓰인 이름만)
        if single and len(key_components(single)) == 1:
            plists = paren_ingredient_lists(name)
            if len(plists) == 1 and len(plists[0]) == 1:
                nv = name_votes[plists[0][0]]
                nv["keys"].add(single)
                nv["entp"].add(r["ENTP_NAME"])
    learned = {k: next(iter(v)) for k, v in learn_votes.items() if len(v) == 1}
    name_learned = {k: next(iter(v["keys"])) for k, v in name_votes.items()
                    if len(v["keys"]) == 1 and len(v["entp"]) >= 2}

    # --- 데이터 기반 성분 별칭 학습 ---
    # 같은 제품의 DUR 표기 X 와 API 표기 X' 가 1:1 이면 별칭으로 본다 (충돌하면 보류)
    alias_votes = defaultdict(Counter)
    for rec in rows:
        cand, akey = rec["cand"], rec["akey"]
        if not (cand and len(cand) == 1 and akey):
            continue
        dc, ac = set(key_components(next(iter(cand)))), set(key_components(akey))
        for c in ac & dc:
            alias_votes[c][c] += 1
        a_only, d_only = ac - dc, dc - ac
        if len(a_only) == 1 and len(d_only) == 1:
            alias_votes[next(iter(a_only))][next(iter(d_only))] += 1
    learned_alias, alias_conflicts = {}, []
    for a_comp, ctr in alias_votes.items():
        targets = set(ctr)
        if len(targets) == 1 and next(iter(targets)) != a_comp:
            learned_alias[a_comp] = next(iter(targets))
        elif len(targets) > 1 and any(t != a_comp for t in targets):
            alias_conflicts.append((a_comp, "; ".join(f"{t}:{n}" for t, n in ctr.most_common())))

    def apply_alias(akey):
        if not akey:
            return akey
        return "+".join(sorted({learned_alias.get(c, c) for c in key_components(akey)}))


    # 우선순위: 수기 < DUR 괄호 < 제품명 괄호 학습 < ingredients.csv 학습
    ingredient_dict = {**manual_dict, **paren_dict, **name_learned, **learned}
    conflicts = [(k, manual_dict[k], v) for k, v in {**paren_dict, **learned}.items()
                 if k in manual_dict and manual_dict[k] != v]

    # --- 2차 이후 매핑 ---
    keys, sources, ko_col, alt_keys = [], [], [], []
    api_dur_mismatch = 0
    mismatch_pairs = Counter()
    mismatch_example = {}
    for (_, r), rec in zip(items.iterrows(), rows):
        cand, src, kl = rec["cand"], rec["src"], rec["ko"]
        akey, astat = apply_alias(rec["akey"]), rec["astat"]
        key, alt = "", ""
        if cand:
            if len(cand) > 1:
                src = "ambiguous"
            else:
                key = next(iter(cand))
                if akey and akey != key:
                    alt = akey  # 두 표기 모두 보존 (엔진이 둘 다로 조회)
                    api_dur_mismatch += 1  # DUR 표기 우선
                    mismatch_pairs[(key, akey)] += 1
                    mismatch_example.setdefault((key, akey), r["ITEM_NAME"])
        elif akey:
            key, src = akey, "api_english"
        else:
            src = None
            if kl:
                known = [ko_lookup(k, ingredient_dict) for k in kl]
                if all(known):
                    key, src = ingredient_key("+".join(known)), "api_ingredients"
            if src is None:
                hits = set()
                for parts in paren_ingredient_lists(r["ITEM_NAME"]):
                    known = [ko_lookup(p, ingredient_dict) for p in parts]
                    if all(known):  # 괄호 안 성분이 전부 사전에 있을 때만 인정
                        hits.add(ingredient_key("+".join(known)))
                if len(hits) == 1:
                    key, src = next(iter(hits)), "paren_dict"
            if src is None:
                src = "count_mismatch" if astat == "count_mismatch" else ("partial" if kl else "unmapped")
        keys.append(key)
        alt_keys.append(alt)
        sources.append(src)
        ko_col.append("|".join(kl))

    prod = items.copy()
    prod["ING_KO"] = ko_col
    prod["INGR_KEY"] = keys
    prod["ALT_KEY"] = alt_keys
    prod["MAP_SOURCE"] = sources
    prod["IS_EXPORT"] = prod["ITEM_NAME"].str.contains("수출", na=False)
    if "CANCEL_NAME" in prod.columns:  # '정상'이 아니면 취소/취하
        cn = prod["CANCEL_NAME"].str.strip()
        prod["IS_CANCELED"] = (cn != "") & (cn != "정상")
    else:
        prod["IS_CANCELED"] = False
    front = [c for c in ("ITEM_SEQ", "ITEM_NAME", "ITEM_ENG_NAME", "ENTP_NAME", "SPCLTY_PBLC", "ETC_OTC_CODE",
                         "PRDUCT_TYPE", "ITEM_PERMIT_DATE", "ITEM_INGR_NAME", "EDI_CODE") if c in prod.columns]
    back = ["ING_KO", "INGR_KEY", "ALT_KEY", "MAP_SOURCE", "IS_EXPORT", "IS_CANCELED"]
    prod = prod[front + back]
    prod.to_csv(out / "products.csv", index=False, encoding="utf-8-sig")

    # --- 약 정보 (e약은요) ---
    info_rows = 0
    if easy_path and Path(easy_path).exists():
        if has_seq:
            info_rows = build_drug_info(easy_path, out)
            covered = int(prod["ITEM_SEQ"].isin(pd.read_csv(out / "drug_info.csv", dtype=str)["ITEM_SEQ"]).sum())
            notes.append(f"약 정보(e약은요): {info_rows}건 수집, 제품 목록과 연결되는 제품 {covered}개")
        else:
            notes.append("e약은요를 무시함: item_list 에 ITEM_SEQ 가 없어 제품과 연결할 수 없습니다.")

    # --- 진단 파일 ---
    diag_dir = out / "diagnostics"
    diag_dir.mkdir(exist_ok=True)
    pd.DataFrame(
        [(k[0], k[1], n, mismatch_example[k]) for k, n in mismatch_pairs.most_common()],
        columns=["dur_key", "api_key", "products", "example_item"],
    ).to_csv(diag_dir / "key_mismatch.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(
        sorted(((a, d, alias_votes[a][d]) for a, d in learned_alias.items()), key=lambda x: -x[2]),
        columns=["api_component", "dur_component", "products"],
    ).to_csv(diag_dir / "learned_alias.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(alias_conflicts, columns=["api_component", "targets(dur_component:products)"]).to_csv(
        diag_dir / "alias_conflicts.csv", index=False, encoding="utf-8-sig")
    bad = prod["MAP_SOURCE"].isin(["count_mismatch", "unmapped", "partial", "ambiguous"])
    cols = [c for c in ("ITEM_NAME", "ITEM_INGR_NAME", "ITEM_INGR_CNT") if c in items.columns]
    unresolved_df = items.loc[bad.values, cols].copy()
    unresolved_df.insert(0, "MAP_SOURCE", prod.loc[bad, "MAP_SOURCE"].values)
    unresolved_df.to_csv(diag_dir / "unresolved_products.csv", index=False, encoding="utf-8-sig")

    # --- DUR 성분키 쌍 (방향 무시, 최신 고시 우선) ---
    d = dur[["keyA", "keyB", "금기사유", "비고", "고시번호", "고시적용일"]].copy()
    d["ingr_a"] = d[["keyA", "keyB"]].min(axis=1)
    d["ingr_b"] = d[["keyA", "keyB"]].max(axis=1)
    d = d.rename(columns={"금기사유": "reason", "비고": "note", "고시번호": "notice_no", "고시적용일": "apply_date"})
    d["note"] = d["note"].fillna("").str.strip()
    d = (d.sort_values("apply_date", ascending=False)
          .drop_duplicates(["ingr_a", "ingr_b", "reason", "note"])
          [["ingr_a", "ingr_b", "reason", "note", "notice_no", "apply_date"]]
          .sort_values(["ingr_a", "ingr_b"]))
    d.to_csv(out / "dur_pairs.csv", index=False, encoding="utf-8-sig")

    # --- 성분 사전 ---
    pd.DataFrame(sorted(ingredient_dict.items()), columns=["ko", "en_key"]).to_csv(
        out / "ingredient_dictionary.csv", index=False, encoding="utf-8-sig")

    # --- DrugBank ---
    db_count = alias_count = miss_count = 0
    if ddi_path and Path(ddi_path).exists():
        ddi = load_csv(ddi_path).rename(columns={
            "Drug 1": "drug_a", "Drug 2": "drug_b", "Interaction Description": "description"})
        for c in ("drug_a", "drug_b"):
            ddi[c] = ddi[c].str.lower().str.strip()
        ddi["description"] = ddi["description"].str.strip()
        ddi = ddi.drop_duplicates(["drug_a", "drug_b", "description"])
        ddi[["drug_a", "drug_b", "description"]].to_csv(
            out / "drugbank_pairs.csv.gz", index=False, encoding="utf-8", compression="gzip")
        db_count = len(ddi)
        db_names = set(ddi["drug_a"]) | set(ddi["drug_b"])

        comps = {c for k in set(keys) | set(d["ingr_a"]) | set(d["ingr_b"]) for c in key_components(k)}
        alias, miss = {}, []
        for c in sorted(comps):
            if c in db_names:
                continue
            variants = [re.sub(r"^(d|l|dl|s|r)-", "", c), c.replace("-", " "), c.replace("-", "")]
            hit = next((v for v in variants if v != c and v in db_names), None)
            if hit:
                alias[c] = hit
            else:
                miss.append(c)
        pd.DataFrame(sorted(alias.items()), columns=["component", "drugbank_name"]).to_csv(
            out / "component_alias.csv", index=False, encoding="utf-8-sig")
        freq = Counter(c for k in prod.loc[prod["INGR_KEY"] != "", "INGR_KEY"] for c in key_components(k))
        um = pd.DataFrame({"component": miss})
        um["products"] = um["component"].map(lambda c: freq.get(c, 0))
        um.sort_values("products", ascending=False).to_csv(  # 제품 수 많은 순
            out / "unmatched_components.csv", index=False, encoding="utf-8-sig")
        alias_count, miss_count = len(alias), len(miss)
        total_comps = len(comps)
    else:
        total_comps = 0
        notes.append("DrugBank 파일이 없어 drugbank_pairs.csv.gz 를 만들지 않았습니다.")

    # --- 리포트 ---
    n = len(prod)
    vc = prod["MAP_SOURCE"].value_counts()
    dur_keys = set(d["ingr_a"]) | set(d["ingr_b"])
    mapped_keys = set(prod.loc[prod["INGR_KEY"] != "", "INGR_KEY"])
    lines = [f"제품 수: {n}  (ITEM_SEQ {'있음' if has_seq else '없음 - 이름으로 식별'})",
             f"한글 성분 정보 출처: {src_label}"]
    for k in ["dur_exact", "dur_loose", "api_english", "api_ingredients", "paren_dict",
              "count_mismatch", "partial", "ambiguous", "unmapped"]:
        lines.append(f"  {k:<16}: {int(vc.get(k, 0)):>6} ({vc.get(k, 0) / n:.1%})")
    lines += [
        f"성분키 확정 제품: {int((prod['INGR_KEY'] != '').sum())} / 수출용 표기 {int(prod['IS_EXPORT'].sum())}"
        f" / 허가취소 등 {int(prod['IS_CANCELED'].sum())}",
        f"DUR 성분키와 API 영문 성분키가 다른 제품(별칭 적용 후): {api_dur_mismatch}개 (DUR 쪽 표기를 사용)",
        f"데이터에서 학습한 성분 별칭 {len(learned_alias)}개 / 충돌로 보류 {len(alias_conflicts)}개 (diagnostics 참고)",
        f"수기 동의어 {n_syn}개 적용 / 두 표기를 모두 보존한 제품(ALT_KEY): {sum(1 for a in alt_keys if a)}개",
        f"DUR 병용금기: 원본 {len(dur)}행 -> 성분키 쌍 {len(d)}행",
        f"DUR 성분키 {len(dur_keys)}개 중 제품과 연결되는 키 {len(dur_keys & mapped_keys)}개",
        f"한글->영문 성분 사전: {len(ingredient_dict)}개 (수기 {len(manual_dict)} / DUR 괄호 {len(paren_dict)} / "
        f"제품명 괄호 학습 {len(name_learned)} / 성분 목록 학습 {len(learned)})",
    ]
    if conflicts:
        lines.append(f"수기 사전과 데이터 학습 결과가 다른 항목 {len(conflicts)}개 (데이터 쪽 채택): "
                     + ", ".join(f"{k}: {m}->{v}" for k, m, v in conflicts[:10]))
    if db_count:
        lines.append(f"DrugBank 쌍 {db_count}행 / 성분 {total_comps}개 중 이름 일치 "
                     f"{total_comps - alias_count - miss_count}개, 별칭 보정 {alias_count}개, 불일치 {miss_count}개")
    lines += notes
    text = "\n".join(lines)
    (out / "mapping_report.txt").write_text(text + "\n", encoding="utf-8")
    info = {
        "built_at": datetime.now().isoformat(timespec="seconds"),
        "products": n,
        "products_resolved": int((prod["INGR_KEY"] != "").sum()),
        "api_dur_mismatch": api_dur_mismatch,
        "learned_alias": len(learned_alias),
        "drug_info": info_rows,
        "dur_latest": max((x for x in d["apply_date"] if x), default=""),
        "permit_latest": max((x for x in items["ITEM_PERMIT_DATE"] if x), default="") if "ITEM_PERMIT_DATE" in items.columns else "",
        "dur_pairs": len(d),
        "drugbank_pairs": db_count,
        "ingredient_source": src_label,
    }
    (out / "build_info.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(text)
    return info


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", default="data/raw/item_list.csv")
    ap.add_argument("--ingredients", default="data/raw/ingredients.csv")
    ap.add_argument("--manual", default="data/manual/ingredient_ko_en.csv")
    ap.add_argument("--synonyms", default="data/manual/ingredient_synonyms.csv")
    ap.add_argument("--easy", default="data/raw/easy_drug.csv")
    ap.add_argument("--dur", default="data/raw/dur_banned.csv")
    ap.add_argument("--ddi", default="data/raw/db_drug_interactions.csv")
    ap.add_argument("--out", default="data/processed")
    a = ap.parse_args()
    build(a.item, a.dur, a.ddi, a.out, ingredients_path=a.ingredients, manual_path=a.manual,
          synonyms_path=a.synonyms, easy_path=a.easy)
