"""다제복용 약물 상호작용 점검기 (Streamlit). 실행: streamlit run app.py"""
import os
import traceback
import urllib.parse

import streamlit as st

from src import ocr
from src.engine import analyze
from src import demos, feedback, plain, theme
from src.report import LEVEL_LABEL, build_pdf, font_is_embedded
from src.store import DataStore, DataStoreError
from src.viz import SEV_RANK, build_dot, pair_severities, short_name

PROCESSED_DIR = os.environ.get("PROCESSED_DIR", "data/processed")

st.set_page_config(page_title="다제복용 약물 상호작용 점검기", page_icon="💊", layout="wide")
st.markdown(theme.style_tag(), unsafe_allow_html=True)


def html(s):
    st.markdown(s, unsafe_allow_html=True)


SHORT_DISCLAIMER = ("참고용 도구입니다. 결과가 없어도 안전을 뜻하지 않으며, 복용 중인 약은 임의로 바꾸지 말고 "
                    "의사·약사와 상담하세요. 성분을 확인하지 못한 약은 검사에서 제외됩니다.")


@st.cache_resource(show_spinner="데이터를 불러오는 중...")
def load_store():
    return DataStore(PROCESSED_DIR)


try:
    store = load_store()
except DataStoreError as e:
    st.error(str(e))
    st.stop()

if "selected" not in st.session_state:
    st.session_state.selected = []  # [{kind, value, label}]
if "ocr_candidates" not in st.session_state:
    st.session_state.ocr_candidates = []


def add_selected(kind, value, label):
    if not any(s["kind"] == kind and s["value"] == value for s in st.session_state.selected):
        st.session_state.selected.append({"kind": kind, "value": value, "label": label})


def to_drug(sel):
    return store.resolve_ingredient(sel["value"]) if sel["kind"] == "ingredient" else store.resolve_product(sel["value"])


FEEDBACK_DIR = os.environ.get("FEEDBACK_DIR", "data/feedback")
FEEDBACK_EMAIL = os.environ.get("FEEDBACK_EMAIL", "").strip()


def render_feedback_form(form_key, error_text=None):
    """문제 신고 양식 (이 PC에만 저장, 약 목록은 동의 시에만 포함)."""
    with st.form(form_key, clear_on_submit=True):
        kind = st.selectbox("어떤 문제인가요?", feedback.KINDS, index=0 if error_text else 1)
        message = st.text_area("내용", max_chars=feedback.MAX_MESSAGE, height=110,
                               placeholder="어떤 약을 골랐고, 무엇이 이상했는지 적어 주세요.")
        contact = st.text_input("연락처 (선택)", placeholder="답변이 필요하면 이메일/전화번호를 적어 주세요")
        include = st.checkbox("오류 정보와 지금 선택한 약 목록도 함께 보내기" if error_text else "지금 선택한 약 목록도 함께 보내기",
                              value=False,
                              help="약 이름은 건강 정보가 될 수 있어요. 체크하지 않으면 약 이름과 오류 내용은 저장하지 않습니다.")
        sent = st.form_submit_button("보내기", use_container_width=True)
    if sent:
        try:
            ctx = feedback.build_context(st.session_state.get("last_summary"), st.session_state.get("last_labels"),
                                         include, error_text if include else None)
            rid = feedback.save_report(FEEDBACK_DIR, kind, message, contact, ctx,
                                       {"data_built": store.info.get("built_at"), "dur_latest": store.dur_latest})
            html(theme.notice(f"접수되었습니다. (접수번호 {rid}) 소중한 의견 감사합니다.", "info"))
            if FEEDBACK_EMAIL:
                mail = feedback.build_mailto(FEEDBACK_EMAIL, f"[약물 점검기] {kind}", f"{message}\n\n접수번호: {rid}")
                st.link_button("이메일로도 보내기", mail, use_container_width=True)
        except ValueError as e:
            html(theme.notice(str(e), "warn"))
        except Exception as e:  # 저장 실패해도 앱은 계속 동작
            html(theme.notice(f"저장하지 못했습니다: {e}", "danger"))


