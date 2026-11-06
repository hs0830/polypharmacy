"""화면 디자인: 파랑·청록 팔레트, 전역 CSS, HTML 컴포넌트. 외부 문자열은 모두 esc() 로 이스케이프한다."""
import html
import re

FONT_STACK = "'Pretendard','Noto Sans KR','Malgun Gothic','Apple SD Gothic Neo',sans-serif"

CSS = """
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');
:root{
  --navy:#0B3A5B; --blue:#0F5C8E; --teal:#0E8C8C; --teal-soft:#E4F3F3; --blue-soft:#EAF2F8;
  --bg:#F4F8FA; --card:#FFFFFF; --line:#D9E5EC; --text:#1B2B38; --muted:#5F7484;
  --red:#B93030; --red-soft:#FDEEEE; --red-line:#F1B9B9;
  --amber:#8A5B00; --amber-soft:#FFF5DF; --amber-line:#F1D9A0;
  --info:#22609E; --info-soft:#EAF2FB; --info-line:#BFD6EE;
  --gray:#55656F; --gray-soft:#F0F3F5; --gray-line:#C9D4DB;
}
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp li, .stMarkdown div, [data-testid="stSidebar"] div {
  font-family: __FONT__;
}
.stApp { background: var(--bg); color: var(--text); }
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1080px; padding-top: 1.6rem; }
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
[data-testid="stHeader"] { background: transparent; }

/* ---- Streamlit 기본 요소 다듬기 ---- */
.stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 600; }
div[data-baseweb="input"], div[data-baseweb="select"] > div { border-radius: 10px; }
[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 14px; border-color: var(--line); background: var(--card); }
[data-testid="stExpander"] { border-radius: 12px; border-color: var(--line); background: var(--card); }
.stTabs [data-baseweb="tab-list"] { gap: 2px; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { padding: 10px 14px; }
.stTabs [aria-selected="true"] p { color: var(--teal); font-weight: 700; }
[class*="st-key-drugrow_"] [data-testid="stHorizontalBlock"] { flex-wrap: nowrap !important; gap: 8px; }
[class*="st-key-drugrow_"] [data-testid="stColumn"] { min-width: 0 !important; }
[class*="st-key-drugrow_"] [data-testid="stColumn"]:last-child { flex: 0 0 44px !important; width: 44px !important; }
[class*="st-key-drugrow_"] [data-testid="stColumn"]:first-child { flex: 1 1 0 !important; width: auto !important; }
[class*="st-key-rm_"] button { padding: 0.15rem 0.5rem; min-height: 0; color: var(--muted); border-color: var(--line); }

/* ---- 공통 부품 ---- */
.pp-hero { background: linear-gradient(135deg, #0B3A5B 0%, #0F5C8E 55%, #0E8C8C 100%); color: #fff;
  border-radius: 18px; padding: 22px 26px; margin-bottom: 14px; }
.pp-hero-title { font-size: 1.55rem; font-weight: 800; letter-spacing: -0.02em; }
.pp-hero-sub { margin-top: 4px; opacity: .88; font-size: .95rem; }
.pp-notice { display: flex; gap: 10px; align-items: flex-start; border-radius: 12px; padding: 10px 14px;
  margin: 8px 0; font-size: .9rem; line-height: 1.5; border: 1px solid; }
.pp-notice-ico { flex: 0 0 auto; width: 20px; height: 20px; border-radius: 50%; color: #fff; font-weight: 800;
  font-size: .8rem; display: flex; align-items: center; justify-content: center; margin-top: 1px; }
.pp-n-warn { background: var(--amber-soft); border-color: var(--amber-line); color: #5B3D00; }
.pp-n-warn .pp-notice-ico { background: #D99A1B; }
.pp-n-info { background: var(--info-soft); border-color: var(--info-line); color: #163F68; }
.pp-n-info .pp-notice-ico { background: var(--info); }
.pp-n-danger { background: var(--red-soft); border-color: var(--red-line); color: #6B1B1B; }
.pp-n-danger .pp-notice-ico { background: var(--red); }
.pp-n-gray { background: var(--gray-soft); border-color: var(--gray-line); color: #33414A; }
.pp-n-gray .pp-notice-ico { background: var(--gray); }

.pp-section { display: flex; align-items: center; flex-wrap: wrap; gap: 4px 10px; margin: 22px 0 8px; }
.pp-step { width: 26px; height: 26px; border-radius: 50%; background: var(--teal); color: #fff; font-weight: 800;
  font-size: .85rem; display: flex; align-items: center; justify-content: center; }
.pp-section-title { font-size: 1.15rem; font-weight: 800; color: var(--navy); white-space: nowrap; }
.pp-section-hint { color: var(--muted); font-size: .85rem; }

.pp-badge { display: inline-block; border-radius: 999px; padding: 2px 10px; font-size: .75rem; font-weight: 700;
  white-space: nowrap; border: 1px solid; }
.pp-b-ok { background: var(--teal-soft); color: #0A6B6B; border-color: #A9DCDC; }
.pp-b-est { background: var(--info-soft); color: var(--info); border-color: var(--info-line); }
.pp-b-unk { background: var(--amber-soft); color: var(--amber); border-color: var(--amber-line); }
.pp-b-gray { background: var(--gray-soft); color: var(--gray); border-color: var(--gray-line); }
.pp-chip { display: inline-block; max-width: 100%; overflow-wrap: anywhere; word-break: break-all; background: var(--blue-soft); color: var(--navy); border-radius: 6px;
  padding: 1px 8px; margin: 2px 4px 2px 0; font-size: .8rem; font-family: ui-monospace, Consolas, monospace; }
.pp-x { color: var(--muted); margin: 0 4px; }

.pp-drug { margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--card);
  border: 1px solid var(--line); border-left: 4px solid var(--teal); border-radius: 12px; padding: 10px 14px; }
.pp-drug-unk { border-left-color: #D99A1B; background: #FFFCF4; }
.pp-drug-name { font-weight: 700; color: var(--navy); }
.pp-drug-sub { color: var(--muted); font-size: .82rem; margin-top: 2px; overflow-wrap: anywhere; }
.pp-drug > div:first-child { min-width: 0; flex: 1 1 auto; }
.pp-drug-name { overflow-wrap: anywhere; }

.pp-banner { display: flex; gap: 16px; align-items: center; border-radius: 16px; padding: 18px 22px;
  border: 1px solid; margin: 6px 0 12px; }
.pp-banner-ico { flex: 0 0 auto; width: 44px; height: 44px; border-radius: 50%; color: #fff; font-weight: 800;
  font-size: 1.4rem; display: flex; align-items: center; justify-content: center; }
.pp-banner-title { font-size: 1.25rem; font-weight: 800; }
.pp-banner-text { margin-top: 2px; font-size: .95rem; line-height: 1.5; }
.pp-lv-contraindicated { background: var(--red-soft); border-color: var(--red-line); color: #6B1B1B; }
.pp-lv-contraindicated .pp-banner-ico { background: var(--red); }
.pp-lv-warning { background: var(--amber-soft); border-color: var(--amber-line); color: #5B3D00; }
.pp-lv-warning .pp-banner-ico { background: #D99A1B; }
.pp-lv-caution { background: var(--info-soft); border-color: var(--info-line); color: #163F68; }
.pp-lv-caution .pp-banner-ico { background: var(--info); }
.pp-lv-none_found { background: var(--teal-soft); border-color: #A9DCDC; color: #0A4F4F; }
.pp-lv-none_found .pp-banner-ico { background: var(--teal); }

.pp-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 6px 0 14px; }
.pp-stat { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 10px 12px; }
.pp-stat-n { font-size: 1.6rem; font-weight: 800; line-height: 1.1; color: #9AA9B4; }
.pp-stat-l { font-size: .78rem; color: var(--muted); margin-top: 2px; }
.pp-stat-red { border-color: var(--red-line); background: var(--red-soft); }
.pp-stat-red .pp-stat-n { color: var(--red); }
.pp-stat-amber { border-color: var(--amber-line); background: var(--amber-soft); }
.pp-stat-amber .pp-stat-n { color: var(--amber); }
.pp-stat-info { border-color: var(--info-line); background: var(--info-soft); }
.pp-stat-info .pp-stat-n { color: var(--info); }
.pp-stat-gray { border-color: var(--gray-line); background: var(--gray-soft); }
.pp-stat-gray .pp-stat-n { color: var(--gray); }

.pp-panel-title { font-weight: 800; color: var(--navy); margin: 2px 0 8px; }
.pp-sum-row { display: flex; align-items: center; gap: 8px; padding: 7px 0; border-bottom: 1px dashed var(--line);
  font-size: .9rem; }
.pp-sum-names { font-weight: 600; }
.pp-legend { color: var(--muted); font-size: .8rem; margin-top: 4px; padding-bottom: 4px; }

.pp-pill { display: inline-block; border-radius: 6px; padding: 1px 9px; font-size: .75rem; font-weight: 800;
  color: #fff; white-space: nowrap; }
.pp-p-contraindicated { background: var(--red); }
.pp-p-warning { background: #D99A1B; }
.pp-p-info { background: var(--info); }
.pp-p-gray { background: var(--gray); }

.pp-card { background: var(--card); border: 1px solid var(--line); border-left: 5px solid var(--gray-line);
  border-radius: 12px; padding: 14px 16px; margin: 10px 0; }
.pp-f-contraindicated { border-left-color: var(--red); }
.pp-f-warning { border-left-color: #D99A1B; }
.pp-f-info { border-left-color: var(--info); }
.pp-f-gray { border-left-color: var(--gray-line); border-style: dashed; border-left-style: solid; background: #FAFBFC; }
.pp-f-head { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.pp-f-names { font-weight: 800; color: var(--navy); overflow-wrap: anywhere; min-width: 0; }
.pp-f-reason { margin-top: 8px; line-height: 1.55; }
.pp-f-lead { margin-top: 10px; font-weight: 700; font-size: 1.02rem; line-height: 1.5; color: var(--navy); }
.pp-f-foot { margin-top: 8px; color: var(--muted); font-size: .8rem; }
.pp-note { margin-top: 8px; background: var(--amber-soft); border: 1px solid var(--amber-line); color: #5B3D00;
  border-radius: 8px; padding: 8px 12px; font-size: .88rem; line-height: 1.5; }
.pp-note small { display: block; opacity: .85; }

.pp-kv { display: grid; grid-template-columns: 110px 1fr; gap: 6px 12px; margin: 8px 0 4px; font-size: .9rem; }
.pp-kv dt { color: var(--muted); font-weight: 600; }
.pp-kv dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.pp-empty { background: var(--gray-soft); border: 1px dashed var(--gray-line); color: #33414A;
  border-radius: 12px; padding: 14px 16px; margin: 8px 0; font-size: .92rem; }
.pp-db { overflow-wrap: anywhere; padding: 6px 0; border-bottom: 1px dashed var(--line); font-size: .88rem; line-height: 1.5; }
.pp-db-desc { color: #33414A; }

.pp-side-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: .88rem; }
.pp-side-row span:first-child { color: var(--muted); }
.pp-bar { height: 6px; background: var(--line); border-radius: 999px; overflow: hidden; margin: 4px 0 8px; }
.pp-bar > div { height: 100%; background: linear-gradient(90deg, var(--blue), var(--teal)); }
.pp-footer { color: var(--muted); font-size: .8rem; margin: 18px 0 6px; line-height: 1.5; }

/* ---- 쉬운 보기 ---- */
.pp-ez-pair { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; }
.pp-ez-drug { background: var(--blue-soft); border-radius: 14px; padding: 10px 18px; min-width: 0; }
.pp-ez-name { font-weight: 800; font-size: 1.2rem; color: var(--navy); overflow-wrap: anywhere; }
.pp-ez-cat { font-size: .9rem; color: var(--muted); margin-top: 2px; }
.pp-ez-and { font-weight: 800; color: var(--muted); font-size: 1.05rem; }
.pp-ez-lead { margin-top: 12px; font-size: 1.12rem; font-weight: 700; line-height: 1.5; }
.pp-ez-list { display: flex; flex-direction: column; gap: 8px; margin: 6px 0 4px; }
.pp-ez-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px 12px; background: var(--card);
  border: 1px solid var(--line); border-radius: 12px; padding: 10px 16px; }
.pp-ez-row .pp-ez-name { font-size: 1.05rem; }
.pp-ez-row .pp-ez-cat { margin: 0; }

@media (max-width: 720px) {
  .pp-stats { grid-template-columns: repeat(2, 1fr); }
  .pp-stat:last-child:nth-child(odd) { grid-column: 1 / -1; }
  .pp-kv { grid-template-columns: 86px 1fr; }
  .pp-hero { padding: 16px 18px; border-radius: 14px; }
  .pp-hero-title { font-size: 1.2rem; }
  .pp-hero-sub { font-size: .85rem; }
  .pp-banner { padding: 14px 16px; gap: 12px; }
  .pp-banner-title { font-size: 1.1rem; }
  .pp-section-hint { flex-basis: 100%; margin-left: 36px; }
}
""".replace("__FONT__", FONT_STACK)


