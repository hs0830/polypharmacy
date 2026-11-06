import json

import pytest

import fetch_items as fi


class FakeResp:
    def __init__(self, payload=None, text=None, status=200):
        self._p, self.text, self.status_code = payload, text or json.dumps(payload or {}), status

    def json(self):
        if self._p is None:
            raise ValueError("not json")
        return self._p


def page(items, total, code="00"):
    return {"header": {"resultCode": code, "resultMsg": "OK"}, "body": {"items": items, "totalCount": total}}


class FakeSession:
    def __init__(self, data):
        self.data, self.calls = data, []

    def get(self, url, params=None, timeout=None):
        self.calls.append(params["pageNo"])
        r = self.data(params["pageNo"])
        return r


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(fi.time, "sleep", lambda *_: None)


def test_collect_paginates_dedupes_and_resumes(tmp_path):
    items = [{"ITEM_SEQ": str(i), "ITEM_NAME": f"약{i}"} for i in range(5)]
    s = FakeSession(lambda p: FakeResp(page(items[(p - 1) * 2: p * 2], 5)))
    out = fi.collect(s, "items", tmp_path, "KEY", rows=2, op="opX")
    import pandas as pd
    assert len(pd.read_csv(out)) == 5 and s.calls == [1, 2, 3]
    s2 = FakeSession(lambda p: (_ for _ in ()).throw(AssertionError("캐시가 있으면 호출하면 안 됨")))
    fi.collect(s2, "items", tmp_path, "KEY", rows=2, op="opX")  # 재실행: 네트워크 호출 없음
    assert s2.calls == []


def test_single_item_dict_and_nested_item_key():
    _, items = fi.parse_response(FakeResp({"response": {"header": {"resultCode": "00"},
                                                        "body": {"items": {"item": {"A": "1"}}, "totalCount": 1}}}))
    assert items == [{"A": "1"}]


def test_xml_error_response_is_reported(tmp_path):
    s = FakeSession(lambda p: FakeResp(text="<OpenAPI_ServiceResponse>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</OpenAPI_ServiceResponse>"))
    with pytest.raises(fi.ApiError) as e:
        fi.fetch_page(s, "opX", 1, 10, "KEY")
    assert "서비스키" in str(e.value)
    assert s.calls == [1]  # 키 오류는 재시도하지 않는다


def test_incomplete_collection_is_not_saved_silently(tmp_path):
    def data(p):
        return FakeResp(page([{"ITEM_SEQ": "1"}], 10)) if p == 1 else FakeResp(status=500, payload={})
    with pytest.raises(fi.ApiError):
        fi.collect(FakeSession(data), "items", tmp_path, "KEY", rows=1, op="opX")
    assert not (tmp_path / "item_list.csv").exists()


def test_key_from_env_is_decoded(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "ab%2Bc%3D%3D")
    assert fi.get_service_key() == "ab+c=="


def test_resolve_op_falls_back_to_working_candidate(monkeypatch):
    monkeypatch.setitem(fi.OP_CANDIDATES, "items", ["badOp08", "goodOp07"])

    class S:
        def get(self, url, params=None, timeout=None):
            if url.endswith("goodOp07"):
                return FakeResp(page([{"ITEM_SEQ": "1"}], 1))
            return FakeResp(status=404, payload={})

    assert fi.resolve_op(S(), "items", "KEY") == "goodOp07"


def test_resolve_op_reports_all_failures(monkeypatch):
    monkeypatch.setitem(fi.OP_CANDIDATES, "items", ["a", "b"])

    class S:
        def get(self, url, params=None, timeout=None):
            return FakeResp(status=404, payload={})

    with pytest.raises(fi.ApiError) as e:
        fi.resolve_op(S(), "items", "KEY")
    assert "a:" in str(e.value) and "b:" in str(e.value)


def test_default_endpoint_is_service08():
    assert fi.BASE_URL.endswith("DrugPrdtPrmsnInfoService08")


def test_easy_target_uses_its_own_service_url():
    urls = []

    class S:
        def get(self, url, params=None, timeout=None):
            urls.append(url)
            return FakeResp(page([{"itemSeq": "1"}], 1))

    assert fi.resolve_op(S(), "easy", "KEY") == "getDrbEasyDrugList"
    assert "DrbEasyDrugInfoService" in urls[-1] and urls[-1].startswith(fi.EASY_BASE_URL)
    fi.resolve_op(S(), "items", "KEY")
    assert urls[-1].startswith(fi.BASE_URL) and "DrbEasyDrugInfoService" not in urls[-1]


def test_easy_can_use_its_own_key(monkeypatch):
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY", "main")
    monkeypatch.delenv("DATA_GO_KR_SERVICE_KEY_EASY", raising=False)
    assert fi.get_service_key("easy") == "main"  # 별도 키가 없으면 공통 키
    monkeypatch.setenv("DATA_GO_KR_SERVICE_KEY_EASY", "easy-only")
    assert fi.get_service_key("easy") == "easy-only"
    assert fi.get_service_key("items") == "main" and fi.get_service_key() == "main"