def load_demo(names):
    """예시 조합으로 선택 목록을 바꾼다."""
    st.session_state.selected = [{"kind": "product", "value": n, "label": n} for n in names]
    st.session_state.expected_count = 0


def clear_selected():
    st.session_state.selected = []


# --- 사이드바 ---
with st.sidebar:
    st.markdown("### 데이터 현황")
    info = store.info
    total = info.get("products", len(store.products))
    resolved_n = info.get("products_resolved", 0)
    html(theme.sidebar_stats(
        [("제품", f"{total:,}개"), ("성분 확인됨", f"{resolved_n:,}개"),
         ("DUR 병용금기 쌍", f"{info.get('dur_pairs', 0):,}개"), ("DrugBank 참고 쌍", f"{info.get('drugbank_pairs', 0):,}개"),
         ("DUR 고시 기준", info.get("dur_latest") or "-")],
        ratio=(resolved_n / total) if total else None))
    st.caption(f"데이터 빌드: {info.get('built_at', '-')}")
    st.markdown("### 보기 설정")
    easy_mode = st.radio("설명 방식", ["약사용 (상세)", "쉬운 설명"], help="쉬운 설명은 전문 용어와 표를 줄이고, 해야 할 일과 약사에게 물어볼 말만 크게 보여줍니다.") == "쉬운 설명"
    if st.checkbox("글자 크게", value=False):
        html(theme.large_font_style())
    include_export = st.checkbox("수출용/허가취소 품목도 검색", value=False)
    enable_ocr = st.checkbox("🧪 실험 기능: 처방전 사진 인식", value=False,
                             help="여러 병원 서식으로 검증되지 않았습니다. 인식이 빠뜨린 약은 분석에서 빠집니다.")
    st.caption("성분을 확인하지 못한 약은 '안전'이 아니라 '확인 불가'로 표시되며 검사에서 제외됩니다.")
    st.divider()
    with st.expander("문제 신고 · 의견 보내기"):
        render_feedback_form("fb_side")
    st.divider()
    st.markdown("### 시연용")
    available = {k: v for k, v in demos.DEMOS.items() if all(store.product_detail(n) for n in v)}
    if available:
        demo_choice = st.selectbox("예시 조합", list(available), label_visibility="collapsed")
        st.button("예시 불러오기", on_click=load_demo, args=(available[demo_choice],), use_container_width=True)
    st.button("선택 목록 비우기", on_click=clear_selected, use_container_width=True)

html(theme.hero("다제복용 약물 상호작용 점검기", "식약처 DUR 병용금기와 DrugBank 참고 자료로, 함께 먹는 약의 위험 조합을 점검합니다"))
html(theme.notice(SHORT_DISCLAIMER, "warn"))

# --- 약 추가 ---
html(theme.section(1, "약 추가", "이름이나 성분명으로 검색해서 하나씩 추가하세요"))
with st.container(border=True):
    col_q, col_pick = st.columns([1, 2])
    with col_q:
        query = st.text_input("약 이름 또는 성분명 검색", placeholder="예: 타이레놀, 와파린, warfarin")
    hits = store.search(query, limit=40, include_export=include_export) if query.strip() else []
    with col_pick:
        if hits:
            idx = st.selectbox("검색 결과 (✅ 성분 확인됨 / ⚠️ 성분 미확인)", range(len(hits)),
                               format_func=lambda i: hits[i].label)
            if st.button("추가", type="primary", icon=":material/add:"):
                h = hits[idx]
                add_selected(h.kind, h.value, h.label)
                st.rerun()
        elif query.strip():
            html(theme.notice("검색 결과가 없습니다. 다른 이름이나 성분명으로 찾아보세요.", "gray"))
        else:
            st.caption("검색어를 입력하면 결과가 여기에 나타납니다.")

