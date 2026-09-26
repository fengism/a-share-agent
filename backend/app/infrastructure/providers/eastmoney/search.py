from app.constants.market import (
    EASTMONEY_A_SHARE_LABELS,
    EASTMONEY_SEARCH_URL,
    EASTMONEY_UT_TRADE,
)
from app.core.market import is_a_share_code
from app.domain.stock import StockSearchItem


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
            "client": "web",
            "keyword": query,
            "pageIndex": 1,
            "pageSize": max(count, 10),
        }
        response = self.em_get_response(EASTMONEY_SEARCH_URL, params=params, headers=self.eastmoney_headers, timeout=10)
        data = response.json().get("result") or []
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
            item: 东财代码表接口返回的原始字典
        Return:
            StockSearchItem | None: 解析成功返回 StockSearchItem，非 A 股或无效数据返回 None
        """
        code = str(item.get("code") or "").strip()
        name = str(item.get("shortName") or item.get("name") or "").strip()
        if not code or not name:
            return None
        if not self._is_a_share_search_item(item):
            return None
        return StockSearchItem(code=code, name=name)

    def _is_a_share_search_item(self, item: dict) -> bool:
        """判断代码表条目是否为在市的 A 股。

        代码表把指数、板块、债券、基金/LOF、B 股、港美股、退市股和真正的 A 股混在
        一起返回，且 000001「上证指数」与 000001「平安银行」代码完全相同——只按代码
        判定会把指数当成股票。代码段与板块标签两道都过才认。

        Param:
            item: 东财代码表接口返回的原始字典
        Return:
            bool: True 表示是可分析的 A 股
        """
        code = str(item.get("code") or "").strip()
        if not is_a_share_code(code):
            return False
        # status=30 是终止上市；退市股与在市股代码段相同，必须单独排除。
        if item.get("status") == 30:
            return False
        label = str(item.get("label") or "").strip()
        # 标签缺失时只信代码段：宁可漏，也不要把指数当股票返回。
        return not label or label in EASTMONEY_A_SHARE_LABELS

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
