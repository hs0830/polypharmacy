"""정제 데이터(data/processed) 로더 + 검색/조회 인덱스."""
import json
import re
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .models import Drug, SearchHit
from .normalize import key_components, loose_name, norm_name, product_core, strip_strength_suffix


class DataStoreError(RuntimeError):
    pass


def _read(path, **kw):
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", **kw)


class DataStore:
    def __init__(self, processed_dir="data/processed"):
        d = Path(processed_dir)
        need = [d / "products.csv", d / "dur_pairs.csv"]
        missing = [p.name for p in need if not p.exists()]
        if missing:
            raise DataStoreError(
                f"{processed_dir} 에 {', '.join(missing)} 가 없습니다. "
                "`python scripts/build_db.py` 를 먼저 실행하세요."
            )
        self.dir = d

        # --- 제품 ---
        p = _read(d / "products.csv")
        p["IS_EXPORT"] = p["IS_EXPORT"].str.lower().eq("true")
        p["IS_CANCELED"] = p["IS_CANCELED"].str.lower().eq("true") if "IS_CANCELED" in p else False
        p["_n"] = p["ITEM_NAME"].map(norm_name)
        self.products = p
        self._by_name = {n: i for i, n in reversed(list(enumerate(p["ITEM_NAME"])))}  # 중복이면 첫 행
        self._by_norm = {n: i for i, n in reversed(list(enumerate(p["_n"])))}
        self._core_index = None

        # 9자리 제품(EDI) 코드 -> 제품명 (처방전 인식용)
        self.edi_index = defaultdict(list)
        if "EDI_CODE" in p.columns:
            for name, codes in zip(p["ITEM_NAME"], p["EDI_CODE"]):
                for c in re.findall(r"(?<!\d)\d{9}(?!\d)", codes):
                    self.edi_index[c].append(name)

        # --- DUR ---
        dur = _read(d / "dur_pairs.csv")
        self.dur_index = defaultdict(list)
        for r in dur.itertuples(index=False):
            self.dur_index[(r.ingr_a, r.ingr_b)].append(
                {"reason": r.reason, "note": r.note, "notice_no": r.notice_no, "apply_date": r.apply_date}
            )
        self.dur_latest = max((x for x in dur["apply_date"] if x), default="")  # DUR 고시 적용일 중 가장 최근
        self.dur_key_comps = {}
        self.comp_to_dur_keys = defaultdict(set)
        for k in set(dur["ingr_a"]) | set(dur["ingr_b"]):
            comps = frozenset(key_components(k))
            self.dur_key_comps[k] = comps
            for c in comps:
                self.comp_to_dur_keys[c].add(k)

        # --- DrugBank (선택) ---
        self.db_index = defaultdict(list)
        gz = d / "drugbank_pairs.csv.gz"
        if gz.exists():
            db = pd.read_csv(gz, dtype=str, keep_default_na=False)
            for a, b, desc in zip(db["drug_a"], db["drug_b"], db["description"]):
                self.db_index[(a, b)].append(desc)
        self.has_drugbank = bool(self.db_index)

        alias_f = d / "component_alias.csv"
        self.alias = dict(_read(alias_f).values) if alias_f.exists() else {}

        dic_f = d / "ingredient_dictionary.csv"
        self.ko_dict = dict(_read(dic_f).values) if dic_f.exists() else {}
        self.ingredient_keys = sorted(
            set(p.loc[p["INGR_KEY"] != "", "INGR_KEY"]) | set(dur["ingr_a"]) | set(dur["ingr_b"])
        )

        # e약은요 약 정보 (선택): ITEM_SEQ -> 정보
        di = d / "drug_info.csv"
        self.drug_info = {r["ITEM_SEQ"]: r for r in _read(di).to_dict("records")} if di.exists() else {}
        self._ko_by_key = defaultdict(list)
        for ko, en in self.ko_dict.items():
            self._ko_by_key[en].append(ko)

        info_f = d / "build_info.json"
        self.info = json.loads(info_f.read_text(encoding="utf-8")) if info_f.exists() else {}
        self.info.setdefault("dur_latest", self.dur_latest)  # 데이터 기준일 (화면/PDF 표시)
        self._loose = None

    # --- 조회 ---
    def alias_of(self, comp):
        """(DrugBank 이름, 별칭 사용 여부)"""
        if comp in self.alias:
            return self.alias[comp], True
        return comp, False

    def dur_keys_within(self, comps):
        """성분 집합에 완전히 포함되는 DUR 성분키들."""
        cs = set(comps)
        cand = set()
        for c in cs:
            cand |= self.comp_to_dur_keys.get(c, set())
        return [k for k in cand if self.dur_key_comps[k] <= cs]

    def resolve_product(self, item_name):
        i = self._by_name.get(item_name)
        if i is None:
            return Drug(label=item_name, kind="product", map_source="not_found")
        r = self.products.iloc[i]
        key = r["INGR_KEY"]
        alt = r["ALT_KEY"] if "ALT_KEY" in r.index else ""
        comps = tuple(sorted(set(key_components(key)) | set(key_components(alt)))) if key else ()
        return Drug(
            label=r["ITEM_NAME"], kind="product", ingr_key=key, components=comps,
            alt_keys=(alt,) if key and alt and alt != key else (),
            map_source=r["MAP_SOURCE"], entp=r["ENTP_NAME"], is_export=bool(r["IS_EXPORT"]),
        )

    def resolve_ingredient(self, key):
        comps = key_components(key)
        return Drug(label=f"[성분] {key}", kind="ingredient", ingr_key=key, components=comps,
                    map_source="ingredient")

    def resolve_hit(self, hit):
        return self.resolve_ingredient(hit.value) if hit.kind == "ingredient" else self.resolve_product(hit.value)

    # --- 약 정보 ---
    def product_detail(self, item_name):
        """제품 기본 정보 + e약은요 정보 (제품이 없으면 None)."""
        i = self._by_name.get(item_name)
        if i is None:
            return None
        row = self.products.iloc[i].to_dict()
        seq = row.get("ITEM_SEQ", "")
        return {"product": row, "info": self.drug_info.get(seq) if seq else None}

    def find_by_dur_name(self, dur_product_name):
        """DUR 제품명으로 제품 찾기 (정확 일치 -> 괄호 무시 일치). 없으면 None."""
        base = strip_strength_suffix(dur_product_name)
        i = self._by_norm.get(norm_name(base))
        if i is None:
            if self._loose is None:
                self._loose = {}
                for j, n in enumerate(self.products["ITEM_NAME"]):
                    self._loose.setdefault(loose_name(n), j)
            i = self._loose.get(loose_name(base))
        return None if i is None else self.resolve_product(self.products.iloc[i]["ITEM_NAME"])

    def category_of(self, item_name):
        """허가정보 제품 분류 ('[01240]진경제' -> '진경제'). 없으면 빈 문자열."""
        i = self._by_name.get(item_name)
        if i is None:
            return ""
        row = self.products.iloc[i]
        t = row["PRDUCT_TYPE"] if "PRDUCT_TYPE" in row.index else ""
        return re.sub(r"^\[[^\]]*\]\s*", "", str(t)).strip()

    def ko_names(self, ingr_key):
        return sorted(self._ko_by_key.get(ingr_key, []))

    # --- 검색 ---
    def search(self, query, limit=30, include_export=False):
        q = norm_name(query)
        ql = query.strip().lower()
        if not q:
            return []
        hits, seen = [], set()

        for ko, en in sorted(((k, v) for k, v in self.ko_dict.items() if q in k),
                             key=lambda kv: (not kv[0].startswith(q), len(kv[0]))):
            if en not in seen:
                seen.add(en)
                hits.append(SearchHit("ingredient", f"성분: {ko} → {en}", en))
        if len(ql) >= 3:
            for en in self.ingredient_keys:
                if ql in en and en not in seen:
                    seen.add(en)
                    hits.append(SearchHit("ingredient", f"성분: {en}", en))
        hits = hits[:8]

        m = self.products["_n"].str.contains(q, regex=False)
        if not include_export:  # 수출용/허가취소 품목은 기본적으로 숨김
            m &= ~(self.products["IS_EXPORT"] | self.products["IS_CANCELED"])
        sub = self.products[m].copy()
        if not sub.empty:
            sub["_rank"] = [(0 if n.startswith(q) else 1, len(n)) for n in sub["_n"]]
            sub = sub.sort_values("_rank").head(limit)
            for r in sub.itertuples(index=False):
                ok = bool(r.INGR_KEY)
                mark = "✅" if ok else "⚠️"
                hits.append(SearchHit("product", f"{mark} {r.ITEM_NAME} — {r.ENTP_NAME}", r.ITEM_NAME, ok))
        return hits

    # --- OCR 후보용 ---
    @property
    def core_index(self):
        """브랜드 핵심어 -> 제품명 목록 (OCR용, 지연 생성)."""
        if self._core_index is None:
            idx = defaultdict(list)
            for name, exp, can in zip(self.products["ITEM_NAME"], self.products["IS_EXPORT"],
                                      self.products["IS_CANCELED"]):
                if exp or can:
                    continue
                core = product_core(name)
                if len(core) >= 3:
                    idx[core].append(name)
            self._core_index = dict(idx)
        return self._core_index
