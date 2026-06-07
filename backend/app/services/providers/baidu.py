import logging
import time

import pandas as pd

from app.services.base.data_provider import BaseDataProvider
from app.models.search_item import NewsSearchItem
from app.utils import http_client
from app.utils.symbol_utils import contains_stock_reference
from app.constants.http import BD_HEADERS, BD_HEADERS_WITH_COOKIE

logger = logging.getLogger(__name__)


def _baidu_request_json(url: str, params: dict, headers: dict | None = None, timeout: int = 10) -> dict:
    """通过共享 http_client 发送 GET 并解析 JSON，自动尊重 http_trust_env 配置。

    Param:
        url: 请求 URL
        params: URL 查询参数
        headers: 可选请求头；为空则使用 self.default_headers
        timeout: 超时秒数，默认 10
    Return:
        解析后的 JSON 字典
    """
    response = http_client.get(url, params=params, headers=headers, timeout=timeout)
    return response.json()


class BaiduDataProvider(BaseDataProvider):
    """Purpose: 封装百度股市通 PAE 接口，提供 K线、股票名称、概念板块、资金流向及 7x24 快讯等数据。"""

    DEFAULT_BASE_URL = "https://finance.pae.baidu.com"
    DEFAULT_TIMEOUT = 10
    MAX_PAGES = 40
    PAGE_SIZE = 200
    NAME_LIST_SLEEP_SECONDS = 0.5

    def __init__(self):
        """初始化 BaiduDataProvider，配置请求头与分页参数。"""
        super().__init__(name="baidu", source_label="百度")
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://gushitong.baidu.com",
            "Accept": "application/json",
            "Origin": "https://gushitong.baidu.com",
            "Host": "finance.pae.baidu.com",
        }

    def _request(self, path: str, params: dict, headers: dict | None = None, timeout: int | None = None) -> dict:
        """通过共享 HTTP 客户端发起 GET 请求并解析 JSON。

        Param:
            path: URL 路径（如 /selfselect/getstockquotation），会自动拼接 base_url
            params: URL 查询参数
            headers: 可选请求头；为空则使用 default_headers
            timeout: 超时秒数；为空使用 DEFAULT_TIMEOUT
        Return:
            解析后的 JSON 字典
        """
        url = path if path.startswith("http") else f"{self.DEFAULT_BASE_URL}{path}"
        return _baidu_request_json(
            url,
            params,
            headers=headers or self.default_headers,
            timeout=timeout or self.DEFAULT_TIMEOUT,
        )

    @staticmethod
    def _check_result_code(data: dict) -> None:
        """校验百度接口业务码，非 0 时抛出 RuntimeError。

        Param:
            data: 接口返回的 JSON 字典
        Return:
            无；成功静默返回，失败抛出异常
        """
        if str(data.get("ResultCode", -1)) != "0":
            raise RuntimeError(f"百度PAE错误: {data}")

    def fetch_stock_kline(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """百度股市通K线 — 独有能力: 返回时自带 ma5/ma10/ma20 均价。
        稳定数据源: 百度股市通 PAE 接口，无依赖第三方库。

        Param:
            code: 股票代码
            start_date: 起始时间 格式为 YYYYMMDD
            end_date: 结束时间 格式为 YYYYMMDD
        Return:
            包含日期、OHLC、成交量、成交额、振幅、涨跌幅、换手率、昨收等列的 DataFrame
        """
        params = {
            "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
            "isFutures": "false", "isStock": "true", "newFormat": "1",
            "group": "quotation_kline_ab", "finClientType": "pc",
            "code": code, "start_time": start_date, "ktype": "1",
        }
        data = self._request("/selfselect/getstockquotation", params)
        keys = data.get("Result", {}).get("newMarketData", {}).get("keys", [])
        rows = data.get("Result", {}).get("newMarketData", {}).get("marketData", "").split(";")
        df = pd.DataFrame([row.split(",") for row in rows], columns=keys)
        df["date"] = df["time"].apply(lambda x: x[:12])
        df = df[["date", "open", "close", "high", "low", "volume", "amount", "range", "ratio", "turnoverratio", "preClose"]]
        df.columns = [
            "date", "open", "close", "high", "low",
            "volume", "amount", "amplitude", "change_pct", "turnover_pct", "pre_close",
        ]
        return df

    def fetch_stock_names(self) -> list[dict]:
        """分页拉取全市场 A/B 股名称代码对照表（最多 40 页、每页 200 条）。

        Return:
            [{"code": 股票代码, "name": 股票名称}, ...] 列表
        """
        all_stocks: list[dict] = []
        for page_no in range(self.MAX_PAGES):
            data = self._request(
                "/selfselect/getmarketrank",
                params={
                    "sort_type": "1",
                    "sort_key": "14",
                    "from_mid": "1",
                    "group": "pclist",
                    "type": "ab",
                    "finClientType": "pc",
                    "pn": str(page_no * self.PAGE_SIZE),
                    "rn": str(self.PAGE_SIZE),
                },
            )
            time.sleep(self.NAME_LIST_SLEEP_SECONDS)

            if data.get("ResultCode") != "0":
                break
            rank = (
                data.get("Result", {}).get("Result", [{}])[0]
                .get("DisplayData", {}).get("resultData", {}).get("tplData", {})
                .get("result", {}).get("rank", [])
            )
            if not rank:
                break
            for item in rank:
                code = str(item.get("code", ""))
                name = str(item.get("name", "")).replace(" ", "")
                if code and name and len(code) == 6 and code.isdigit():
                    all_stocks.append({"code": code, "name": name})
            if len(rank) < self.PAGE_SIZE:
                break
        return all_stocks

    def fetch_stock_concept_blocks(self, code: str) -> dict:
        """百度股市通概念板块归属。

        Param:
            code: 6 位股票代码
        Return:
            包含 industry/concept/region/concept_tags 四个分类的字典
        """
        data = self._request(
            "/api/getrelatedblock",
            params={
                "stock": __import__("json").dumps({"market": "ab", "type": "stock", "code": code}),
                "finClientType": "pc",
            },
        )
        self._check_result_code(data)

        result: dict = {"industry": [], "concept": [], "region": [], "concept_tags": []}
        blocks = data.get("Result", {}).get(code, [])
        for block in blocks:
            block_name = block.get("name", "")
            for item in block.get("list", []):
                entry = {
                    "name": item.get("name", ""),
                    "change_pct": item.get("increase", ""),
                    "desc": item.get("desc", ""),
                }
                if block_name == "行业":
                    result["industry"].append(entry)
                elif block_name == "概念":
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif block_name == "地域":
                    result["region"].append(entry)
        return result

    def fetch_stock_fund_flow(self, code: str) -> list[dict]:
        """获取个股资金流数据（百度 PAE fundflow 接口）。

        Param:
            code: 6 位股票代码
        Return:
            百度接口 fundFlowSpread 原始字典列表（含超大单/大单/中单/小单等字段）
        """
        data = self._request(
            "/vapi/v1/fundflow",
            params={
                "finance_type": "stock",
                "fund_flow_type": "",
                "market": "ab",
                "code": code,
                "type": "stock",
                "finClientType": "pc",
            },
        )
        self._check_result_code(data)
        return data.get("Result", {}).get("content", {}).get("fundFlowSpread", {}).get("result", [])

    def fetch_market_kuaixun(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """百度 7x24 快讯（ExpressNews），可选按股票代码/名称过滤。

        Param:
            code: 可选，6 位股票代码
            code_name: 可选，股票名称
        Return:
            NewsSearchItem 列表
        """
        data = self._request(
            "/selfselect/expressnews",
            params={
                "rn": "20",
                "pn": "0",
                "tag": "",
                "filterByUserStocks": "0",
                "finClientType": "pc",
            },
            headers=BD_HEADERS,
        )
        self._check_result_code(data)

        results: list[NewsSearchItem] = []
        for item in data.get("Result", {}).get("content", {}).get("list", []):
            title = str(item.get("title") or "").strip()
            content = self._join_express_content(item.get("content", {}))
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            publish_time = self._parse_timestamp(item.get("publish_time"))
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:500],
                    source="百度 7x24 快讯",
                    publish_time=str(publish_time),
                    url=item.get("third_url", ""),
                    author=item.get("author", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    @staticmethod
    def _join_express_content(content_obj: dict) -> str:
        """拼接百度 7x24 快讯的 content.items[*].data 字段。

        Param:
            content_obj: 百度快讯原始 content 字段
        Return:
            拼接后的纯文本内容
        """
        items = content_obj.get("items", []) if isinstance(content_obj, dict) else []
        return "".join(str(item.get("data", "")) for item in items)

    def _fetch_fund_flow_rank(self, block_type: str) -> list[dict]:
        """通用资金流排名接口：支持行业/概念板块。

        Param:
            block_type: HY=行业, GN=概念
        Return:
            统一格式的资金流条目列表
        """
        data = self._request(
            "/sapi/v1/ranks",
            params={
                "bizType": "fundflow_rank",
                "style": "tablelist",
                "fundflowRankTarget": "block",
                "market": "ab",
                "sortKey": "",
                "sortType": "",
                "blockType": block_type,
                "pn": "0",
                "rn": "200",
                "finClientType": "pc",
            },
            headers=BD_HEADERS_WITH_COOKIE,
        )
        self._check_result_code(data)
        items = data.get("Result", {}).get("list", {}).get("body", [])
        return [
            {
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "mainNetIn": item.get("mainNetIn", 0),
                "mainTotalIn": item.get("mainTotalIn", 0),
                "totalAmount": item.get("totalAmount", 0),
            }
            for item in items
        ]

    def fetch_industry_fund_flow(self) -> list[dict]:
        """获取行业资金流向排名（百度 PAE fundflow_rank HY 板块）。

        Return:
            资金流条目列表，每项含 code/name/mainNetIn/mainTotalIn/totalAmount
        """
        return self._fetch_fund_flow_rank("HY")

    def fetch_concept_fund_flow(self) -> list[dict]:
        """获取概念资金流向排名（百度 PAE fundflow_rank GN 板块）。

        Return:
            资金流条目列表，每项含 code/name/mainNetIn/mainTotalIn/totalAmount
        """
        return self._fetch_fund_flow_rank("GN")

    def fetch_trade_dates(self) -> list[dict]:
        """获取交易日期列表（百度 PAE marketStatus 接口）。

        Return:
            A/B 股市场日期信息列表
        """
        data = self._request(
            "/sapi/v1/marketquote",
            params={"bizType": "marketStatus", "finClientType": "pc"},
            headers=BD_HEADERS_WITH_COOKIE,
        )
        self._check_result_code(data)
        return data.get("Result", {}).get("index", {}).get("ab", {}).get("marketDate", [])


baidu_provider = BaiduDataProvider()


if __name__ == "__main__":
    data = baidu_provider.fetch_market_kuaixun()
    print(data)
