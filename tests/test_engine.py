"""합성 데이터로 build -> store -> engine 전체 흐름을 검증한다 (실데이터 불필요)."""
from pathlib import Path

import pandas as pd
import pytest

from apphelpers import page_text

from build_db import build
from src.normalize import SYNONYMS
from src.engine import analyze
from src.store import DataStore


@pytest.fixture(scope="module")
def store(tmp_path_factory):
    orig_synonyms = dict(SYNONYMS)  # build 가 전역 동의어를 바꾸므로 끝나면 복원
    d = tmp_path_factory.mktemp("raw")
    pd.DataFrame({
        "ITEM_SEQ": [str(i) for i in range(1, 19)],
        "ITEM_NAME": ["엑스정", "와이정", "엑스큐복합정", "엑스신정", "제트정", "모름정", "엑스정2",
                    "에이비정", "불일치정", "취소정", "엠정", "엠2정", "엠3정", "시노정",
                    "가나정(에이드럭)", "다라정(에이드럭)", "마바정(브랜드전용)", "사아정(브랜드전용)"],
        "ENTP_NAME": ["가사"] * 14 + ["갑제약", "을제약", "병제약", "병제약"],
        # 허가정보 API 필드 (영문 성분, 개수, 허가 상태)
        "ITEM_INGR_NAME": ["Xdrug/Yextra", "", "", "", "", "", "", "Drug-A/Drug-B Hydrochloride", "Drug-C/Drug-D", "Drug-Z",
                           "Drug-M Weirdform", "Drug-M Weirdform", "Drug-M/Drug-N", "Synonym-X",
                           "Drug-A1", "Drug-A1", "Drug-B1", "Drug-B1"],
        "ITEM_INGR_CNT": ["2", "", "", "", "", "", "", "2", "3", "1", "1", "1", "2", "1", "1", "1", "1", "1"],
        "CANCEL_NAME": ["정상"] * 9 + ["취소"] + ["정상"] * 8,
        "EDI_CODE": ["111111111,222222222"] + [""] * 17,
        "PRDUCT_TYPE": ["[01240]분류엑스", "[01100]분류와이"] + [""] * 16,
    }).to_csv(d / "item.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({
        "ITEM_SEQ": ["1", "2", "3", "3", "4", "5", "7"],
        "MTRAL_NM": ["엑스", "와이", "엑스", "큐큐", "엑스염산염", "제트제트", "엑스"],
    }).to_csv(d / "ing.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({"ko": ["큐큐", "제트제트"], "en": ["drug-q", "drug-z"]}).to_csv(d / "manual.csv", index=False, encoding="utf-8-sig")
    # DUR: x <-> y 금기 (제품명이 item 목록과 일치해야 확정)
    dur = pd.DataFrame({
        "성분명A": ["drug-x hydrochloride (as drug-x)", "drug-m", "drug-m", "drug-n"],
        "제품명A": ["엑스정_(10mg)", "엠정_(1mg)", "엠3정_(1mg)", "엔정_(1mg)"],
        "성분명B": ["drug-y"] * 4, "제품명B": ["와이정_(5mg)"] * 4,
        "금기사유": ["심각한 부작용 위험", "테스트 사유", "테스트 사유", "엔 사유"],
        "비고": ["48시간 이내 병용금기", "", "", ""],
        "고시번호": ["20200001", "20200002", "20200002", "20200003"],
        "고시적용일": ["2020-01-01", "2020-02-01", "2020-02-01", "2020-03-01"],
    })
    dur.to_csv(d / "dur.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({
        "Drug 1": ["Drug-Z", "drug-y"], "Drug 2": ["drug-y", "Drug-Q"],
        "Interaction Description": ["Z may increase Y", "Y may decrease Q"],
    }).to_csv(d / "ddi.csv", index=False)
    pd.DataFrame({"from": ["synonym-x"], "to": ["drug-y"], "note": ["테스트"]}).to_csv(d / "syn.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame({
        "itemSeq": ["1"],
        "efcyQesitm": ["<p>이 약은 &lt;통증&gt; 완화에 사용합니다.</p>"],
        "useMethodQesitm": ["1일 3회<br/>식후 복용"],
        "atpnQesitm": [""], "intrcQesitm": [""], "seQesitm": [""],
        "depositMethodQesitm": ["실온 보관"], "itemImage": [""],
    }).to_csv(d / "easy.csv", index=False, encoding="utf-8-sig")
    out = d / "processed"
    build(d / "item.csv", d / "dur.csv", d / "ddi.csv", out, ingredients_path=d / "ing.csv",
          manual_path=d / "manual.csv", synonyms_path=d / "syn.csv", easy_path=d / "easy.csv")
    yield DataStore(out)
    SYNONYMS.clear()
    SYNONYMS.update(orig_synonyms)