if enable_ocr:
    with st.expander("📸 처방전/약봉투 사진으로 후보 찾기 (실험 기능)", expanded=True):
        if not ocr.is_available():
            html(theme.notice("OCR 은 선택 기능입니다. 사용하려면 `pip install -r requirements-ocr.txt` 후 다시 실행하세요.", "info"))
        else:
            st.caption("인식 결과는 '후보'입니다. 처방전 약 목록과 직접 대조한 뒤 추가하세요. "
                       "처방전의 9자리 제품코드가 일치하면 가장 정확합니다. "
                       "사진에는 이름·주민번호 등이 있으니 약 목록 부분만 잘라서 올리면 인식도 더 잘 됩니다.")
            tab_up, tab_cam = st.tabs(["📁 사진 올리기", "📷 카메라 촬영"])
            with tab_up:
                up = st.file_uploader("사진 선택 (JPG/PNG)", type=["jpg", "jpeg", "png"])
            with tab_cam:
                cam = st.camera_input("약 목록이 잘 보이게 촬영")
            image_file = up or cam
            if image_file is not None and st.button("인식 시작"):
                with st.spinner("글자를 읽는 중..."):
                    dets = ocr.read_detections(image_file.getvalue())
                    texts = [t for t, _ in dets]
                    st.session_state.ocr_dets = dets
                    st.session_state.ocr_texts = texts
                    st.session_state.ocr_candidates = ocr.find_candidates(
                        texts, store.core_index, store.ko_dict, edi_index=store.edi_index)
                if not st.session_state.ocr_candidates:
                    html(theme.notice("후보를 찾지 못했습니다. 아래 인식된 글자를 확인하거나 검색창에서 직접 추가해 주세요.", "warn"))
            if st.session_state.get("ocr_dets"):
                with st.expander("인식된 글자 원문 보기 (틀리게 읽힌 곳 확인용)"):
                    st.text("\n".join(f"{'⚠ ' if c < 0.5 else '  '}{t}   ({c:.0%})" for t, c in st.session_state.ocr_dets))
                    bad = ocr.unmatched_codes(st.session_state.ocr_texts, store.edi_index)
                    if bad:
                        html(theme.notice("제품 코드와 맞지 않는 9자리 번호: " + ", ".join(bad)
                                          + "  (숫자가 틀리게 읽혔거나, 목록에 없는 제품일 수 있습니다.)", "warn"))
                    st.caption("⚠ 표시는 신뢰도가 낮은 조각입니다. 처방전의 **약 개수**와 후보 개수를 꼭 비교하세요. "
                               "글자가 통째로 안 읽힌 줄은 후보에 나타나지 않습니다.")
            cands = st.session_state.ocr_candidates
            if cands:
                default = [i for i, c in enumerate(cands) if c[2].startswith(("[코드+이름 일치]", "[코드 일치,"))]
                picked = st.multiselect("후보 (추가할 항목을 선택)", range(len(cands)), default=default,
                                        format_func=lambda i: cands[i][2])
                st.caption("코드가 일치하고 이름도 (비슷하게) 읽힌 항목은 미리 선택되어 있습니다. [코드만 일치]나 [이름 일치]는 이름/규격을 확인하고 직접 선택하세요.")
                if st.button("선택한 후보 추가") and picked:
                    for i in picked:
                        add_selected(cands[i][0], cands[i][1], cands[i][2])
                    st.rerun()

# --- 선택 목록 ---
html(theme.section(2, "선택한 약", "처방전 약 개수를 적어 두면 빠진 약이 없는지 확인해 드려요"))
col_cnt, _ = st.columns([1, 3])
with col_cnt:
    st.number_input("처방전에 적힌 약 개수 (선택)", min_value=0, max_value=30, step=1, key="expected_count",
                    help="빠진 약이 없는지 확인용입니다. 0 이면 확인하지 않습니다.")
expected = st.session_state.get("expected_count", 0)
if not st.session_state.selected:
    html(theme.notice("검색해서 약을 2개 이상 추가하세요.", "info"))
for i, sel in enumerate(list(st.session_state.selected)):
    d = to_drug(sel)
    status = "unk" if not d.resolved else ("est" if d.map_source == "paren_dict" else "ok")
    with st.container(key=f"drugrow_{i}"):
        c1, c2 = st.columns([14, 1], vertical_alignment="center")
        c1.markdown(theme.drug_row(d.label, d.ingr_key, status, d.entp,
                                   category=store.category_of(d.label) if easy_mode and d.kind == "product" else ("" if easy_mode else None)),
                    unsafe_allow_html=True)
        if c2.button("", key=f"rm_{i}", icon=":material/close:", help="목록에서 빼기"):
            st.session_state.selected.pop(i)
            st.rerun()

