"""처방전/약봉투 OCR (선택 기능, easyocr 필요). 결과는 후보 제안일 뿐 자동으로 확정하지 않는다."""
import re
from difflib import SequenceMatcher

from .normalize import product_core

_reader = None


def is_available():
    try:
        import easyocr  # noqa: F401
        return True
    except Exception:
        return False


def preprocess(img):
    """대비를 높이고 가로 2000px 이상으로 키운다."""
    from PIL import ImageOps

    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    w, h = g.size
    if w < 2000:
        scale = 2000 / w
        g = g.resize((int(w * scale), int(h * scale)))
    return g


def merge_detections(passes, min_conf=0.05):
    """여러 번 읽은 결과를 합친다 (같은 글자는 신뢰도 높은 쪽만)."""
    best, order = {}, []
    for lst in passes:
        for text, conf in lst:
            k = re.sub(r"[^가-힣A-Za-z0-9]", "", text) or text.strip()
            if not k:
                continue
            if k not in best:
                best[k] = (text, conf)
                order.append(k)
            elif conf > best[k][1]:
                best[k] = (text, conf)
    return [best[k] for k in order if best[k][1] >= min_conf]


def _readtext(reader, arr):
    res = reader.readtext(arr)  # [(bbox, text, conf)]
    res.sort(key=lambda r: (min(p[1] for p in r[0]) // 20, min(p[0] for p in r[0])))  # 대략 읽는 순서
    return [(t, float(c)) for _, t, c in res]


def read_detections(image_bytes, langs=("ko", "en"), min_conf=0.05, enhance=True):
    """이미지 -> [(글자, 신뢰도)]. 신뢰도 낮은 조각도 유지한다. enhance=True 면 원본과 전처리본을 모두 읽는다(약 2배 느림)."""
    global _reader
    import io

    import easyocr
    import numpy as np
    from PIL import Image, ImageOps

    if _reader is None:
        _reader = easyocr.Reader(list(langs), gpu=False)
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(image_bytes)))  # 휴대폰 사진 회전 보정
    passes = [_readtext(_reader, np.array(img.convert("L")))]
    if enhance:
        passes.append(_readtext(_reader, np.array(preprocess(img))))
    return merge_detections(passes, min_conf)


def read_text(image_bytes, **kw):
    """(하위 호환) 글자만 반환."""
    return [t for t, _ in read_detections(image_bytes, **kw)]


def _clean(s):
    return re.sub(r"[^가-힣A-Za-z]", "", s)


EDI_RE = re.compile(r"(?<!\d)\d{9}(?!\d)")


def _similar(core, blob):
    """core 와 가장 비슷한 부분 문자열의 유사도(0~1). 한 글자 오인식 대응."""
    n, best = len(core), 0.0
    for size in (n - 1, n, n + 1):
        if size < 2 or size > len(blob):
            continue
        for i in range(len(blob) - size + 1):
            best = max(best, SequenceMatcher(None, core, blob[i:i + size]).ratio())
            if best >= 1.0:
                return 1.0
    return best


def unmatched_codes(texts, edi_index):
    """제품 코드와 맞지 않는 9자리 번호 (숫자 오인식 가능성)."""
    return [c for c in dict.fromkeys(EDI_RE.findall(" ".join(texts))) if c not in edi_index]


def find_candidates(texts, core_index, ko_ingredients=None, min_len=3, max_products=5, edi_index=None):
    """OCR 텍스트에서 약 후보를 찾는다. 반환: [(kind, value, label)]
    1) 9자리 제품코드 정확 일치 (이름도 보이면 '코드+이름 일치')
    2) 브랜드 핵심어가 텍스트에 있으면 이름 후보 (코드로 확정된 제품의 형제 규격은 제외)
    """
    blob = _clean(" ".join(texts))
    out, used, code_cores = [], set(), set()

    if edi_index:
        for code in dict.fromkeys(EDI_RE.findall(" ".join(texts))):
            for name in edi_index.get(code, []):
                if name in used:
                    continue
                used.add(name)
                core = product_core(name)
                code_cores.add(core)
                if core and core in blob:
                    tag = "코드+이름 일치"
                elif core and _similar(core, blob) >= 0.6:
                    tag = "코드 일치, 이름은 비슷하게 읽힘"
                else:
                    tag = "코드만 일치 - 이름 확인 필요"
                out.append(("product", name, f"[{tag}] {name}"))

    if not blob:
        return out

    seen_ing = set()
    for ko, en in (ko_ingredients or {}).items():
        if len(ko) >= min_len and ko in blob and en not in seen_ing:
            seen_ing.add(en)
            out.append(("ingredient", en, f"성분: {ko} → {en}"))

    # 긴 핵심어 우선, 포함되는 짧은 핵심어는 제외
    cores = sorted((c for c in core_index if len(c) >= min_len and c in blob), key=len, reverse=True)
    kept = []
    for c in cores:
        if any(c in cc for cc in code_cores) or any(c in longer for longer in kept):  # 코드로 확정된 이름의 일부도 제외
            continue
        kept.append(c)
    for c in kept:
        for name in sorted(core_index[c], key=len)[:max_products]:
            if name not in used:
                out.append(("product", name, f"[이름 일치] {name}  (인식 키워드: {c})"))
    return out