def drug(store, name):
    return store.resolve_product(name)


def test_build_mapping_sources(store):
    p = store.products.set_index("ITEM_NAME")
    assert p.loc["엑스정", "MAP_SOURCE"] == "dur_exact" and p.loc["엑스정", "INGR_KEY"] == "drug-x"
    assert p.loc["엑스신정", "MAP_SOURCE"] == "api_ingredients" and p.loc["엑스신정", "INGR_KEY"] == "drug-x"  # 염산염 제거 후 사전 조회
    assert p.loc["엑스큐복합정", "INGR_KEY"] == "drug-q+drug-x"  # 복합제 성분 유지
    assert p.loc["모름정", "INGR_KEY"] == "" and p.loc["모름정", "MAP_SOURCE"] == "unmapped"


def test_dur_exact_with_note_and_symmetry(store):
    for a, b in [("엑스정", "와이정"), ("와이정", "엑스정")]:
        r = analyze(store, [drug(store, a), drug(store, b)])
        assert r.overall == "contraindicated"
        f = r.of_kind("dur")[0]
        assert f.note == "48시간 이내 병용금기" and f.notice_no == "20200001"


def test_combo_containing_forbidden_component_is_flagged(store):
    r = analyze(store, [drug(store, "엑스큐복합정"), drug(store, "와이정")])
    assert r.count("dur") == 0 and r.count("dur_possible") == 1
    assert r.overall == "warning"


def test_duplicate_ingredient(store):
    r = analyze(store, [drug(store, "엑스정"), drug(store, "엑스정2")])
    assert r.count("duplicate") == 1


def test_unresolved_drug_is_reported_never_safe(store):
    r = analyze(store, [drug(store, "엑스정"), drug(store, "모름정")])
    assert [d.label for d in r.unresolved] == ["모름정"]
    assert r.overall == "caution"  # none_found 가 아니다
    assert "안전" not in r.overall_text.replace("안전을 의미하지", "")


def test_none_found_text_never_claims_safety(store):
    r = analyze(store, [drug(store, "엑스정"), drug(store, "제트정")])
    assert r.overall == "none_found"
    assert "안전을 의미하지는 않습니다" in r.overall_text


def test_drugbank_both_directions_and_case(store):
    r = analyze(store, [drug(store, "제트정"), drug(store, "와이정")])
    f = r.of_kind("drugbank")[0]
    assert f.details[0][2] == "Z may increase Y"
    r2 = analyze(store, [drug(store, "와이정"), store.resolve_ingredient("drug-q")])
    assert r2.of_kind("drugbank")[0].details[0][2] == "Y may decrease Q"


def test_no_substring_false_positive(store):
    r = analyze(store, [store.resolve_ingredient("ol"), store.resolve_ingredient("in")])
    assert r.findings == [] and r.overall == "none_found"


def test_same_drug_selected_twice_counts_once(store):
    r = analyze(store, [drug(store, "엑스정"), drug(store, "엑스정"), drug(store, "와이정")])
    assert r.ignored_duplicates == ["엑스정"] and r.count("dur") == 1


