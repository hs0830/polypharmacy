#!/usr/bin/env python3
"""식약처 「의약품 제품 허가정보」 OpenAPI 수집기 (공공데이터포털).

- 서비스키는 환경변수 DATA_GO_KR_SERVICE_KEY 또는 .env 에서 읽는다 (코드에 넣지 않음).
- 페이지 단위로 data/raw/cache/ 에 저장하므로 끊겨도 이어받을 수 있다.
- 사용: python scripts/fetch_items.py --probe | --what items|ingredients|easy|all
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import requests

# 활용신청 페이지의 End Point (기본 Service08)
BASE_URL = os.environ.get(
    "MFDS_BASE_URL", "https://apis.data.go.kr/1471000/DrugPrdtPrmsnInfoService08"
)
# 버전에 따라 오퍼레이션 이름이 달라 후보를 차례로 시도 (MFDS_OP_* 로 직접 지정 가능)
OP_CANDIDATES = {
    "items": ["getDrugPrdtPrmsnInq08", "getDrugPrdtPrmsnInq07"],  # 제품 허가정보 목록
    "ingredients": ["getDrugPrdtMcpnDtlInq08", "getDrugPrdtMcpnDtlInq07"],  # 제품 주성분 상세(성분 1건당 1행)
}
for _what, _env in (("items", "MFDS_OP_ITEMS"), ("ingredients", "MFDS_OP_INGREDIENTS")):
    if os.environ.get(_env):
        OP_CANDIDATES[_what] = [os.environ[_env]]
# e약은요(효능·주의사항, 일반의약품 중심): 별도 활용신청 필요
EASY_BASE_URL = os.environ.get("MFDS_EASY_BASE_URL", "https://apis.data.go.kr/1471000/DrbEasyDrugInfoService")
OP_CANDIDATES["easy"] = [os.environ.get("MFDS_OP_EASY", "getDrbEasyDrugList")]
BASES = {"items": BASE_URL, "ingredients": BASE_URL, "easy": EASY_BASE_URL}
OUTPUT_NAMES = {"items": "item_list.csv", "ingredients": "ingredients.csv", "easy": "easy_drug.csv"}
DEDUPE_KEYS = {"items": ["ITEM_SEQ"], "ingredients": None, "easy": ["itemSeq"]}  # None = 전체 컬럼 기준


class ApiError(RuntimeError):
    pass


def load_env(path=".env"):
    """.env 를 읽는다 (이미 설정된 환경변수는 유지)."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def get_service_key(what=None):
    """easy 는 DATA_GO_KR_SERVICE_KEY_EASY 가 있으면 사용하고, 없으면 공통 키를 쓴다."""
    key = ""
    if what == "easy":
        key = os.environ.get("DATA_GO_KR_SERVICE_KEY_EASY", "").strip()
    key = key or os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        sys.exit(
            "서비스키가 없습니다. .env 파일에 DATA_GO_KR_SERVICE_KEY=발급받은키 를 적어 주세요.\n"
            "(발급 방법은 README.md 참고)"
        )
    # Encoding 키도 쓸 수 있게 디코딩 (requests 가 다시 인코딩)
    return unquote(key) if "%" in key else key


def parse_response(resp):
    """응답에서 (totalCount, items) 추출. 오류면 ApiError."""
    try:
        data = resp.json()
    except ValueError:
        # 인증키 오류 등은 type=json 이어도 XML 로 내려온다.
        snippet = resp.text[:300].replace("\n", " ")
        raise ApiError(f"JSON이 아닌 응답 (HTTP {resp.status_code}): {snippet}")

    root = data.get("response", data)
    header = root.get("header", {}) or {}
    body = root.get("body", {}) or {}
    code = str(header.get("resultCode", "00"))
    if code not in ("00", "0"):
        raise ApiError(f"API 오류 resultCode={code} msg={header.get('resultMsg')}")

    items = body.get("items", [])
    if isinstance(items, dict):
        items = items.get("item", items)
    if isinstance(items, dict):
        items = [items]
    total = int(body.get("totalCount", 0) or 0)
    return total, list(items or [])


def fetch_page(session, op, page, rows, key, retries=4, timeout=30, base=None):
    url = f"{base or BASE_URL}/{op}"
    params = {"serviceKey": key, "pageNo": page, "numOfRows": rows, "type": "json"}
    last = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            if resp.status_code != 200:
                raise ApiError(f"HTTP {resp.status_code}")
            return parse_response(resp)
        except (requests.RequestException, ApiError) as e:
            last = e
            msg = str(e)
            # 키 오류는 재시도하지 않음
            if "SERVICE_KEY" in msg.upper() or "resultCode=30" in msg or "resultCode=31" in msg:
                raise ApiError(f"{msg}\n서비스키가 등록/승인되지 않았거나 만료됐습니다. (README 참고)")
            wait = min(2**attempt, 20)
            if attempt < retries:
                print(f"  ! {op} {page}페이지 실패({attempt}/{retries}): {msg[:120]} -> {wait}초 후 재시도")
                time.sleep(wait)
    raise ApiError(f"{op} {page}페이지 수집 실패: {last}")