def esc(x):
    return html.escape(str(x), quote=True)


def _c(h):
    """마크다운이 HTML 블록을 깨지 않도록 줄바꿈/공백 제거."""
    return re.sub(r">\s+<", "><", re.sub(r"\s*\n\s*", "", h)).strip()


def style_tag():
    return f"<style>{CSS}</style>"


def hero(title, subtitle):
    return _c(f'<div class="pp-hero"><div class="pp-hero-title">{esc(title)}</div>'
              f'<div class="pp-hero-sub">{esc(subtitle)}</div></div>')


NOTICE_ICON = {"warn": "!", "danger": "!", "info": "i", "gray": "i"}


def notice(text, kind="warn"):
    return _c(f'<div class="pp-notice pp-n-{kind}"><span class="pp-notice-ico">{NOTICE_ICON[kind]}</span>'
              f'<div>{esc(text)}</div></div>')


def section(num, title, hint=""):
    h = f'<span class="pp-section-hint">{esc(hint)}</span>' if hint else ""
    return _c(f'<div class="pp-section"><span class="pp-step">{esc(num)}</span>'
              f'<span class="pp-section-title">{esc(title)}</span>{h}</div>')


def badge(text, kind="ok"):
    return f'<span class="pp-badge pp-b-{kind}">{esc(text)}</span>'