def test_report_has_no_score(store):
    r = analyze(store, [drug(store, "엑스정"), drug(store, "와이정")])
    assert not hasattr(r, "score") and not hasattr(r, "risk_score")


def test_api_english_ingredients_are_used_and_normalized(store):
    p = store.products.set_index("ITEM_NAME")
    assert p.loc["에이비정", "MAP_SOURCE"] == "api_english"
    assert p.loc["에이비정", "INGR_KEY"] == "drug-a+drug-b"  # 슬래시 -> 복합제, 염 제거


def test_api_count_mismatch_is_not_guessed(store):
    p = store.products.set_index("ITEM_NAME")
    assert p.loc["불일치정", "MAP_SOURCE"] == "count_mismatch" and p.loc["불일치정", "INGR_KEY"] == ""
    r = analyze(store, [drug(store, "불일치정"), drug(store, "와이정")])
    assert [d.label for d in r.unresolved] == ["불일치정"]


def test_dur_key_wins_over_api_english_and_mismatch_is_counted(store):
    assert store.products.set_index("ITEM_NAME").loc["엑스정", "INGR_KEY"] == "drug-x"  # 성분 수가 달라 별칭 불가
    assert store.info["api_dur_mismatch"] >= 1


def test_canceled_products_hidden_from_search_but_resolvable(store):
    assert not [h for h in store.search("취소정") if h.kind == "product"]
    assert [h for h in store.search("취소정", include_export=True) if h.kind == "product"]
    assert drug(store, "취소정").ingr_key == "drug-z"


def test_diagnostics_written(store):
    import pandas as pd
    d = store.dir / "diagnostics"
    mm = pd.read_csv(d / "key_mismatch.csv")
    assert {"dur_key", "api_key", "products", "example_item"} <= set(mm.columns)
    assert ((mm.dur_key == "drug-x") & (mm.api_key == "xdrug+yextra")).any()
    un = pd.read_csv(d / "unresolved_products.csv")
    assert set(["불일치정", "모름정"]) <= set(un["ITEM_NAME"])
    um = pd.read_csv(store.dir / "unmatched_components.csv")
    assert "products" in um.columns


def test_alias_learned_from_dur_matched_product_is_applied_to_others(store):
    import pandas as pd
    la = pd.read_csv(store.dir / "diagnostics" / "learned_alias.csv")
    assert ((la.api_component == "drug-m weirdform") & (la.dur_component == "drug-m")).any()
    p = store.products.set_index("ITEM_NAME")
    # 별칭 덕분에 DUR 목록에 없는 '엠2정'도 금기 검출
    assert p.loc["엠2정", "INGR_KEY"] == "drug-m" and p.loc["엠2정", "MAP_SOURCE"] == "api_english"
    r = analyze(store, [drug(store, "엠2정"), drug(store, "와이정")])
    assert r.overall == "contraindicated"


def test_both_notations_are_kept_when_dur_and_api_disagree(store):
    p = store.products.set_index("ITEM_NAME")
    assert p.loc["엠3정", "INGR_KEY"] == "drug-m"  # DUR 표기
    assert p.loc["엠3정", "ALT_KEY"] == "drug-m+drug-n"  # 허가정보 표기(DUR 에는 없는 성분 포함)
    d = drug(store, "엠3정")
    assert "drug-n" in d.components and d.alt_keys == ("drug-m+drug-n",)
    r = analyze(store, [d, drug(store, "와이정")])
    assert r.count("dur") == 1  # m × y : 정확 일치
    assert r.count("dur_possible") == 1  # n × y : DUR 표기에서 빠졌던 성분도 놓치지 않음
    assert r.overall == "contraindicated"


def test_manual_synonyms_are_applied_in_build(store):
    assert store.products.set_index("ITEM_NAME").loc["시노정", "INGR_KEY"] == "drug-y"


