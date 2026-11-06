"""문제 신고 저장. 이 PC의 data/feedback/reports.jsonl 에만 저장하고 외부로 보내지 않는다.
약 목록은 동의했을 때만 포함한다.
"""
import json
import urllib.parse
import uuid
from datetime import datetime
from pathlib import Path

MAX_MESSAGE = 2000
MAX_CONTACT = 200
MAX_FILE_BYTES = 5_000_000
MAX_MAILTO_URL = 1800  # 메일 링크 길이 제한

KINDS = [
    "오류가 났어요 / 화면이 이상해요",
    "결과가 이상해요 (금기가 안 잡히거나 잘못 잡힘)",
    "제품·성분 정보가 틀렸어요",
    "이런 기능이 있으면 좋겠어요",
    "기타",
]


def save_report(directory, kind, message, contact="", context=None, app_info=None):
    """신고 1건을 저장하고 접수 번호를 반환한다."""
    message = (message or "").strip()
    if not message:
        raise ValueError("내용을 입력해 주세요.")
    d = Path(directory)
    d.mkdir(parents=True, exist_ok=True)
    f = d / "reports.jsonl"
    if f.exists() and f.stat().st_size > MAX_FILE_BYTES:
        raise RuntimeError("신고 저장 공간이 가득 찼습니다. 운영자에게 알려 주세요.")
    now = datetime.now()
    rid = now.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    rec = {
        "id": rid,
        "time": now.isoformat(timespec="seconds"),
        "type": kind,
        "message": message[:MAX_MESSAGE],
        "contact": (contact or "").strip()[:MAX_CONTACT],
        "context": context or {},
        "app": app_info or {},
    }
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rid


def load_reports(directory):
    f = Path(directory) / "reports.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue  # 깨진 줄은 건너뜀
    return out


def build_context(summary, drug_labels, include_drugs, error_text=None):
    """신고에 붙일 정보 (약 목록은 include_drugs 일 때만)."""
    ctx = {}
    if summary:
        ctx["result"] = summary
    if include_drugs and drug_labels:
        ctx["drugs"] = list(drug_labels)
    if error_text:
        ctx["error"] = error_text[-3000:]
    return ctx


def build_mailto(email, subject, body):
    """mailto 링크 생성 (URL 길이 제한에 맞게 본문을 줄임)."""
    def make(b):
        q = urllib.parse.urlencode({"subject": subject, "body": b}, quote_via=urllib.parse.quote)
        return f"mailto:{email}?{q}"

    url = make(body)
    while len(url) > MAX_MAILTO_URL and body:
        body = body[: int(len(body) * 0.8)]
        url = make(body.rstrip() + " …(길어서 일부만 담았어요. 전체는 앱의 '문제 신고'로 보내 주세요)")
    return url