def chip(text):
    return f'<span class="pp-chip">{esc(text)}</span>'


def chips_from_title(title):
    """'a × b' 형태면 칩 두 개로, 아니면 텍스트 그대로."""
    if " × " in title:
        a, b = title.split(" × ", 1)
        return f'{chip(a)}<span class="pp-x">×</span>{chip(b)}'
    return esc(title)


def drug_row(name, ingr_key, status, entp="", category=None):
    """status: ok | est | unk. category 가 있으면 성분키 대신 약 분류를 보여 준다."""
    kind = {"ok": ("성분 확인", "ok"), "est": ("이름 기반 추정", "est"), "unk": ("성분 확인 불가", "unk")}[status]
    if category is not None:
        sub = esc(category) if category else ""
    else:
        sub = f"성분 {esc(ingr_key)}" if ingr_key else "성분 정보 없음"
    if entp:
        sub = f"{sub} · {esc(entp)}" if sub else esc(entp)
    cls = "pp-drug pp-drug-unk" if status == "unk" else "pp-drug"
    return _c(f'<div class="{cls}"><div><div class="pp-drug-name">{esc(name)}</div>'
              f'<div class="pp-drug-sub">{sub}</div></div>{badge(*kind)}</div>')


BANNER_ICON = {"contraindicated": "!", "warning": "!", "caution": "i", "none_found": "i"}