n_selected = len(st.session_state.selected)
incomplete = bool(expected) and n_selected < expected
if incomplete:
    html(theme.notice(f"처방전에는 약이 {expected}개라고 했는데 {expected - n_selected}개가 아직 추가되지 않았습니다. "
                      "빠진 약이 있으면 아래 분석은 불완전합니다.", "warn"))
elif expected and n_selected > expected:
    html(theme.notice(f"처방전 약 개수({expected}개)보다 많이 선택되어 있습니다. 목록을 다시 확인하세요.", "info"))

if n_selected < 2:
    st.stop()


def _clean_name(label):
    return short_name(label)


def question_lines(report):
    """약사에게 보여 줄 질문 만들기 (의학적 판단 없이 확인만 요청)."""
    seen, lines = set(), []

    def add(line):
        if line not in seen:
            seen.add(line)
            lines.append(line)

    for f in report.of_kind("dur"):
        add(f"- {_clean_name(f.drug_a)}와(과) {_clean_name(f.drug_b)}을(를) 함께 써도 되는지, 시간 간격을 두어야 하는지 알려 주세요.")
    for f in report.of_kind("dur_possible"):
        add(f"- {_clean_name(f.drug_a)}와(과) {_clean_name(f.drug_b)}을(를) 함께 써도 되는지 알려 주세요. (복합제 성분 확인이 필요하대요)")
    for f in report.of_kind("duplicate"):
        add(f"- {_clean_name(f.drug_a)}와(과) {_clean_name(f.drug_b)}에 같은 성분이 들어 있는데 함께 먹어도 되는지 알려 주세요.")
    for d in report.unresolved:
        add(f"- {_clean_name(d.label)}은(는) 어떤 약인지, 다른 약과 함께 먹어도 되는지 알려 주세요.")
    if not lines:
        lines.append("- 제가 먹는 약 전체를 함께 먹어도 되는지 확인해 주세요.")
    return lines


def render_easy(report):
    """쉬운 보기: 표·그래프 없이 할 일과 질문 중심 화면."""
    def cat(d):
        return store.category_of(d.label) if d.kind == "product" else ""

    cat_of = {d.label: cat(d) for d in report.drugs}

    dur = report.of_kind("dur")
    if dur:
        html('<div class="pp-panel-title" style="margin-top:6px">함께 먹으면 안 되는 약</div>')
        for f in dur:
            html(theme.easy_pair_card("contraindicated", _clean_name(f.drug_a), cat_of.get(f.drug_a, ""),
                                      _clean_name(f.drug_b), cat_of.get(f.drug_b, ""), plain.LEAD["dur"], f.note))
            with st.expander("왜 그런가요? (식약처 자료 원문)"):
                st.write(f.reason or "-")
                if f.note:
                    st.write(f"조건: {f.note}")

    check = report.of_kind("dur_possible") + report.of_kind("duplicate")
    if check:
        html('<div class="pp-panel-title" style="margin-top:18px">한 번 더 확인할 것</div>')
        for f in check:
            if f.kind == "dur_possible":
                lead = plain.LEAD["dur_possible"]
            else:  # 한글 성분명을 알 때만 이름 표시
                comps = [c.strip() for c in f.title.split(":", 1)[-1].split(",") if c.strip()]
                ko = [(store.ko_names(c) or [None])[0] for c in comps]
                lead = plain.duplicate_lead(ko if ko and all(ko) else None)
            html(theme.easy_pair_card("warning", _clean_name(f.drug_a), cat_of.get(f.drug_a, ""),
                                      _clean_name(f.drug_b), cat_of.get(f.drug_b, ""), lead, f.note))

    if report.unresolved:
        html('<div class="pp-panel-title" style="margin-top:18px">확인하지 못한 약</div>')
        for d in report.unresolved:
            html(theme.unresolved_card(_clean_name(d.label), "성분을 찾지 못해서 검사하지 못했어요.",
                                       lead=plain.LEAD["unresolved"]))

    if not dur and not check and not report.unresolved:
        html(theme.empty("찾아낸 위험 조합이 없어요. 그렇다고 안전하다는 뜻은 아니에요. 자료에 없는 조합일 수 있어요."))

    html('<div class="pp-panel-title" style="margin-top:18px">약사에게 이렇게 물어보세요</div>')
    text = "\n".join(question_lines(report))
    try:
        st.code(text, language=None, wrap_lines=True)  # 복사 버튼으로 복사
    except TypeError:  # 구버전 Streamlit 대응
        st.code(text, language=None)
    st.caption("더 자세한 근거(고시 번호, 성분, 영어 참고 자료)는 사이드바에서 '약사용 (상세)'로 바꾸면 볼 수 있어요.")


