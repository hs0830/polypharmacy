from src.normalize import product_core
from src.ocr import find_candidates, merge_detections, preprocess, unmatched_codes

CORE = {"타이레놀": ["타이레놀정500밀리그램", "타이레놀콜드에스정"], "레놀": ["레놀정"], "아스피린": ["아스피린장용정100밀리그램"]}


def test_core_must_be_in_text_and_shorter_overlaps_dropped():
    out = find_candidates(["처방: 타이레놀 500mg 1일 3회"], CORE)
    values = [v for _, v, _ in out]
    assert "타이레놀정500밀리그램" in values
    assert "레놀정" not in values  # '타이레놀' 안에 포함된 더 짧은 핵심어는 제외
    assert "아스피린장용정100밀리그램" not in values


def test_short_or_unrelated_text_gives_nothing():
    assert find_candidates(["정 캡슐 1일 3회"], CORE) == []
    assert find_candidates([], CORE) == []


def test_ingredient_candidates():
    out = find_candidates(["아세트아미노펜 325mg"], {}, ko_ingredients={"아세트아미노펜": "acetaminophen"})
    assert out == [("ingredient", "acetaminophen", "성분: 아세트아미노펜 → acetaminophen")]


EDI = {"645604690": ["후로스판디정(플로로글루시놀)"], "663601460": ["엑사드캡슐(니자티딘)"]}
CORE2 = {"후로스판디": ["후로스판디정(플로로글루시놀)"], "후로스판": ["후로스판정(플로로글루시놀)"],
         "엑사드": ["엑사드캡슐(니자티딘)", "엑사드정75밀리그램(니자티딘)"]}
LINES = ["645604690 후로스판디정/1정", "663601460 엑사드캡슐/1캡셀"]


def test_code_and_name_match_suppresses_sibling_products():
    out = find_candidates(LINES, CORE2, edi_index=EDI)
    labels = {v: l for _, v, l in out}
    assert labels["엑사드캡슐(니자티딘)"].startswith("[코드+이름 일치]")
    assert "엑사드정75밀리그램(니자티딘)" not in labels  # 코드로 확정된 제품의 형제 규격은 제안하지 않음
    assert "후로스판정(플로로글루시놀)" not in labels
    assert len(out) == 2


def test_code_only_match_is_flagged_for_name_check():
    out = find_candidates(["663601460 ???"], CORE2, edi_index=EDI)
    assert out[0][2].startswith("[코드만 일치")


def test_misread_digits_fall_back_to_name_and_never_guess_a_code():
    out = find_candidates(["645604600 후로스판디정/1정"], CORE2, edi_index=EDI)  # 90 -> 00 오인식
    assert [v for _, v, _ in out] == ["후로스판디정(플로로글루시놀)"]
    assert out[0][2].startswith("[이름 일치]")


def test_ten_digit_numbers_are_not_treated_as_codes():
    assert find_candidates(["6456046901"], CORE2, edi_index=EDI) == []


# 실제 처방전을 easyocr 로 읽은 원문 (넷째 줄 누락, 오인식 포함)
REAL_OCR = ["1회", "1일", "총", "처 방 의 약 품 의 명 칭", "투여량 | 투여횟수 | 투약일수",
            "645604690 후로스판디정 / 1정", "663601460 액사드컵슐/ |갑실", "필요시",
            "641607171 스타넥현탁액( 내복) /2Om", "포"]
EDI4 = {"645604690": ["후로스판디정(플로로글루시놀)"], "655605380": ["바이오탑하이포르테캡슐"],
        "663601460": ["엑사드캡슐(니자티딘)"], "641607171": ["스타빅현탁액(디옥타헤드랄스멕타이트)"]}
CORE4 = {product_core(n): [n] for names in EDI4.values() for n in names}


def test_real_ocr_text_codes_rescue_misread_names():
    labels = {v: l for _, v, l in find_candidates(REAL_OCR, CORE4, edi_index=EDI4)}
    assert labels["후로스판디정(플로로글루시놀)"].startswith("[코드+이름 일치]")
    # 이름이 오인식돼도 코드가 맞으면 검출
    assert labels["엑사드캡슐(니자티딘)"].startswith("[코드 일치, 이름은 비슷하게")
    assert labels["스타빅현탁액(디옥타헤드랄스멕타이트)"].startswith("[코드 일치, 이름은 비슷하게")
    # 통째로 누락된 줄은 후보에 없음 -> '처방전 약 개수' 확인 필요
    assert "바이오탑하이포르테캡슐" not in labels and len(labels) == 3


def test_unmatched_codes_reports_misread_numbers():
    assert unmatched_codes(["645604600 후로스판디정", "663601460 x"], EDI4) == ["645604600"]


def test_merge_detections_dedupes_and_keeps_best_confidence():
    a = [("645604690 후로스판디정", 0.4), ("필요시", 0.9)]
    b = [("645604690 후로스판디정", 0.8), ("포", 0.02)]
    out = merge_detections([a, b], min_conf=0.05)
    assert out == [("645604690 후로스판디정", 0.8), ("필요시", 0.9)]  # 순서 유지, 높은 신뢰도, 극저신뢰 제외


def test_preprocess_upscales_and_keeps_grayscale():
    from PIL import Image
    g = preprocess(Image.new("RGB", (1000, 300), "white"))
    assert g.mode == "L" and g.size[0] >= 2000
