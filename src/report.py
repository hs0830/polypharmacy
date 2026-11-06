"""PDF 보고서 (reportlab). 한글 폰트를 OS별로 찾고, 없으면 내장 CID 폰트를 쓴다."""
import io
import os
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

FONT_CANDIDATES = [
    os.environ.get("KOREAN_FONT_PATH", ""),
    "C:/Windows/Fonts/malgun.ttf",
    "/Library/Fonts/NanumGothic.ttf",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
    # 참고: CFF 기반 OTF/TTC(Noto Sans CJK 등)는 못 읽으므로 TrueType 폰트 필요
]

_FONT = None


def font_is_embedded():
    """한글 폰트가 PDF에 임베딩되는지 (False 면 뷰어 폰트에 의존)."""
    return korean_font() == "KRFont"


def korean_font():
    """한글 폰트 이름 반환 (최초 1회 등록)."""
    global _FONT
    if _FONT:
        return _FONT
    for path in FONT_CANDIDATES:
        if not path or not os.path.exists(path):
            continue
        for idx in ([1, 0, 2, 3, 4] if path.lower().endswith(".ttc") else [None]):
            try:
                font = TTFont("KRFont", path, subfontIndex=idx) if idx is not None else TTFont("KRFont", path)
                pdfmetrics.registerFont(font)
                pdfmetrics.registerFontFamily("KRFont", normal="KRFont", bold="KRFont",
                                              italic="KRFont", boldItalic="KRFont")
                _FONT = "KRFont"
                return _FONT
            except Exception:
                continue
    # 폰트 파일이 없으면 내장 CID 폰트 (임베딩 안 됨)
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    pdfmetrics.registerFontFamily("HYSMyeongJo-Medium", normal="HYSMyeongJo-Medium",
                                  bold="HYSMyeongJo-Medium", italic="HYSMyeongJo-Medium",
                                  boldItalic="HYSMyeongJo-Medium")
    _FONT = "HYSMyeongJo-Medium"
    return _FONT


LEVEL_LABEL = {
    "contraindicated": "병용금기 발견",
    "warning": "확인 필요",
    "caution": "참고 사항 있음",
    "none_found": "발견된 상호작용 없음 (안전을 의미하지 않음)",
}
LEVEL_COLOR = {"contraindicated": "#FEE2E2", "warning": "#FEF3C7", "caution": "#E0F2FE", "none_found": "#F1F5F9"}
SOURCE_LABEL = {
    "dur_exact": "확정", "dur_loose": "확정", "api_english": "확정", "api_ingredients": "확정",
    "paren_dict": "이름 기반 추정", "ingredient": "성분 직접 선택",
}

DISCLAIMER = (
    "본 보고서는 식약처 DUR 병용금기 공고와 DrugBank 참고 자료를 조회한 결과이며, 의사·약사의 판단을 대체하지 않습니다. "
    "결과가 없다는 것은 안전하다는 뜻이 아닙니다. 성분을 확인하지 못한 약은 검사에서 제외되었습니다. "
    "복용 중인 약을 임의로 중단하거나 변경하지 말고 반드시 의료 전문가와 상담하세요."
)


def _p(text, style):
    return Paragraph(escape(str(text)).replace("\n", "<br/>"), style)


def build_pdf(report, info=None):
    font = korean_font()
    info = info or {}
    base = ParagraphStyle("base", fontName=font, fontSize=9, leading=13, textColor=colors.HexColor("#1E293B"))
    small = ParagraphStyle("small", parent=base, fontSize=8, leading=11, textColor=colors.HexColor("#475569"))
    h1 = ParagraphStyle("h1", parent=base, fontSize=18, leading=22, textColor=colors.HexColor("#1E3A8A"))
    h2 = ParagraphStyle("h2", parent=base, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=32, rightMargin=32, topMargin=32, bottomMargin=32,
                            title="다제복용 약물 상호작용 점검 보고서")
    W = A4[0] - 64
    story = [
        _p("다제복용 약물 상호작용 점검 보고서", h1),
        _p(f"생성: {datetime.now():%Y-%m-%d %H:%M}   |   데이터 빌드: {info.get('built_at', '-')}   |   "
           f"DUR 고시 기준(최신 적용일): {info.get('dur_latest') or '-'}", small),
        HRFlowable(width="100%", thickness=1, color=colors.HexColor("#94A3B8"), spaceBefore=4, spaceAfter=8),
    ]

    banner = Table([[_p(f"종합: {LEVEL_LABEL[report.overall]}\n{report.overall_text}", base)]], colWidths=[W])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(LEVEL_COLOR[report.overall])),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#94A3B8")),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [banner, Spacer(1, 8)]

    # 분석 대상
    story.append(_p("분석 대상 약물", h2))
    rows = [[_p("약물", base), _p("성분(영문)", base), _p("성분 확인", base)]]
    for d in report.drugs:
        status = SOURCE_LABEL.get(d.map_source, "확인 불가") if d.resolved else "확인 불가 (검사 제외)"
        rows.append([_p(d.label, small), _p(d.ingr_key or "-", small), _p(status, small)])
    t = Table(rows, colWidths=[W * 0.45, W * 0.35, W * 0.20], repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(t)

    def findings_table(title, kind, header_bg):
        fs = report.of_kind(kind)
        story.append(_p(f"{title} ({len(fs)}건)", h2))
        if not fs:
            story.append(_p("해당 없음", small))
            return
        rows = [[_p("약물 조합", base), _p("내용", base)]]
        for f in fs:
            body = f.reason
            if f.note:
                body += f"\n※ 조건/비고: {f.note}"
            if f.notice_no:
                body += f"\n(고시 {f.notice_no}, 적용 {f.apply_date})"
            if f.kind == "drugbank":
                lines = [f"- {c1} × {c2}: {desc}" for c1, c2, desc, _ in f.details[:8]]
                if len(f.details) > 8:
                    lines.append(f"... 외 {len(f.details) - 8}건")
                body = "\n".join(lines)
            rows.append([_p(f"{f.drug_a}\n× {f.drug_b}", small), _p(body, small)])
        t = Table(rows, colWidths=[W * 0.34, W * 0.66], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(header_bg)),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(t)

    findings_table("식약처 DUR 병용금기", "dur", "#FECACA")
    findings_table("복합제 포함 가능성 (DUR, 확인 필요)", "dur_possible", "#FDE68A")
    findings_table("성분 중복", "duplicate", "#FDE68A")
    findings_table("참고 상호작용 (DrugBank, 심각도 정보 없음)", "drugbank", "#BAE6FD")

    story.append(_p(f"성분 확인 불가 약물 ({len(report.unresolved)}건)", h2))
    if report.unresolved:
        story.append(_p("아래 약물은 성분을 확정하지 못해 위 검사에 포함되지 않았습니다. 약사에게 별도로 확인하세요.", small))
        for d in report.unresolved:
            story.append(_p(f"- {d.label}", small))
    else:
        story.append(_p("없음", small))

    story += [Spacer(1, 12), HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#94A3B8")),
              Spacer(1, 4), _p(DISCLAIMER, small)]
    doc.build(story)
    return buf.getvalue()
