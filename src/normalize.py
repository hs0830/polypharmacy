"""성분명/제품명 정규화 (빌드와 앱이 같은 규칙 사용)."""
import re

# 끝에서만 제거할 염/제형 단어
SALT_WORDS = {
    "hydrochloride", "dihydrochloride", "hcl", "sulfate", "bisulfate", "besylate",
    "maleate", "calcium", "sodium", "potassium", "magnesium", "acetate", "phosphate",
    "tartrate", "succinate", "fumarate", "mesylate", "camsylate", "hydrobromide",
    "citrate", "hydrate", "monohydrate", "dihydrate", "trihydrate", "hemihydrate",
    "sesquihydrate", "hexahydrate", "bromide", "chloride", "nitrate", "oxalate",
    "lactate", "gluconate", "benzoate", "propionate", "valerate", "furoate",
    "hyclate", "orotate", "lysinate", "micronized", "coated", "granules", "anhydrous",
    # 제형/제조 방식 표기
    "enteric", "enteric-coated", "extended-release", "sustained-release", "pellets", "pellet",
    "dispersion", "dispersions", "solid", "mixture", "amorphous", "dried", "solution", "d.c.",
    # 추가 염/에스테르
    "ditosylate", "tosylate", "aspartate", "palmitate", "xinafoate", "malate", "hemiedisylate",
    "edisylate", "pentahydrate", "strontium", "l-proline", "bis",
    "propanediol", "granule", "hci",  # hci: DUR 자료의 HCl 오타
}

# 떼면 안 되는 이름
PROTECTED = {"chloral hydrate"}

# 성분명 앞에 붙는 수식어
PREFIX_WORDS = r"(anhydrous|precipitated|dilute|micronized|microemulsion)"

# 확실한 동의어만 (나머지는 unmatched_components.csv 참고)
SYNONYMS = {
    "5-fluorouracil": "fluorouracil",
    "aspirin": "acetylsalicylic acid",
    "diphenylhydantoin": "phenytoin",
    "esomeprazol": "esomeprazole",
    "ethinyl estradiol": "ethinylestradiol",
    "divalproex": "valproic acid",
}


def normalize_component(raw):
    """영문 성분 1개를 정규화. 예: 'rosuvastatin calcium (as rosuvastatin)' -> 'rosuvastatin'"""
    p = str(raw).strip().lower()
    m = re.search(r"\(as ([^)]*)\)?", p)  # 닫는 괄호가 잘린 데이터도 처리
    if m:
        p = re.split(r"\s+\d", m.group(1).strip())[0]
    else:
        p = re.sub(r"\([^)]*\)?", "", p)
    p = re.sub(r"\b\d+(\.\d+)?\s*(mg|g|mcg|iu|%).*$", "", p)
    p = re.sub(r"\s+-\s*", " ", p)  # 'cabozantinib -malate' -> 'cabozantinib malate'
    p = re.sub(r"\s+with\s+.*$", "", p)  # 'metformin hydrochloride with colloidal anhydrous silica'
    p = re.sub(r"\bext\.?(?=\s|$)", "extract", p)
    p = re.sub(r"\s+", " ", p).strip(" -")
    p = re.sub(r"^" + PREFIX_WORDS + r"\s+", "", p)
    if p in PROTECTED:
        return SYNONYMS.get(p, p)
    while True:
        words = p.split(" ")
        if len(words) > 1 and words[-1] in SALT_WORDS:
            rest = " ".join(words[:-1])
            if rest in SALT_WORDS:  # 과잉 제거 방지 (potassium chloride 등)
                break
            p = rest
        else:
            break
    return SYNONYMS.get(p, p)


def ingredient_key(raw):
    """복합제('a+b')를 정렬된 하나의 키로 만든다."""
    comps = sorted({c for c in (normalize_component(x) for x in str(raw).split("+")) if c})
    return "+".join(comps)


def key_components(key):
    return tuple(c for c in str(key).split("+") if c)