def resolve_op(session, what, key):
    """응답하는 오퍼레이션을 찾는다 (키 오류는 즉시 중단)."""
    errors = []
    for op in OP_CANDIDATES[what]:
        try:
            fetch_page(session, op, 1, 1, key, retries=1, base=BASES[what])
            return op
        except ApiError as e:
            if "서비스키" in str(e):
                raise
            errors.append(f"{op}: {str(e)[:100]}")
    raise ApiError(f"{what}: 응답하는 오퍼레이션을 찾지 못했습니다.\n  " + "\n  ".join(errors)
                   + "\n  (활용신청 페이지의 End Point/오퍼레이션 목록을 확인하고 MFDS_OP_* 환경변수로 지정하세요)")


def probe(session, key_for):
    print(f"End Point: {BASE_URL}")
    for what, ops in OP_CANDIDATES.items():
        print(f"\n=== {what} ===")
        for op in ops:
            try:
                total, items = fetch_page(session, op, 1, 2, key_for(what), retries=1, base=BASES[what])
            except ApiError as e:
                print(f"[{op}] 실패: {str(e)[:150]}")
                continue
            print(f"[{op}] 성공  totalCount={total}")
            if items:
                print("  필드:", list(items[0].keys()))
                for k, v in items[0].items():
                    print(f"    {k}: {str(v)[:80]}")
            else:
                print("  items 가 비어 있음")


def collect(session, what, out_dir, key, rows=100, max_pages=None, allow_partial=False, sleep=0.15, op=None):
    op = op or resolve_op(session, what, key)
    print(f"  오퍼레이션: {op}")
    cache = Path(out_dir) / "cache" / what
    cache.mkdir(parents=True, exist_ok=True)

    page, total = 1, None
    while True:
        f = cache / f"page_{page:06d}.json"
        if f.exists():
            cached = json.loads(f.read_text(encoding="utf-8"))
            total, items = cached["total"], cached["items"]
        else:
            total, items = fetch_page(session, op, page, rows, key, base=BASES[what])
            f.write_text(json.dumps({"total": total, "items": items}, ensure_ascii=False), encoding="utf-8")
            time.sleep(sleep)
        if page == 1 or page % 20 == 0:
            print(f"  [{what}] {page}페이지 / 총 {total}건")
        if not items or page * rows >= total:
            break
        page += 1
        if max_pages and page > max_pages:
            print(f"  --max-pages={max_pages} 에서 중단")
            break

    records = []
    for f in sorted(cache.glob("page_*.json")):
        records.extend(json.loads(f.read_text(encoding="utf-8"))["items"])

    df = pd.DataFrame(records)
    if df.empty:
        raise ApiError(f"{what}: 수집된 데이터가 없습니다.")
    keys = DEDUPE_KEYS[what]
    df = df.drop_duplicates(subset=[k for k in keys if k in df.columns] or None)

    complete = total is not None and len(records) >= total
    if not complete and not allow_partial and not max_pages:
        raise ApiError(
            f"{what}: {len(records)}건 / 총 {total}건 — 일부만 수집됐습니다. 다시 실행하면 이어서 받습니다. "
            "(일부만 저장하려면 --allow-partial)"
        )

    out = Path(out_dir) / OUTPUT_NAMES[what]
    df.to_csv(out, index=False, encoding="utf-8-sig")
    print(f"  저장: {out} ({len(df)}행, 컬럼 {len(df.columns)}개)")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--what", choices=["items", "ingredients", "easy", "all"], default="all",
                    help="all = items + ingredients (easy 는 별도 활용신청이 필요해 명시할 때만 수집)")
    ap.add_argument("--out", default="data/raw")
    ap.add_argument("--rows", type=int, default=100, help="페이지당 건수")
    ap.add_argument("--probe", action="store_true", help="각 API 2건만 조회해 필드 확인")
    ap.add_argument("--max-pages", type=int, default=None, help="테스트용 페이지 제한")
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args(argv)

    load_env()
    session = requests.Session()

    if args.probe:
        probe(session, get_service_key)
        return 0

    targets = ["items", "ingredients"] if args.what == "all" else [args.what]
    Path(args.out).mkdir(parents=True, exist_ok=True)
    for what in targets:
        print(f"\n>> {what} 수집 시작")
        try:
            collect(session, what, args.out, get_service_key(what), rows=args.rows,
                    max_pages=args.max_pages, allow_partial=args.allow_partial)
        except ApiError as e:
            print("중단:", e)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