def test_drug_info_is_cleaned_and_joined_by_item_seq(store):
    det = store.product_detail("엑스정")
    assert det["info"]["efcy"] == "이 약은 <통증> 완화에 사용합니다."  # 태그 제거, 본문의 꺾쇠는 보존
    assert det["info"]["use_method"] == "1일 3회\n식후 복용"
    assert det["product"]["ENTP_NAME"] == "가사"
    assert store.product_detail("와이정")["info"] is None  # e약은요에 없는 제품
    assert store.product_detail("없는약") is None


def test_ko_names_reverse_lookup(store):
    assert "큐큐" in store.ko_names("drug-q")


def test_app_shows_drug_info_tab(store, monkeypatch):
    pytest.importorskip("streamlit")
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PROCESSED_DIR", str(store.dir))
    st.cache_resource.clear()
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "app.py"), default_timeout=120)
    at.session_state["selected"] = [
        {"kind": "product", "value": "엑스정", "label": "엑스정"},
        {"kind": "product", "value": "와이정", "label": "와이정"},
    ]
    at.run()
    assert not at.exception
    text = page_text(at)
    assert "통증" in text  # 효능 섹션
    assert "e약은요 자료가 없습니다" in text  # 정보 없는 제품 안내
    st.cache_resource.clear()


def test_edi_code_index(store):
    assert store.edi_index["111111111"] == ["엑스정"] and store.edi_index["222222222"] == ["엑스정"]
    assert "" not in store.edi_index


def test_app_warns_when_fewer_drugs_than_prescription(store, monkeypatch):
    pytest.importorskip("streamlit")
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PROCESSED_DIR", str(store.dir))
    st.cache_resource.clear()
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "app.py"), default_timeout=120)
    at.session_state["selected"] = [
        {"kind": "product", "value": "엑스정", "label": "엑스정"},
        {"kind": "product", "value": "와이정", "label": "와이정"},
    ]
    at.session_state["expected_count"] = 4
    at.run()
    assert not at.exception
    warns = page_text(at)
    assert "2개가 아직 추가되지 않았습니다" in warns
    assert "이 결과는 불완전합니다" in warns
    st.cache_resource.clear()


def test_app_ocr_is_off_by_default_and_summary_is_shown(store, monkeypatch):
    pytest.importorskip("streamlit")
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PROCESSED_DIR", str(store.dir))
    st.cache_resource.clear()
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "app.py"), default_timeout=120)
    at.session_state["selected"] = [
        {"kind": "product", "value": "엑스정", "label": "엑스정"},
        {"kind": "product", "value": "와이정", "label": "와이정"},
    ]
    at.run()
    assert not at.exception
    ocr_box = [c for c in at.sidebar.checkbox if "처방전 사진" in c.label]
    assert ocr_box and ocr_box[0].value is False  # 기본 꺼짐
    assert not any("처방전/약봉투 사진" in x.label for x in at.expander)  # OCR 영역이 보이지 않음
    md = page_text(at)
    assert "핵심 요약" in md and "관계도" in md and 'class="pp-pill pp-p-contraindicated"' in md
    st.cache_resource.clear()


def test_demo_loader_only_offers_available_examples_and_loads_them(store, monkeypatch):
    pytest.importorskip("streamlit")
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from src import demos

    monkeypatch.setattr(demos, "DEMOS", {"가능한 예시": ["엑스정", "와이정"], "없는 제품 포함": ["엑스정", "존재하지않는약"]})
    monkeypatch.setenv("PROCESSED_DIR", str(store.dir))
    st.cache_resource.clear()
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "app.py"), default_timeout=120).run()
    assert not at.exception
    box = [s for s in at.sidebar.selectbox if s.label == "예시 조합"][0]
    assert box.options == ["가능한 예시"]  # 제품 목록에 없는 제품이 든 예시는 숨김
    [b for b in at.sidebar.button if b.label == "예시 불러오기"][0].click().run()
    assert not at.exception
    assert [s["value"] for s in at.session_state["selected"]] == ["엑스정", "와이정"]
    assert "병용금기 발견" in page_text(at)
    [b for b in at.sidebar.button if b.label == "선택 목록 비우기"][0].click().run()
    assert at.session_state["selected"] == []
    st.cache_resource.clear()


