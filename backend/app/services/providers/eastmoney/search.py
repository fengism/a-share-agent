import json
import logging
import re

import pandas as pd
import requests


logger = logging.getLogger(__name__)

from app.constants.market import EASTMONEY_UT_TRADE

from app.models.stock import StockSearchItem


class SearchMixin:
    """东方财富 search 数据接口。"""

    def search_stocks(self, query: str, count: int = 10) -> list[StockSearchItem]:
        """搜索股票。

        根据关键词（代码、名称、拼音）搜索 A 股股票。

        Param:
            query: 搜索关键词（如 "600519"、"贵州茅台"、"GZMT"）
            count: 返回结果数量上限，默认 10
        Return:
            list[StockSearchItem]: 搜索结果列表，每个元素包含 code 和 name
        """
        params = {
            "input": query,
            "type": "14",
            "token": EASTMONEY_SEARCH_SUGGEST_TOKEN,
            "count": str(max(count, 5)),
        }
        response = self.em_get_response(EASTMONEY_SEARCH_SUGGEST_URL, params=params, headers=self.eastmoney_headers, timeout=10)
        data = response.json().get("QuotationCodeTable", {}).get("Data") or []
        results: list[StockSearchItem] = []
        seen_codes: set[str] = set()
        for item in data:
            parsed = self._parse_search_item(item)
            if parsed is None or parsed.code in seen_codes:
                continue
            results.append(parsed)
            seen_codes.add(parsed.code)
            if len(results) >= count:
                break
        return results

    def _parse_search_item(self, item: dict) -> StockSearchItem | None:
        """解析搜索结果项。

        Param:
            item: 东财搜索接口返回的原始字典
        Return:
            StockSearchItem | None: 解析成功返回 StockSearchItem，无效数据返回 None
        """
        code = str(item.get("Code") or item.get("SecurityCode") or "").strip()
        name = str(item.get("Name") or item.get("SecurityName") or item.get("PinYin") or "").strip()
        if not code or not name or len(code) != 6 or not code.isdigit():
            return None
        if not self._is_a_share_search_item(item):
            return None
        return StockSearchItem(code=code, name=name)

    def _is_a_share_search_item(self, item: dict) -> bool:
        """判断搜索结果是否为 A 股。

        通过代码、分类和市场信息综合判断。

        Param:
            item: 东财搜索接口返回的原始字典
        Return:
            bool: True 表示是 A 股，False 表示不是
        """
        classify = str(item.get("Classify") or item.get("SecurityTypeName") or "").strip()
        market = str(item.get("MarketType") or item.get("Market") or "").strip().upper()
        code = str(item.get("Code") or item.get("SecurityCode") or "").strip()
        if len(code) == 6 and code.isdigit():
            try:
                return classify_exchange(code) in {"SH", "SZ", "BJ"}
            except ValueError:
                return False
        if classify in A_SHARE_SEARCH_CLASSIFY:
            return True
        return market in {"SH", "SZ", "BJ", "CN"}

    def fetch_stock_names(self) -> list[dict]:
        """获取全市场股票代码和名称列表。

        通过东方财富 clist 接口分页获取所有 A 股的代码和名称。

        Return:
            list[dict]: 股票列表，每个字典包含:
                - code (str): 6 位股票代码
                - name (str): 股票名称（去除空格）
        """
        params={
                "pn": "1",
                "pz": "100",
                "po": "1",
                "np": "1",
                "ut": EASTMONEY_UT_TRADE,
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f14",
            }

        all_data = self._fetch_clist_diff(params, headers=self.eastmoney_headers, page_size=100)
        stocks: list[dict] = []
        for item in all_data:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", "")).replace(" ", "")
            if code and name and len(code) == 6 and code.isdigit():
                stocks.append({"code": code, "name": name})
        return stocks