try:
    # --- 분석 ---
    html(theme.section(3, "분석 결과"))
    drugs = [to_drug(s) for s in st.session_state.selected]
    report = analyze(store, drugs)
    st.session_state.last_summary = {
        "overall": report.overall,
        "counts": {"dur": report.count("dur"), "dur_possible": report.count("dur_possible"),
                   "duplicate": report.count("duplicate"), "drugbank": report.count("drugbank"),
                   "unresolved": len(report.unresolved)},
    }
    st.session_state.last_labels = [d.label for d in report.drugs]

    if easy_mode:
        b_title, b_text = plain.BANNER[report.overall]
    else:
        b_title, b_text = LEVEL_LABEL[report.overall], report.overall_text
    html(theme.banner(report.overall, b_title, b_text))
    st.caption(f"데이터 기준: DUR 고시 최신 적용일 {store.dur_latest or '-'} · 데이터 빌드 {store.info.get('built_at', '-')}")
    if incomplete:
        html(theme.notice(f"처방전 약 {expected}개 중 {n_selected}개만 분석했습니다. 이 결과는 불완전합니다.", "warn"))
    if report.unresolved:
        html(theme.notice(f"성분을 확인하지 못한 약 {len(report.unresolved)}개는 검사에서 제외되었습니다: "
                          + ", ".join(short_name(d.label) for d in report.unresolved), "warn"))
    if report.ignored_duplicates:
        st.caption("같은 약을 중복 선택해 1개만 분석했습니다: " + ", ".join(report.ignored_duplicates))

    if easy_mode:
        render_easy(report)
    else:
        html(theme.stat_cards([
            ("DUR 병용금기", report.count("dur"), "red"),
            ("복합제 포함 가능성", report.count("dur_possible"), "amber"),
            ("성분 중복", report.count("duplicate"), "amber"),
            ("참고 상호작용", report.count("drugbank"), "info"),
            ("확인 불가 약", len(report.unresolved), "gray"),
        ]))

        # 관계도 + 핵심 요약
        col_graph, col_sum = st.columns([3, 2], gap="large")
        with col_graph:
            with st.container(border=True):
                html('<div class="pp-panel-title">관계도</div>')
                st.graphviz_chart(build_dot(report))
                html('<div class="pp-legend">빨강: DUR 병용금기 · 주황: 확인 필요(복합제 포함/성분 중복) · 파랑 점선: 참고 상호작용 · 회색 점선: 확인 불가</div>')
        with col_sum:
            with st.container(border=True):
                html('<div class="pp-panel-title">핵심 요약</div>')
                sev_pairs = sorted(pair_severities(report).items(), key=lambda kv: -SEV_RANK[kv[1]])
                html(theme.summary_rows([((short_name(a_), short_name(b_)), sev) for (a_, b_), sev in sev_pairs],
                                        [short_name(d.label) for d in report.unresolved]))

        n_dur = report.count("dur") + report.count("dur_possible")
        t0, t1, t2, t3, t4 = st.tabs([
            "약 정보",
            f"DUR 병용금기 ({n_dur})",
            f"성분 중복 ({report.count('duplicate')})",
            f"참고 상호작용 ({report.count('drugbank')})",
            f"확인 불가 ({len(report.unresolved)})",
        ])

        INFO_SECTIONS = [
            ("efcy", "효능·효과", True),
            ("use_method", "사용법", False),
            ("warn", "반드시 알아야 할 주의(경고)", False),
            ("atpn", "사용 전 주의사항", False),
            ("intrc", "다른 약과의 상호작용", False),
            ("se", "이상반응(부작용)", False),
            ("deposit", "보관법", False),
        ]


        def md_escape(text):
            """마크다운 기호 이스케이프."""
            for ch in "\\`*_{}[]<>#|~":
                text = text.replace(ch, "\\" + ch)
            return text.replace("\n", "  \n")


        def fmt_date(s):
            return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 and s.isdigit() else (s or "-")


        def status_badge(d):
            if not d.resolved:
                return theme.badge("성분 확인 불가", "unk")
            return theme.badge("이름 기반 추정", "est") if d.map_source == "paren_dict" else theme.badge("성분 확인", "ok")


        def render_drug_info(sel, d):
            esc = theme.esc
            with st.container(border=True):
                if sel["kind"] == "ingredient":
                    ko = store.ko_names(d.ingr_key)
                    html(f'<div class="pp-f-head"><span class="pp-f-names">{esc(d.label)}</span>{status_badge(d)}</div>')
                    html(theme.kv([("성분(영문)", theme.chip(d.ingr_key)), ("한글명", esc(", ".join(ko)) if ko else "-")]))
                    html(theme.notice("성분으로 직접 선택한 항목이라 제품 정보는 없습니다.", "gray"))
                    return
                det = store.product_detail(sel["value"])
                if det is None:
                    html(theme.notice("제품 목록에서 찾을 수 없습니다.", "warn"))
                    return
                p, info = det["product"], det["info"]
                kind_badge = theme.badge(p["SPCLTY_PBLC"], "gray") if p.get("SPCLTY_PBLC") else ""
                html(f'<div class="pp-f-head"><span class="pp-f-names">{esc(d.label)}</span>{kind_badge}{status_badge(d)}</div>')
                rows = [("제조/수입사", esc(p.get("ENTP_NAME") or "-")), ("분류", esc(p.get("PRDUCT_TYPE") or "-")),
                        ("성분(영문)", theme.chip(d.ingr_key) if d.ingr_key else "확인 불가"),
                        ("허가일", esc(fmt_date(p.get("ITEM_PERMIT_DATE", ""))))]
                if p.get("ITEM_ENG_NAME"):
                    rows.append(("영문명", esc(p["ITEM_ENG_NAME"])))
                html(theme.kv(rows))
                if not store.drug_info:
                    pass  # 안내는 탭 위에서 한 번만 표시
                elif not info:
                    html(theme.notice("이 제품은 e약은요 자료가 없습니다 (전문의약품이거나 공급 실적이 없는 제품일 수 있습니다). "
                                      "복약 정보는 약사에게 확인하세요.", "gray"))
                else:
                    if info.get("image", "").startswith("http"):
                        st.image(info["image"], width=140)
                    for key, title, opened in INFO_SECTIONS:
                        if info.get(key):
                            with st.expander(title, expanded=opened):
                                st.markdown(md_escape(info[key]))


        with t0:
            st.caption("식약처 e약은요(일반의약품 중심)와 허가정보 기준입니다. 복용 전에는 반드시 의사·약사와 상담하세요.")
            if not store.drug_info:
                html(theme.notice("효능·주의사항 데이터가 아직 없습니다. `python scripts/fetch_items.py --what easy` 후 빌드하세요.", "info"))
            for sel in st.session_state.selected:
                render_drug_info(sel, to_drug(sel))

        with t1:
            exact, possible = report.of_kind("dur"), report.of_kind("dur_possible")
            if not exact and not possible:
                html(theme.empty("선택한 약(성분 확인된 약 기준) 사이에서 DUR 병용금기 조합이 발견되지 않았습니다. "
                                 "이것이 안전을 보증하지는 않습니다."))
            for f in exact:
                html(theme.finding_card("contraindicated", f.drug_a, f.drug_b, theme.chips_from_title(f.title),
                                        plain.reason_label(f.reason) if easy_mode else f.reason, f.note,
                                        f"고시 {f.notice_no} · 적용 {f.apply_date}",
                                        lead=plain.LEAD["dur"] if easy_mode else ""))
            if possible:
                html('<div class="pp-panel-title" style="margin-top:18px">복합제에 금기 성분이 포함되어 있을 가능성</div>')
                st.caption("제품의 성분 구성이 DUR 목록의 조합과 정확히 같지는 않지만, 금기 성분이 들어 있어 확인이 필요합니다.")
                for f in possible:
                    html(theme.finding_card("warning", f.drug_a, f.drug_b, theme.chips_from_title(f.title),
                                            plain.reason_label(f.reason) if easy_mode else f.reason, f.note,
                                            f"고시 {f.notice_no} · 적용 {f.apply_date}", pill_text="확인 필요",
                                            lead=plain.LEAD["dur_possible"] if easy_mode else ""))

        with t2:
            dups = report.of_kind("duplicate")
            if not dups:
                html(theme.empty("중복된 성분이 발견되지 않았습니다."))
            for f in dups:
                html(theme.finding_card("warning", f.drug_a, f.drug_b, "", "" if easy_mode else f.reason, "", f.title,
                                        pill_text="성분 중복", lead=plain.duplicate_lead(f.title) if easy_mode else ""))

        with t3:
            st.caption("DrugBank 데이터는 심각도 정보가 없고 영어 원문입니다. 참고용이며 금기 판정 근거로 쓰면 안 됩니다."
                       + (" 이 탭의 내용은 영어 원문 그대로라 어려울 수 있어요. 약사에게 보여 주세요." if easy_mode else ""))
            if not store.has_drugbank:
                html(theme.notice("DrugBank 데이터가 로드되지 않았습니다.", "info"))
            dbs = report.of_kind("drugbank")
            if store.has_drugbank and not dbs:
                html(theme.empty("참고 상호작용이 발견되지 않았습니다."))
            for f in dbs:
                with st.expander(f"{f.drug_a}  ×  {f.drug_b}  ({f.title})"):
                    html("".join(theme.db_row(c1, c2, desc, aliased) for c1, c2, desc, aliased in f.details[:20]))
                    if len(f.details) > 20:
                        st.caption(f"... 외 {len(f.details) - 20}건")

        with t4:
            if not report.unresolved:
                html(theme.empty("모든 약의 성분이 확인되었습니다."))
            REASON = {
                "unmapped": "성분 정보를 찾지 못했습니다.",
                "partial": "일부 성분의 영문명을 몰라 확정하지 못했습니다.",
                "ambiguous": "DUR 자료에서 서로 다른 성분으로 중복 등록되어 확정하지 못했습니다.",
                "count_mismatch": "허가정보의 성분 개수와 성분명이 맞지 않아 확정하지 못했습니다.",
                "not_found": "제품 목록에서 찾을 수 없습니다.",
            }
            for d in report.unresolved:
                html(theme.unresolved_card(d.label, REASON.get(d.map_source, "성분을 확정하지 못했습니다."),
                                           lead=plain.LEAD["unresolved"] if easy_mode else ""))

    # --- PDF ---
    st.divider()
    try:
        if not font_is_embedded():
            st.caption("한글 TrueType 폰트를 찾지 못해 PDF 의 한글이 일부 뷰어에서 보이지 않을 수 있습니다. "
                       "README 의 '한글 폰트' 항목을 참고하세요.")
        st.download_button("PDF 보고서 다운로드", data=build_pdf(report, store.info), type="primary",
                           icon=":material/download:", file_name="polypharmacy_report.pdf", mime="application/pdf")
    except Exception as e:  # PDF 가 실패해도 화면 결과는 유지
        html(theme.notice(f"PDF 생성 실패: {e}", "danger"))

    html(theme.footer("DrugBank 데이터는 라이선스 조건(비상업 이용 등)을 확인한 뒤 사용하세요. 이 도구는 의료 행위를 대체하지 않습니다."))
except Exception:  # 예상치 못한 오류는 안내 후 신고 받기
    tb = traceback.format_exc()
    html(theme.notice("예상치 못한 오류가 발생했습니다. 아래에 내용을 남겨 주시면 고치는 데 큰 도움이 됩니다.", "danger"))
    with st.expander("오류 정보 (개발자용)"):
        st.code(tb[-1500:])
    render_feedback_form("fb_err", error_text=tb)