def test_korean_ingredient_learned_from_names_needs_two_manufacturers(store):
    assert store.ko_dict.get("에이드럭") == "drug-a1"  # 서로 다른 제조사 2곳의 '제품명(성분)' 괄호에서 학습
    assert "브랜드전용" not in store.ko_dict  # 한 제조사(병제약)에서만 쓰인 표기는 성분명으로 보지 않음
    assert store.search("에이드")[0].value == "drug-a1"  # 한글 성분명으로 검색하면 성분이 먼저 나옴


def test_data_basis_dates_are_exposed(store):
    assert store.info["dur_latest"] == "2020-03-01"  # DUR 고시 적용일 중 최신
    assert store.dur_latest == "2020-03-01"


def _app(store, monkeypatch, selected=None, extra_env=None):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("PROCESSED_DIR", str(store.dir))
    for k, v in (extra_env or {}).items():
        monkeypatch.setenv(k, v)
    st.cache_resource.clear()
    root = Path(__file__).resolve().parent.parent
    at = AppTest.from_file(str(root / "app.py"), default_timeout=120)
    if selected:
        at.session_state["selected"] = [{"kind": "product", "value": n, "label": n} for n in selected]
    return at


def test_easy_mode_is_a_different_layout_not_just_different_words(store, monkeypatch):
    at = _app(store, monkeypatch, ["엑스정", "와이정"])
    at.run()
    detailed = page_text(at)
    assert "병용금기 발견" in detailed and "pp-stats" in detailed and len(at.tabs) == 5  # 기본은 약사용(표·탭·통계)
    [r for r in at.sidebar.radio if r.label == "설명 방식"][0].set_value("쉬운 설명").run()
    assert not at.exception
    text = page_text(at)
    # 배너와 카드는 쉬운 말
    assert "함께 먹으면 안 되는 약이 들어 있어요" in text
    assert "함께 먹으면 안 된다고 식약처가 정했어요" in text
    # 조건부 비고는 쉬운 모드에서도 빠지지 않는다
    assert "48시간 이내 병용금기" in text
    # 약 분류가 이름 옆에 표시 (코드 접두사 제거)
    assert "분류엑스" in text and "분류와이" in text and "[01240]" not in text
    # 표·통계·탭·관계도·성분키 같은 기술적 요소는 나오지 않는다
    assert "pp-stats" not in text and "관계도" not in text and len(at.tabs) == 0
    assert "고시 2020" not in text  # 고시 번호 같은 근거 번호는 쉬운 보기에 나오지 않는다
    # 약사에게 보여 줄 질문 생성
    assert "약사에게 이렇게 물어보세요" in text
    codes = [c.value for c in at.code]
    assert codes
    assert "엑스정" in codes[0] and "와이정" in codes[0] and "함께 써도 되는지" in codes[0]
    # 사유 원문은 접힌 곳에 그대로 전달된다
    assert any("왜 그런가요" in e.label for e in at.expander)
    assert any("심각한 부작용 위험" in m.value for m in at.markdown)
    import streamlit as st
    st.cache_resource.clear()


def test_easy_mode_does_not_force_large_font(store, monkeypatch):
    """글자 크기는 '글자 크게' 체크박스로 따로 고른다 (쉬운 설명이 자동으로 켜지 않는다)."""
    at = _app(store, monkeypatch, ["엑스정", "와이정"])
    at.run()
    [r for r in at.sidebar.radio if r.label == "설명 방식"][0].set_value("쉬운 설명").run()
    assert not any("font-size: 118%" in m.value for m in at.markdown)
    [c for c in at.sidebar.checkbox if c.label == "글자 크게"][0].check().run()
    assert any("font-size: 118%" in m.value for m in at.markdown)
    import streamlit as st
    st.cache_resource.clear()