# --- 제품명 ---
def strip_strength_suffix(name):
    """DUR 제품명 끝의 '_(0.25g/5mL)' 제거."""
    return re.sub(r"_\(.*\)\s*$", "", str(name)).strip()


def norm_name(s):
    return re.sub(r"\s+", "", str(s)).lower()


def loose_name(s):
    """괄호 내용까지 뺀 비교용 이름."""
    return norm_name(re.sub(r"\([^)]*\)?", "", str(s)))


def korean_parens(name):
    """제품명 괄호 안 한글 성분 후보 (수출 표기 제외)."""
    out = []
    for inner in re.findall(r"\(([^()]*)\)", str(name)):
        if "수출" in inner:
            continue
        k = re.sub(r"[^가-힣]", "", inner)
        if len(k) >= 3:
            out.append(k)
    return out


def parse_korean_ingredients(text):
    """API 주성분 문자열에서 한글 성분명 목록 추출 ('[M040702]포도당|...' 형식 허용)."""
    if text is None:
        return []
    s = str(text)
    if s.strip().lower() in ("", "nan", "none"):
        return []
    s = re.sub(r"\[[A-Za-z]?\d+\]", "", s)
    out = []
    for part in re.split(r"[|/,;\n]", s):
        part = re.sub(r"\([^)]*\)?", "", part)
        part = re.sub(r"\s+", "", part)
        part = re.sub(r"[^가-힣A-Za-z0-9\-]", "", part)
        if len(part) >= 2:
            out.append(part)
    return out


def product_core(name):
    """브랜드 핵심어 추출 (OCR 후보 검색용). 예: '타이레놀정500밀리그램' -> '타이레놀'"""
    s = re.sub(r"\([^)]*\)?", "", str(name))
    cut = re.sub(r"\d.*$", "", s)  # 첫 숫자(함량) 이후 제거
    s = cut if re.search(r"[가-힣A-Za-z]", cut) else s
    s = re.sub(r"[^가-힣A-Za-z]", "", s)
    s = re.sub(r"(밀리그램|밀리그람)$", "", s)
    s = re.sub(r"(연질캡슐|경질캡슐|서방정|장용정|필름코팅정|캡슐|정|주사액|주|시럽|액|크림|연고|겔|패치|과립|산|환)$", "", s)
    return s


# --- 한글 성분명 조회 ---
KO_SALT_SUFFIXES = sorted([
    "브롬화수소산염수화물", "브롬화수소산염", "염산염수화물", "염산염", "일수화물", "이수화물", "삼수화물",
    "반수화물", "수화물", "무수물", "베실산염", "메실산염", "말레산염", "푸마르산염", "타르타르산염",
    "황산염", "인산염", "질산염", "아세트산염", "구연산염", "숙신산염", "옥살산염", "젖산염", "나트륨",
    "칼륨", "칼슘", "마그네슘", "미분화", "유전자재조합",
], key=len, reverse=True)


def ko_lookup(name, mapping):
    """한글 성분명 조회. 못 찾으면 염/수화물 접미사를 떼며 재시도."""
    n = re.sub(r"\s+", "", str(name))
    while len(n) >= 2:
        if n in mapping:
            return mapping[n]
        for suf in KO_SALT_SUFFIXES:
            if n.endswith(suf) and len(n) > len(suf) + 1:
                n = n[: -len(suf)]
                break
        else:
            return None
    return None


def paren_ingredient_lists(name):
    """괄호 안 성분을 리스트로 반환. '(a, b)' -> ['a', 'b'] (수출 표기 제외)."""
    out = []
    for inner in re.findall(r"\(([^()]*)\)", str(name)):
        if "수출" in inner:
            continue
        parts = [re.sub(r"[^가-힣]", "", p) for p in re.split(r"[,·/+]", inner)]
        parts = [p for p in parts if len(p) >= 2]
        if parts:
            out.append(parts)
    return out
