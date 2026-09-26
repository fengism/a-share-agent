"""东方财富股票搜索接口的回归护栏。

真实事故：``searchapi.eastmoney.com/api/suggest/get`` 已被改成 JSONP 包裹
（``jQuery35108723733748578402_1693632913001({...})``）并改返回论坛用户，载荷里不再有
``QuotationCodeTable``。``response.json()`` 必然抛 JSONDecodeError，被上层兜底成
「EastMoney 搜索建议 fallback 失败」，于是本地名称映射没命中的查询（行业黑话、口语化
提问）永远搜不到任何东西。

换用 ``search-codetable.eastmoney.com`` 后还有一个更隐蔽的坑：它把指数、板块、债券、
基金/LOF、B 股、港美股、退市股和真 A 股混在一起返回，而 000001「上证指数」与 000001
「平安银行」代码完全相同——只按代码段过滤会把指数当股票交给分析流程。
"""
import pytest

from app.constants.market import EASTMONEY_SEARCH_URL
from app.infrastructure.providers.eastmoney.search import SearchMixin

# 真实载荷（2026-09-26，keyword=000001 / 复星 / 红利ETF / 上证）混合了所有证券类型。
_CODETABLE_PAYLOAD = {
    "code": "0",
    "msg": "Success",
    "result": [
        {"code": "000001", "shortName": "上证指数", "label": "指数", "market": 1, "smallType": 1, "status": 10},
        {"code": "000001", "shortName": "平安银行", "label": "深A", "market": 0, "smallType": 6, "status": 10},
        {"code": "600519", "shortName": "贵州茅台", "label": "沪A", "market": 1, "smallType": 2, "status": 10},
        {"code": "300750", "shortName": "宁德时代", "label": "深A", "market": 0, "smallType": 80, "status": 10},
        {"code": "688981", "shortName": "中芯国际", "label": "科创", "market": 1, "smallType": 23, "status": 10},
        {"code": "920174", "shortName": "五新智能", "label": "京A", "market": 0, "smallType": 81, "status": 10},
        {"code": "835174", "shortName": "五新隧装(已切换)", "label": "退市", "market": 0, "smallType": 81, "status": 30},
        {"code": "200011", "shortName": "深物业B", "label": "深B", "market": 0, "smallType": 7, "status": 10},
        {"code": "510880", "shortName": "红利ETF华泰柏瑞", "label": "沪基", "market": 1, "smallType": 9, "status": 10},
        {"code": "159943", "shortName": "深证成指ETF大成", "label": "深基", "market": 0, "smallType": 10, "status": 10},
        {"code": "100706", "shortName": "国债0706", "label": "债券", "market": 0, "smallType": 8, "status": 10},
        {"code": "03750", "shortName": "宁德时代", "label": "HK", "market": 116, "smallType": 3, "status": 10},
        {"code": "00656", "shortName": "复星国际", "label": "HK", "market": 116, "smallType": 3, "status": 10},
        {"code": "BK0611", "shortName": "上证50_", "label": "板块", "market": 90, "smallType": 3, "status": 10},
        {"code": "MET", "shortName": "METIR PLC ORD", "label": "UK", "market": 155, "smallType": 1, "status": 10},
    ],
}


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def json(self) -> dict:
        return self._payload


class _FakeProvider(SearchMixin):
    """只桩掉网络入口，其余解析逻辑走真实实现。"""

    eastmoney_headers: dict = {}

    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.request: dict = {}

    def em_get_response(self, url, params=None, headers=None, timeout=15, **kwargs):
        self.request = {"url": url, "params": params}
        return _FakeResponse(self.payload)


@pytest.fixture
def provider() -> _FakeProvider:
    return _FakeProvider(_CODETABLE_PAYLOAD)


class TestEndpointContract:
    def test_uses_the_json_endpoint_not_the_jsonp_one(self, provider):
        provider.search_stocks("茅台")
        # suggest 接口现在返回 JSONP 包裹，改回去就是 JSONDecodeError 复发。
        assert provider.request["url"] == EASTMONEY_SEARCH_URL
        assert "searchapi.eastmoney.com" not in provider.request["url"]

    def test_reads_the_result_array(self, provider):
        provider.search_stocks("茅台")
        assert provider.request["params"]["keyword"] == "茅台"
        assert provider.request["params"]["pageIndex"] == 1


class TestAShareFiltering:
    def test_keeps_only_listed_a_shares(self, provider):
        results = provider.search_stocks("000001")
        names = [item.name for item in results]
        # 000001 上证指数与 000001 平安银行同代码：只能靠板块标签区分。
        assert "平安银行" in names
        assert "上证指数" not in names
        # 真 A 股一个都不该丢，重复代码也只留一条。
        assert results[0].code == "000001"
        assert len({item.code for item in results}) == len(results)

    def test_keeps_every_a_share_board(self):
        payload = {"result": _CODETABLE_PAYLOAD["result"][2:7]}
        kept = [(item.code, item.name) for item in _FakeProvider(payload).search_stocks("x")]
        assert kept == [
            ("600519", "贵州茅台"),
            ("300750", "宁德时代"),
            ("688981", "中芯国际"),
            ("920174", "五新智能"),
        ]

    @pytest.mark.parametrize(
        ("code", "name"),
        [
            ("510880", "红利ETF华泰柏瑞"),
            ("159943", "深证成指ETF大成"),
            ("100706", "国债0706"),
            ("200011", "深物业B"),
            ("03750", "宁德时代"),
            ("00656", "复星国际"),
            ("BK0611", "上证50_"),
            ("MET", "METIR PLC ORD"),
            ("835174", "五新隧装(已切换)"),
        ],
    )
    def test_rejects_non_stock_instruments(self, provider, code, name):
        assert all(item.code != code for item in provider.search_stocks("x")), name

    def test_deduplicates_repeated_codes(self, provider):
        codes = [item.code for item in provider.search_stocks("000001")]
        assert len(codes) == len(set(codes))

    def test_respects_count(self, provider):
        assert len(provider.search_stocks("股票", count=2)) == 2

    def test_tolerates_missing_label(self):
        # 标签缺失时只信代码段，不能因此把整批结果丢掉。
        payload = {"result": [{"code": "600519", "shortName": "贵州茅台"}]}
        assert [item.code for item in _FakeProvider(payload).search_stocks("茅台")] == ["600519"]

    def test_tolerates_empty_and_malformed_payloads(self):
        for payload in ({}, {"result": None}, {"result": [{}, {"code": "600519"}]}):
            assert _FakeProvider(payload).search_stocks("茅台") == []
