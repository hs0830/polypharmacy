from src import theme


def test_dynamic_text_is_escaped_everywhere():
    evil = "<script>alert(1)</script>"
    outputs = [
        theme.finding_card("contraindicated", evil, evil, theme.chips_from_title(f"{evil} × {evil}"), evil, evil, evil),
        theme.drug_row(evil, evil, "ok", evil),
        theme.banner("caution", evil, evil),
        theme.notice(evil, "warn"),
        theme.unresolved_card(evil, evil),
        theme.summary_rows([((evil, evil), "info")], [evil]),
        theme.db_row(evil, evil, evil),
        theme.stat_cards([(evil, 3, "red")]),
        theme.kv([(evil, theme.esc(evil))]),
        theme.section(1, evil, evil),
        theme.sidebar_stats([(evil, evil)]),
        theme.easy_pair_card("contraindicated", evil, evil, evil, evil, evil, evil),
        theme.easy_drug_list([(evil, evil, True)]),
    ]
    for out in outputs:
        assert "<script>" not in out and "&lt;script&gt;" in out


def test_html_has_no_blank_lines_or_leading_indent_that_break_markdown():
    for out in (theme.finding_card("warning", "a", "b", "", "사유", "비고", "푸터"),
                theme.banner("none_found", "제목", "본문"), theme.stat_cards([("x", 0, "gray")])):
        assert "\n" not in out


def test_zero_count_stat_is_muted_and_nonzero_is_colored():
    html = theme.stat_cards([("금기", 0, "red"), ("참고", 2, "info")])
    assert 'class="pp-stat"' in html and 'class="pp-stat pp-stat-info"' in html


def test_none_found_banner_never_uses_a_safe_wording():
    from src.engine import OVERALL_TEXT
    assert "안전을 의미하지는 않습니다" in OVERALL_TEXT["none_found"]
    assert "pp-lv-none_found" in theme.banner("none_found", "x", OVERALL_TEXT["none_found"])
