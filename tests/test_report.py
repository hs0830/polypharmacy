import io

import pytest

from src.models import Drug, Finding, Report
from src.report import build_pdf


def sample_report():
    a = Drug(label="중외5-에프유주(플루오로우라실)", ingr_key="fluorouracil", components=("fluorouracil",), map_source="dur_exact")
    b = Drug(label="테고캡슐25", ingr_key="gimeracil+oteracil+tegafur", components=("gimeracil", "oteracil", "tegafur"), map_source="dur_exact")
    c = Drug(label="알수없는정", map_source="unmapped")
    f = Finding(kind="dur", severity="contraindicated", drug_a=a.label, drug_b=b.label, title="x", reason="대사 감소로 독성 증가",
                note="48시간 이내 병용금기", notice_no="20200130", apply_date="2020-12-28")
    g = Finding(kind="drugbank", severity="info", drug_a=a.label, drug_b=b.label, title="1건", details=[("a", "b", "May increase X", False)])
    return Report(drugs=[a, b, c], unresolved=[c], findings=[f, g], overall="contraindicated", overall_text="식약처 DUR 병용금기 조합이 발견되었습니다.")


def test_pdf_builds_and_contains_korean_text():
    pytest.importorskip("pypdf")
    from pypdf import PdfReader
    data = build_pdf(sample_report(), {"built_at": "2026-09-29T00:00:00"})
    assert data[:4] == b"%PDF"
    text = "".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(data)).pages)
    assert "병용금기" in text and "테고캡슐25" in text and "알수없는정" in text
    assert "안전을 의미하지" in text or "안전하다는 뜻이 아닙니다" in text  # 면책 문구 포함
