"""관계도(Graphviz DOT) 생성 (크기 상한과 짧은 라벨 사용)."""
import re

SEV_RANK = {"info": 0, "warning": 1, "contraindicated": 2}
SEV_STYLE = {
    "contraindicated": 'color="#B93030", penwidth=2.8',
    "warning": 'color="#D99A1B", penwidth=2.2',
    "info": 'color="#22609E", style=dashed, penwidth=1.5',
}
# 관계에 참여한 약의 테두리/배경 (가장 높은 등급 기준)
NODE_STYLE = {
    "contraindicated": 'fillcolor="#FDEEEE", color="#B93030", penwidth=2',
    "warning": 'fillcolor="#FFF5DF", color="#D99A1B", penwidth=2',
    "info": 'fillcolor="#EAF2FB", color="#22609E", penwidth=1.6',
}
SEV_EMOJI = {"contraindicated": "🔴", "warning": "🟠", "info": "🔵"}


def short_name(name, max_len=22):
    """화면용 짧은 이름 ('[성분]' 접두사·괄호 제거, 길면 줄임)."""
    s = re.sub(r"^\[성분\]\s*", "", str(name))
    s = re.sub(r"\([^)]*\)?", "", s).strip() or str(name)
    cut = re.sub(r"(?<=[가-힣A-Za-z])\d.*$", "", s).strip()  # 함량(500밀리그램 등) 이하 제거
    s = cut if len(cut) >= 2 else s
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _wrap(s, width=11):
    return "\\n".join(s[i:i + width] for i in range(0, len(s), width))  # DOT 의 줄바꿈 이스케이프


def _q(s):
    return str(s).replace("\\", "/").replace('"', "'")


def pair_severities(report):
    """{(약A, 약B): 가장 높은 등급}"""
    out = {}
    for f in report.findings:
        key = tuple(sorted((f.drug_a, f.drug_b)))
        if key not in out or SEV_RANK[f.severity] > SEV_RANK[out[key]]:
            out[key] = f.severity
    return out


def build_dot(report):
    ids = {d.label: f"n{i}" for i, d in enumerate(report.drugs)}
    pairs = pair_severities(report)
    worst = {}  # 약 -> 연결된 관계 중 가장 높은 등급
    for (a, b), sev in pairs.items():
        for n in (a, b):
            if n not in worst or SEV_RANK[sev] > SEV_RANK[worst[n]]:
                worst[n] = sev
    lines = [
        "graph G {",
        'graph [rankdir=LR, size="6.4,3.4", pad="0.15", nodesep="0.3", ranksep="0.9", bgcolor="transparent"];',
        'node [shape=box, style="rounded,filled", fontname="Pretendard, Noto Sans KR, Malgun Gothic, sans-serif", '
        'fontsize=11, margin="0.22,0.09", fillcolor="#FFFFFF", color="#0E8C8C", fontcolor="#0B3A5B", penwidth=1.4];',
    ]
    for d in report.drugs:
        label = _wrap(_q(short_name(d.label)))
        if not d.resolved:
            extra = ', fillcolor="#F0F3F5", color="#8A99A5", style="rounded,filled,dashed"'
        elif d.label in worst:
            extra = ", " + NODE_STYLE[worst[d.label]]
        else:
            extra = ""
        lines.append(f'{ids[d.label]} [label="{label}"{extra}];')
    for (a, b), sev in pairs.items():
        lines.append(f"{ids[a]} -- {ids[b]} [{SEV_STYLE[sev]}];")
    lines.append("}")
    return "\n".join(lines)