def banner(level, label, text):
    return _c(f'<div class="pp-banner pp-lv-{level}"><div class="pp-banner-ico">{BANNER_ICON[level]}</div>'
              f'<div><div class="pp-banner-title">{esc(label)}</div><div class="pp-banner-text">{esc(text)}</div></div></div>')


def stat_cards(items):
    """items: [(라벨, 숫자, 톤)]. 0 이면 회색."""
    cells = []
    for label, n, tone in items:
        cls = f"pp-stat pp-stat-{tone}" if n else "pp-stat"
        cells.append(f'<div class="{cls}"><div class="pp-stat-n">{esc(n)}</div><div class="pp-stat-l">{esc(label)}</div></div>')
    return _c(f'<div class="pp-stats">{"".join(cells)}</div>')


SEV_LABEL = {"contraindicated": "금기", "warning": "확인", "info": "참고", "gray": "확인 불가"}


def pill(sev):
    return f'<span class="pp-pill pp-p-{sev}">{SEV_LABEL[sev]}</span>'


def summary_rows(pairs, unresolved, limit=8):
    """pairs: [((이름A, 이름B), 등급)]"""
    rows = [f'<div class="pp-sum-row">{pill(sev)}<span class="pp-sum-names">{esc(a)} <span class="pp-x">×</span> {esc(b)}</span></div>'
            for (a, b), sev in pairs[:limit]]
    if len(pairs) > limit:
        rows.append(f'<div class="pp-legend">... 외 {len(pairs) - limit}개 조합 (아래 탭에서 확인)</div>')
    rows += [f'<div class="pp-sum-row">{pill("gray")}<span class="pp-sum-names">{esc(n)}</span></div>' for n in unresolved]
    if not rows:
        rows = ['<div class="pp-legend">발견된 조합이 없습니다.</div>']
    return _c("".join(rows))