def test_easy_mode_question_lists_unresolved_and_duplicates(store, monkeypatch):
    at = _app(store, monkeypatch, ["엑스정", "엑스정2", "모름정"])
    at.run()
    [r for r in at.sidebar.radio if r.label == "설명 방식"][0].set_value("쉬운 설명").run()
    assert not at.exception
    q = [c.value for c in at.code][0]
    assert "같은 성분이 들어 있는데" in q  # 성분 중복
    assert "모름정은(는) 어떤 약인지" in q or "모름정" in q  # 확인 불가 약
    assert "확인하지 못한 약" in page_text(at)
    assert "drug-x" not in page_text(at)  # 영문 성분키는 쉬운 보기에 나오지 않는다
    import streamlit as st
    st.cache_resource.clear()


def test_large_font_toggle_injects_css(store, monkeypatch):
    at = _app(store, monkeypatch, ["엑스정", "와이정"])
    at.run()
    assert "html { font-size: 118%" not in page_text(at)
    [c for c in at.sidebar.checkbox if c.label == "글자 크게"][0].check().run()
    assert any("font-size: 118%" in m.value for m in at.markdown)
    import streamlit as st
    st.cache_resource.clear()


def test_data_basis_date_is_shown(store, monkeypatch):
    at = _app(store, monkeypatch, ["엑스정", "와이정"])
    at.run()
    text = page_text(at)
    assert "DUR 고시 최신 적용일 2020-03-01" in text
    import streamlit as st
    st.cache_resource.clear()


def test_feedback_form_saves_report_with_consent_only(store, monkeypatch, tmp_path):
    from src import feedback
    at = _app(store, monkeypatch, ["엑스정", "와이정"], {"FEEDBACK_DIR": str(tmp_path)})
    at.run()
    sb = at.sidebar
    [t for t in sb.text_area if t.label == "내용"][0].input("엑스정 결과가 이상해요")
    sb.button[[b.label for b in sb.button].index("보내기")].click().run()
    assert not at.exception
    rep = feedback.load_reports(tmp_path)[0]
    assert rep["message"] == "엑스정 결과가 이상해요"
    assert "drugs" not in rep["context"]  # 동의하지 않았으면 약 목록은 저장하지 않는다
    assert rep["context"]["result"]["overall"] == "contraindicated"  # 결과 요약(약 이름 없음)은 참고용으로 포함
    import streamlit as st
    st.cache_resource.clear()


def test_unexpected_error_shows_friendly_notice_and_report_form(store, monkeypatch, tmp_path):
    import src.engine as engine
    monkeypatch.setattr(engine, "analyze", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("일부러 낸 오류")))
    at = _app(store, monkeypatch, ["엑스정", "와이정"], {"FEEDBACK_DIR": str(tmp_path)})
    at.run()
    assert not at.exception  # 빨간 스택트레이스 화면이 아니라
    assert "예상치 못한 오류가 발생했습니다" in page_text(at)  # 안내 화면
    assert any(f.label == "내용" for f in at.text_area)  # 신고 양식이 나옴
    import streamlit as st
    st.cache_resource.clear()


def test_error_details_are_saved_only_when_user_agrees(store, monkeypatch, tmp_path):
    from src import feedback
    import src.engine as engine
    monkeypatch.setattr(engine, "analyze", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("비밀 오류 문구")))
    at = _app(store, monkeypatch, ["엑스정", "와이정"], {"FEEDBACK_DIR": str(tmp_path)})
    at.run()
    [t for t in at.text_area if t.label == "내용"][0].input("오류가 났어요")
    at.button[[b.label for b in at.button].index("보내기")].click().run()
    rep = feedback.load_reports(tmp_path)[0]
    assert "error" not in rep["context"] and "drugs" not in rep["context"]  # 동의 전에는 오류 내용도 약 이름도 저장 안 함
    import streamlit as st
    st.cache_resource.clear()


def test_category_of_strips_code_prefix(store):
    assert store.category_of("엑스정") == "분류엑스"
    assert store.category_of("제트정") == ""  # 분류가 비어 있으면 빈 문자열
    assert store.category_of("없는약") == ""
