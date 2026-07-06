import json
import logging
from urllib.parse import quote
import random
import re
import threading
import time

logger = logging.getLogger(__name__)

import pandas as pd
import requests

from app.constants.http import EASTMONEY_HEADERS, COMMON_HEADERS
from app.constants.market import (
    A_SHARE_SEARCH_CLASSIFY,
    EASTMONEY_API_TOKEN,
    EASTMONEY_UT_HISTORY,
    EASTMONEY_UT_TRADE,
    EASTMONEY_CLIST_URL,
    INDEX_FALLBACKS,
    EASTMONEY_FLATTEN_FLAG,
    EASTMONEY_INDEX_QUOTE_FIELDS,
    EASTMONEY_INVESTOR_TYPE,
    EASTMONEY_KLINE_FIELDS1,
    EASTMONEY_KLINE_FIELDS2,
    EASTMONEY_SEARCH_SUGGEST_TOKEN,
    EASTMONEY_SEARCH_SUGGEST_URL,
    EASTMONEY_STOCK_KLINE_URL,
)
from app.models.search_item import NewsSearchItem
from app.models.stock import StockSearchItem
from app.services.base.data_provider import BaseDataProvider
from app.utils.intraday_utils import event_stream, normalize_intraday_df
from app.utils.symbol_utils import classify_exchange
from app.utils.symbol_utils import contains_stock_reference
from app.utils.data_clean import rename_and_keep_columns, safe_float
from app.config import get_settings



class EastMoneyBase(BaseDataProvider):
    """东方财富 API 基础设施。管理 session、限流、统一请求入口。"""

    def __init__(self):
        super().__init__(name="eastmoney", source_label="东方财富")
        self.REPORT_API = "https://reportapi.eastmoney.com/report/list"
        self.PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        self.UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self.DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        self._em_last_call = 0.0
        self._em_lock = threading.Lock()
        self.em_session = requests.Session()
        self.em_session.trust_env = get_settings().http_trust_env
        self.em_session.headers.update({"User-Agent": self.UA})
        self.EM_MIN_INTERVAL = 1.0
        self.eastmoney_headers = EASTMONEY_HEADERS.copy()
        # 支持自定义 cookie（配置为空时使用 http.py 中的内置默认值）
        custom_cookie = get_settings().eastmoney_cookie
        if custom_cookie:
            self.eastmoney_headers["cookie"] = custom_cookie
    def em_get_response(self, url, params=None, headers=None, timeout=15, **kwargs):
        """东财统一请求入口：自动节流 + 复用 session。

        Param:
            url: 请求地址
            params: URL 查询参数
            headers: 请求头
            timeout: 超时秒数
        Return:
            requests.Response 响应对象
        """
        with self._em_lock:
            wait = self.EM_MIN_INTERVAL - (time.time() - self._em_last_call)
            if wait > 0:
                time.sleep(wait + random.uniform(0.1, 0.5))
            try:
                return self.em_session.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
            finally:
                self._em_last_call = time.time()
    def fetch_datacenter_report(self, report_name: str, columns: str = "ALL",
                                filter_str: str = "", page_size: int = 50,
                                sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
        """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用。

        Param:
            report_name: 报表名称，对应东财数据中心的 reportName 参数
            columns: 返回字段，默认 "ALL"
            filter_str: 过滤条件字符串
            page_size: 每页条数
            sort_columns: 排序字段
            sort_types: 排序方向（-1 倒序，1 正序）
        Return:
            list[dict]: 报表数据行列表，每行为一个字典；无数据时返回空列表
        """
        params = {
            "reportName": report_name, "columns": columns,
            "pageNumber": "1", "pageSize": str(page_size),
            "sortColumns": sort_columns, "sortTypes": sort_types,
            "source": "WEB", "client": "WEB",
        }
        # filter 需要手工拼入 URL：requests 不编码 ' " < > 等字符，
        # 但东财 ANTLR 解析器要求 %27 %22 %3C %3E 形式。
        url = self.DATACENTER_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        if filter_str:
            _quote = __import__("urllib.parse", fromlist=["quote"]).quote
            url += "&filter=" + _quote(filter_str, safe="")
        r = self.em_get_response(url, headers={"User-Agent": self.UA}, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
        return []
    def _fetch_clist_diff(self, params: dict[str, str], headers: dict = None, page_size: int = 100, url: str = EASTMONEY_CLIST_URL) -> list[dict]:
        """分页获取东方财富 clist 接口的全部 diff 数据。

        自动处理分页，直到数据取完或达到上限。

        Param:
            params: 请求参数字典（不含分页参数 pn/pz，由本方法自动添加）
            headers: 可选的自定义请求头，默认使用实例级东财请求头
            page_size: 每页条数，默认 100
            url: clist 接口 URL，默认使用 EASTMONEY_CLIST_URL
        Return:
            list[dict]: 所有页的 diff 数据合并列表
        """
        all_data: list[dict] = []
        page = 1
        while True:
            req_params = {**params, "pn": str(page), "pz": str(page_size)}
            try:
                response = self.em_get_response(url, params=req_params, headers=headers, timeout=15)
                if response.status_code != 200:
                    _log = __import__("logging").getLogger(__name__)
                    _log.warning(f"东方财富 clist HTTP 错误: page={page}, status={response.status_code}")
                    break
                data_json = response.json()
            except Exception as exc:
                _log = __import__("logging").getLogger(__name__)
                _log.warning(f"东方财富 clist 请求失败: page={page}, error={exc}")
                break
            data = data_json.get("data") or {}
            diff = data.get("diff") or []
            if not diff:
                break

            all_data.extend(diff)
            total = int(data.get("total") or 0)
            if total and page * page_size >= total:
                break
            if len(diff) < page_size:
                break
            page += 1
        return all_data
    def _parse_json_from_text(self, text: str, error_message: str) -> dict:
        """从可能包含 JSONP 包装的文本中提取 JSON 数据。

        Param:
            text: 原始响应文本，可能包含 callback 包装
            error_message: 解析失败时的错误提示
        Return:
            dict: 解析后的 JSON 字典
        """
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(error_message)
        return json.loads(text[start:end + 1])
    def _fmt_amount(self, value) -> float | None:
        """格式化金额为万元单位。

        Param:
            value: 原始金额值（元）
        Return:
            float | None: 万元为单位的金额，保留 2 位小数；输入无效返回 None
        """
        result = safe_float(value)
        if result is None:
            return None
        return round(result / 10000, 2)
