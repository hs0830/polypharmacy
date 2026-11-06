import shutil
import subprocess

import pytest

from src.models import Drug, Finding, Report
from src.viz import build_dot, pair_severities, short_name


def report():
    a = Drug(label="옴니파큐240주(이오헥솔)", ingr_key="iohexol", components=("iohexol",))
    b = Drug(label="글루코닐정(메트포르민염산염)", ingr_key="metformin", components=("metformin",))
    c = Drug(label="서흥캡슐0호")  # 성분 확인 불가
    fs = [Finding(kind="drugbank", severity="info", drug_a=a.label, drug_b=b.label, title="1건"),
          Finding(kind="dur", severity="contraindicated", drug_a=b.label, drug_b=a.label, title="x")]
    return Report(drugs=[a, b, c], unresolved=[c], findings=fs, overall="contraindicated", overall_text="")


def test_short_name_drops_parens_strength_and_prefix():
    assert short_name("타이레놀정500밀리그람(아세트아미노펜)") == "타이레놀정"
    assert short_name("[성분] warfarin") == "warfarin"
    assert len(short_name("가" * 60)) <= 22


def test_pair_uses_highest_severity_regardless_of_order():
    r = report()
    assert list(pair_severities(r).values()) == ["contraindicated"]


def test_dot_is_size_capped_and_marks_unresolved():
    dot = build_dot(report())
    assert 'size="6.4,3.4"' in dot  # 화면을 꽉 채우지 않도록 크기 상한
    assert "n2 [label=" in dot and "dashed" in dot.split("n2 [label=")[1].split("\n")[0]
    assert dot.count(" -- ") == 1  # 같은 쌍은 선 하나


@pytest.mark.skipif(shutil.which("dot") is None, reason="graphviz 없음")
def test_dot_is_valid_graphviz():
    p = subprocess.run(["dot", "-Tsvg"], input=build_dot(report()), text=True, capture_output=True)
    assert p.returncode == 0 and "<svg" in p.stdout