def finding_card(sev, drug_a, drug_b, chips_html="", reason="", note="", foot="", pill_text=None, lead=""):
    note_html = ""
    if note:
        note_html = (f'<div class="pp-note"><b>조건/비고</b> {esc(note)}'
                     f'<small>조건부 금기일 수 있으니 약사에게 확인하세요.</small></div>')
    label = f'<span class="pp-pill pp-p-{sev}">{esc(pill_text or SEV_LABEL[sev])}</span>'
    return _c(
        f'<div class="pp-card pp-f-{sev}"><div class="pp-f-head">{label}'
        f'<span class="pp-f-names">{esc(drug_a)} <span class="pp-x">×</span> {esc(drug_b)}</span></div>'
        f'{f"<div class=pp-f-lead>{esc(lead)}</div>" if lead else ""}'
        f'{f"<div>{chips_html}</div>" if chips_html else ""}'
        f'{f"<div class=pp-f-reason>{esc(reason)}</div>" if reason else ""}{note_html}'
        f'{f"<div class=pp-f-foot>{esc(foot)}</div>" if foot else ""}</div>')


def unresolved_card(name, reason, lead=""):
    return _c(f'<div class="pp-card pp-f-gray"><div class="pp-f-head">{pill("gray")}'
              f'<span class="pp-f-names">{esc(name)}</span></div>'
              f'{f"<div class=pp-f-lead>{esc(lead)}</div>" if lead else ""}'
              f'<div class="pp-f-reason">{esc(reason)}<br>이 약은 위 검사에 포함되지 않았습니다. 약사에게 직접 확인하세요.</div></div>')


def kv(pairs):
    """[(라벨, HTML)]. 값은 안전한 HTML 이어야 한다."""
    body = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in pairs)
    return _c(f'<dl class="pp-kv">{body}</dl>')


def empty(text):
    return f'<div class="pp-empty">{esc(text)}</div>'


def db_row(c1, c2, desc, aliased=False):
    tail = ' <span class="pp-legend">(유사 성분명으로 매칭)</span>' if aliased else ""
    return (f'<div class="pp-db">{chip(c1)}<span class="pp-x">×</span>{chip(c2)}{tail}'
            f'<div class="pp-db-desc">{esc(desc)}</div></div>')


def sidebar_stats(rows, ratio=None, bar_after=1):
    """rows: [(라벨, 값)]. ratio(0~1)가 있으면 bar_after 번째 줄 아래에 진행 막대 표시."""
    parts = []
    for i, (k, v) in enumerate(rows):
        parts.append(f'<div class="pp-side-row"><span>{esc(k)}</span><span>{esc(v)}</span></div>')
        if ratio is not None and i == bar_after:
            parts.append(f'<div class="pp-bar"><div style="width:{max(0, min(1, ratio)) * 100:.0f}%"></div></div>')
    return _c("".join(parts))


def easy_drug_box(name, category=""):
    cat = f'<div class="pp-ez-cat">{esc(category)}</div>' if category else ""
    return f'<div class="pp-ez-drug"><div class="pp-ez-name">{esc(name)}</div>{cat}</div>'


def easy_pair_card(sev, a, a_cat, b, b_cat, lead, note=""):
    """쉬운 보기 카드: 약 이름 두 개와 한 줄 안내 (기술 용어 없음)."""
    note_html = ""
    if note:
        note_html = (f'<div class="pp-note"><b>조건</b> {esc(note)}'
                     f'<small>조건이 붙은 금기일 수 있어요. 약사에게 꼭 확인하세요.</small></div>')
    return _c(f'<div class="pp-card pp-f-{sev}"><div class="pp-ez-pair">{easy_drug_box(a, a_cat)}'
              f'<span class="pp-ez-and">와(과)</span>{easy_drug_box(b, b_cat)}</div>'
              f'<div class="pp-ez-lead">{esc(lead)}</div>{note_html}</div>')


def easy_drug_list(items):
    """items: [(이름, 분류, 확인 여부)]"""
    rows = []
    for name, cat, ok in items:
        badge_html = badge("확인됨", "ok") if ok else badge("확인 못 함", "unk")
        c = f'<span class="pp-ez-cat">{esc(cat)}</span>' if cat else ""
        rows.append(f'<div class="pp-ez-row"><span class="pp-ez-name">{esc(name)}</span>{c}{badge_html}</div>')
    return _c(f'<div class="pp-ez-list">{"".join(rows)}</div>')


def large_font_style(scale=118):
    """글자 크게 (rem 기준 글자 크기 확대)."""
    return f"<style>html {{ font-size: {int(scale)}%; }}</style>"


def footer(text):
    return f'<div class="pp-footer">{esc(text)}</div>'
