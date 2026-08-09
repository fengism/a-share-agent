import json
import logging
import random
import threading
import time
from urllib.parse import quote, urlsplit

import requests

from app.configuration import get_settings
from app.constants.http import EASTMONEY_HEADERS
from app.constants.market import EASTMONEY_CLIST_URL
from app.core.market import safe_float

logger = logging.getLogger(__name__)

_DATACENTER_HOST = "datacenter-web.eastmoney.com"


class EastMoneyCooldownError(RuntimeError):
    """东方财富风控冷却期内拒绝继续发起网络请求。"""

    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = max(0.0, retry_after_seconds)
        super().__init__(f"东方财富接口处于冷却期，请 {self.retry_after_seconds:.1f} 秒后重试")


class EastMoneyBase:
    """东方财富 API 基础设施。管理 session、限流、统一请求入口。"""

    name = "eastmoney"

    def __init__(self):
        self.REPORT_API = "https://reportapi.eastmoney.com/report/list"
        self.PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        self.UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self.DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        self._em_last_call_by_host: dict[str, float] = {}
        self._em_cooldown_until_by_host: dict[str, float] = {}
        self._em_transient_failures_by_host: dict[str, int] = {}
        self._em_lock = threading.Lock()
        self.em_session = requests.Session()
        self.em_session.trust_env = get_settings().http_trust_env
        self.em_session.headers.update({
            "User-Agent": self.UA,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://quote.eastmoney.com/",
            "Connection": "keep-alive",
        })
        self._base_eastmoney_headers = EASTMONEY_HEADERS.copy()

    @property
    def eastmoney_headers(self) -> dict:
        """动态构建东财请求头，每次读取最新 cookie 配置。"""
        headers = self._base_eastmoney_headers.copy()
        custom_cookie = get_settings().eastmoney_cookie
        if custom_cookie:
            headers["cookie"] = custom_cookie
        return headers

    def em_get_response(self, url, params=None, headers=None, timeout=15, **kwargs):
        """东财统一请求入口：全局串行节流、风控冷却与会话复用。

        Param:
            url: 请求地址
            params: URL 查询参数
            headers: 请求头
            timeout: 超时秒数
        Return:
            requests.Response 响应对象
        """
        settings = get_settings()
        with self._em_lock:
            now = time.monotonic()
            hostname = self._request_hostname(url)
            cooldown_until = self._em_cooldown_until_by_host.get(hostname, 0.0)
            if now < cooldown_until:
                raise EastMoneyCooldownError(cooldown_until - now)

            min_interval = self._min_interval_seconds(hostname, settings)
            jitter_min = max(0.0, settings.eastmoney_jitter_min_seconds)
            jitter_max = max(jitter_min, settings.eastmoney_jitter_max_seconds)
            last_call = self._em_last_call_by_host.get(hostname, 0.0)
            wait = min_interval - (now - last_call)
            if wait > 0:
                time.sleep(wait + random.uniform(jitter_min, jitter_max))

            self.em_session.trust_env = settings.http_trust_env
            try:
                response = self.em_session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout):
                failures = self._em_transient_failures_by_host.get(hostname, 0) + 1
                self._em_transient_failures_by_host[hostname] = failures
                threshold = max(1, settings.eastmoney_transient_failure_threshold)
                if failures >= threshold:
                    self._activate_em_cooldown(
                        hostname,
                        self._cooldown_seconds(hostname, settings),
                        "连续连接失败",
                    )
                raise
            finally:
                self._em_last_call_by_host[hostname] = time.monotonic()

            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code in {403, 429}:
                retry_after = self._retry_after_seconds(response)
                cooldown = max(self._cooldown_seconds(hostname, settings), retry_after)
                self._activate_em_cooldown(hostname, cooldown, f"HTTP {status_code}")
                response.raise_for_status()
                raise requests.HTTPError(f"东方财富风控响应: HTTP {status_code}", response=response)
            if status_code >= 500:
                failures = self._em_transient_failures_by_host.get(hostname, 0) + 1
                self._em_transient_failures_by_host[hostname] = failures
                threshold = max(1, settings.eastmoney_transient_failure_threshold)
                if failures >= threshold:
                    self._activate_em_cooldown(
                        hostname,
                        self._cooldown_seconds(hostname, settings),
                        f"HTTP {status_code}",
                    )
                response.raise_for_status()
            elif status_code >= 400:
                response.raise_for_status()
            else:
                self._em_transient_failures_by_host[hostname] = 0
            return response

    @staticmethod
    def _request_hostname(url: str) -> str:
        return urlsplit(url).hostname or ""

    @staticmethod
    def _min_interval_seconds(hostname: str, settings) -> float:
        if hostname == _DATACENTER_HOST:
            return max(0.0, settings.eastmoney_datacenter_min_interval_seconds)
        return max(0.0, settings.eastmoney_min_interval_seconds)

    @staticmethod
    def _cooldown_seconds(hostname: str, settings) -> float:
        if hostname == _DATACENTER_HOST:
            return max(0.0, settings.eastmoney_datacenter_cooldown_seconds)
        return max(0.0, settings.eastmoney_cooldown_seconds)

    def _activate_em_cooldown(self, hostname: str, seconds: float, reason: str) -> None:
        cooldown_seconds = max(0.0, seconds)
        self._em_cooldown_until_by_host[hostname] = max(
            self._em_cooldown_until_by_host.get(hostname, 0.0),
            time.monotonic() + cooldown_seconds,
        )
        logger.warning(
            "东方财富请求触发冷却: host=%s reason=%s cooldown_seconds=%.1f",
            hostname,
            reason,
            cooldown_seconds,
        )

    @staticmethod
    def _retry_after_seconds(response) -> float:
        raw_value = (getattr(response, "headers", {}) or {}).get("Retry-After")
        if raw_value is None:
            return 0.0
        try:
            return max(0.0, float(raw_value))
        except (TypeError, ValueError):
            return 0.0

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
            url += "&filter=" + quote(filter_str, safe="")
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
