import json

import pytest

from src import feedback


def test_save_and_load_roundtrip(tmp_path):
    rid = feedback.save_report(tmp_path, feedback.KINDS[1], "  금기가 안 잡혀요  ", contact=" a@b.c ",
                               context={"result": {"overall": "none_found"}}, app_info={"dur_latest": "2026-07-21"})
    reps = feedback.load_reports(tmp_path)
    assert len(reps) == 1 and reps[0]["id"] == rid
    assert reps[0]["message"] == "금기가 안 잡혀요" and reps[0]["contact"] == "a@b.c"
    assert reps[0]["app"]["dur_latest"] == "2026-07-21"


def test_empty_message_is_rejected_and_nothing_is_written(tmp_path):
    with pytest.raises(ValueError):
        feedback.save_report(tmp_path, feedback.KINDS[0], "   ")
    assert feedback.load_reports(tmp_path) == []


def test_long_message_is_truncated_and_lines_are_json(tmp_path):
    feedback.save_report(tmp_path, "x", "가" * 5000, contact="c" * 999)
    rec = feedback.load_reports(tmp_path)[0]
    assert len(rec["message"]) == feedback.MAX_MESSAGE and len(rec["contact"]) == feedback.MAX_CONTACT
    assert json.loads((tmp_path / "reports.jsonl").read_text(encoding="utf-8").splitlines()[0])["id"] == rec["id"]


def test_store_refuses_when_file_too_big(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback, "MAX_FILE_BYTES", 10)
    feedback.save_report(tmp_path, "x", "첫 번째")
    with pytest.raises(RuntimeError):
        feedback.save_report(tmp_path, "x", "두 번째")


def test_drugs_are_included_only_with_consent():
    summary = {"overall": "contraindicated"}
    assert "drugs" not in feedback.build_context(summary, ["타이레놀정"], include_drugs=False)
    assert feedback.build_context(summary, ["타이레놀정"], include_drugs=True)["drugs"] == ["타이레놀정"]
    assert feedback.build_context(None, [], True, error_text="x" * 5000)["error"] == "x" * 3000


def test_broken_lines_are_skipped(tmp_path):
    (tmp_path / "reports.jsonl").write_text('{"id": "1", "time": "t", "type": "k", "message": "m"}\n깨진줄\n', encoding="utf-8")
    assert [r["id"] for r in feedback.load_reports(tmp_path)] == ["1"]


def test_mailto_is_encoded_and_length_limited():
    url = feedback.build_mailto("dev@example.com", "[점검기] 오류", "가" * 5000 + " & = ?")
    assert url.startswith("mailto:dev@example.com?subject=") and " " not in url
    assert len(url) <= feedback.MAX_MAILTO_URL + 200  # 한글은 퍼센트 인코딩으로 길어지므로 본문을 자른다
    short = feedback.build_mailto("dev@example.com", "s", "짧은 내용")
    assert "%EC%A7%A7%EC%9D%80" in short and "%E2%80%A6" not in short  # 짧으면 그대로
