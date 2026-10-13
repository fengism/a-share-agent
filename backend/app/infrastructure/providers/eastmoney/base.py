import json
import logging
import random
import threading
import time
from urllib.parse import quote, urlsplit

import requests

from app.configuration import get_settings
from app.constants.http import EASTMONEY_HEADERS
from app.constants.market import EASTMONEY_CLIST_URL, EASTMONEY_PUSH2_NODES
from app.core.exceptions import UpstreamUnavailableError
from app.core.market import safe_float
from app.infrastructure.http.proxy import (
    DIRECT_REQUEST,
    ProxyConfigError,
    ProxyScope,
    resolve_proxy_request,
)

logger = logging.getLogger(__name__)

_DATACENTER_HOST = "datacenter-web.eastmoney.com"
_PROXY_RETRY_BASE_SECONDS = 0.5
_PROXY_RETRY_JITTER_SECONDS = 0.3
# 代理链路连续失败到该次数后熔断，期间作用域内的请求直接跳过代理。
_PROXY_BREAKER_THRESHOLD = 3
_PROXY_BREAKER_COOLDOWN_SECONDS = 60.0
# 东方财富按出口 IP 风控，只有历史 K 线与资金流接口允许走公共出站代理；
# 实时行情、数据中心等接口继续直连，避免破坏既有反爬策略。
PROXY_SCOPE: ProxyScope = ProxyScope(
    hosts=frozenset({"push2his.eastmoney.com"}),
    path_prefixes=("/api/qt/stock/kline/get", "/api/qt/stock/fflow/daykline/get"),
)


class EastMoneyCooldownError(UpstreamUnavailableError):
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
        # 代理链路故障独立计数：代理抖动不代表上游被风控，不应触发 host 冷却。
        self._em_proxy_failures: int = 0
        # 代理熔断截止时间：熔断期内跳过代理，避免每次请求都空等整轮超时。
        self._em_proxy_open_until: float = 0.0
        self._em_lock = threading.Lock()
        self.em_session = requests.Session()
        # 东方财富反爬策略严禁代理访问：禁用环境变量代理并清空会话级代理配置。
        # K 线 / 资金流接口的独立代理以单次请求的 proxies 参数下发，不污染会话。
        self.em_session.trust_env = False
        self.em_session.proxies = {"http": None, "https": None}
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

    @staticmethod
    def _is_push2_host(hostname: str) -> bool:
        """判断是否属于东财 push2 实时行情节点（包含主节点及数字镜像节点）。"""
        if hostname == "push2.eastmoney.com":
            return True
        if hostname.endswith(".push2.eastmoney.com"):
            prefix = hostname[:-len(".push2.eastmoney.com")]
            return prefix.isdigit()
        return False

    def em_get_response(self, url, params=None, headers=None, timeout=15, **kwargs):
        """东财统一请求入口：全局串行节流、风控冷却、push2 节点池轮询容灾与会话复用。

        锁只保护节流/冷却状态；网络 I/O 与退避均在锁外执行，避免单次慢请求
        （例如经代理超时重试）阻塞其它东财接口。

        Param:
            url: 请求地址
            params: URL 查询参数
            headers: 请求头
            timeout: 超时秒数
        Return:
            requests.Response 响应对象
        """
        settings = get_settings()
        proxy_options = resolve_proxy_request(url, settings, PROXY_SCOPE)
        if proxy_options.active and self._proxy_breaker_open():
            logger.warning("东财代理处于熔断期，本次请求跳过代理直连")
            proxy_options = DIRECT_REQUEST
        request_timeout = proxy_options.timeout or timeout

        orig_hostname = self._request_hostname(url)
        is_push2 = self._is_push2_host(orig_hostname)
        with self._em_lock:
            if is_push2:
                candidate_hosts = list(EASTMONEY_PUSH2_NODES)
                random.shuffle(candidate_hosts)
                now = time.monotonic()
                # 优先选择未处于冷却期的节点
                available = [h for h in candidate_hosts if self._em_cooldown_until_by_host.get(h, 0.0) <= now]
                if available:
                    candidate_hosts = available
                else:
                    min_cooldown = min(self._em_cooldown_until_by_host.get(h, 0.0) for h in candidate_hosts)
                    raise EastMoneyCooldownError(max(0.0, min_cooldown - now))
            else:
                candidate_hosts = [orig_hostname]
                now = time.monotonic()
                cooldown_until = self._em_cooldown_until_by_host.get(orig_hostname, 0.0)
                if now < cooldown_until:
                    raise EastMoneyCooldownError(cooldown_until - now)

        last_exc = None
        for attempt_idx, hostname in enumerate(candidate_hosts):
            if is_push2 and hostname != orig_hostname:
                target_url = urlsplit(url)._replace(netloc=hostname).geturl()
            else:
                target_url = url

            # 锁内预约节流时隙后立即返回，网络 I/O 与退避 sleep 全部在锁外。
            wait = self._reserve_em_slot(hostname, settings)
            if wait is None:
                continue
            if wait > 0:
                time.sleep(wait)

            has_fallback = is_push2 and (attempt_idx < len(candidate_hosts) - 1)
            try:
                response = self._em_request(
                    target_url,
                    params=params,
                    headers=headers,
                    timeout=request_timeout,
                    proxies=proxy_options.proxies,
                    retries=proxy_options.retries,
                    **kwargs,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                if proxy_options.active:
                    self._record_proxy_failure()
                else:
                    self._record_host_failure(hostname, settings, "连续连接失败")
                last_exc = exc
                if has_fallback:
                    logger.warning("东财 push2 节点 %s 临时不可用 (%s)，切换备用节点重试...", hostname, exc)
                    continue
                raise
            finally:
                self._mark_em_call_done(hostname)

            status_code = int(getattr(response, "status_code", 0) or 0)
            if status_code in {403, 429}:
                retry_after = self._retry_after_seconds(response)
                cooldown = max(self._cooldown_seconds(hostname, settings), retry_after)
                self._activate_em_cooldown(hostname, cooldown, f"HTTP {status_code}")
                if has_fallback:
                    logger.warning("东财 push2 节点 %s 触发风控 HTTP %s，切换备用节点重试...", hostname, status_code)
                    continue
                response.raise_for_status()
                raise requests.HTTPError(f"东方财富风控响应: HTTP {status_code}", response=response)

            if status_code in {502, 503, 504}:
                self._record_host_failure(hostname, settings, f"HTTP {status_code}")
                if has_fallback:
                    logger.warning("东财 push2 节点 %s 返回 HTTP %s，切换备用节点重试...", hostname, status_code)
                    continue
                response.raise_for_status()

            if status_code >= 500:
                self._record_host_failure(hostname, settings, f"HTTP {status_code}")
                response.raise_for_status()
            elif status_code >= 400:
                response.raise_for_status()
            else:
                self._record_host_success(hostname, proxy_options.active)
            return response

        if last_exc:
            raise last_exc

    def _reserve_em_slot(self, hostname: str, settings) -> float | None:
        """在锁内预约本 host 的节流时隙，调用方在锁外等待。

        Param:
            hostname: 目标主机
            settings: 应用配置
        Return:
            float | None: 需要等待的秒数；host 处于冷却期时返回 None 表示跳过
        """
        with self._em_lock:
            now = time.monotonic()
            if now < self._em_cooldown_until_by_host.get(hostname, 0.0):
                return None
            min_interval = self._min_interval_seconds(hostname, settings)
            jitter_min = max(0.0, settings.eastmoney_jitter_min_seconds)
            jitter_max = max(jitter_min, settings.eastmoney_jitter_max_seconds)
            last_call = self._em_last_call_by_host.get(hostname, 0.0)
            wait = min_interval - (now - last_call)
            if wait < 0:
                wait = 0.0
            # 先把时隙推进到本次实际发起时刻，避免并发线程拿到同一空档一起冲出去
            self._em_last_call_by_host[hostname] = now + wait
            return wait + random.uniform(jitter_min, jitter_max)

    def _mark_em_call_done(self, hostname: str) -> None:
        """请求结束后记录真实发起时刻，用于下次节流计算。"""
        with self._em_lock:
            self._em_last_call_by_host[hostname] = time.monotonic()

    def _record_host_failure(self, hostname: str, settings, reason: str) -> None:
        """累加 host 瞬时失败计数，达到阈值则触发风控冷却。"""
        with self._em_lock:
            failures = self._em_transient_failures_by_host.get(hostname, 0) + 1
            self._em_transient_failures_by_host[hostname] = failures
            threshold = max(1, settings.eastmoney_transient_failure_threshold)
            if failures >= threshold:
                self._activate_em_cooldown(hostname, self._cooldown_seconds(hostname, settings), reason)

    def _record_host_success(self, hostname: str, via_proxy: bool) -> None:
        """请求成功：清零该 host 与代理的失败计数。"""
        with self._em_lock:
            self._em_transient_failures_by_host[hostname] = 0
            if via_proxy:
                self._em_proxy_failures = 0
                self._em_proxy_open_until = 0.0

    def _record_proxy_failure(self) -> None:
        """累加代理失败计数，达到阈值则熔断代理。

        代理整体不可用时，每次请求都走完整超时+重试会白白拖住调用方；
        熔断期内直接跳过代理，失败也快。
        """
        with self._em_lock:
            self._em_proxy_failures += 1
            failures = self._em_proxy_failures
            if failures >= _PROXY_BREAKER_THRESHOLD:
                self._em_proxy_open_until = time.monotonic() + _PROXY_BREAKER_COOLDOWN_SECONDS
                logger.warning(
                    "东财代理连续失败 %d 次，熔断 %.0f 秒，期间直接直连",
                    failures,
                    _PROXY_BREAKER_COOLDOWN_SECONDS,
                )

    def _proxy_breaker_open(self) -> bool:
        """代理熔断是否处于生效期。"""
        with self._em_lock:
            return time.monotonic() < self._em_proxy_open_until

    def _em_request(self, url: str, *, retries: int = 0, **kwargs):
        """发起东财请求，代理链路不稳定时按指数退避重试。

        Param:
            url: 请求地址
            retries: 额外重试次数（仅代理请求启用），0 表示不重试
        Return:
            requests.Response 响应对象
        """
        attempts = max(0, int(retries))
        for attempt in range(attempts + 1):
            try:
                return self.em_session.get(url, **kwargs)
            except requests.exceptions.InvalidSchema as exc:
                    raise ProxyConfigError(
                        "代理协议不受当前运行环境支持，请安装 PySocks（pip install 'requests[socks]'）"
                    ) from exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                    if attempt >= attempts:
                        raise
                    delay = _PROXY_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(
                        0, _PROXY_RETRY_JITTER_SECONDS,
                    )
                    logger.warning(
                        "东财代理请求失败，%.1fs 后第 %d/%d 次重试: %s",
                        delay,
                        attempt + 1,
                        attempts,
                        exc,
                    )
                    time.sleep(delay)

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
        now = time.monotonic()
        previous_until = self._em_cooldown_until_by_host.get(hostname, 0.0)
        self._em_cooldown_until_by_host[hostname] = max(
            previous_until,
            now + cooldown_seconds,
        )
        if previous_until > now:
            logger.debug(
                    "东方财富冷却期已生效: host=%s reason=%s remaining_seconds=%.1f",
                    hostname,
                    reason,
                    previous_until - now,
            )
            return
        logger.warning(
            "东方财富请求触发冷却: host=%s reason=%s cooldown_seconds=%.1f",
            hostname,
            reason,
            cooldown_seconds,
        )

    def em_cooldown_remaining(self, url: str) -> float:
        hostname = self._request_hostname(url)
        with self._em_lock:
            return max(
                    0.0,
                    self._em_cooldown_until_by_host.get(hostname, 0.0) - time.monotonic(),
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
                                    sort_columns: str = "", sort_types: str = "-1",
                                    page_number: int = 1) -> list[dict]:
        """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用。

        Param:
            report_name: 报表名称，对应东财数据中心的 reportName 参数
            columns: 返回字段，默认 "ALL"
            filter_str: 过滤条件字符串
            page_size: 每页条数
            page_number: 页码，从 1 开始
            sort_columns: 排序字段
            sort_types: 排序方向（-1 倒序，1 正序）
        Return:
            list[dict]: 报表数据行列表，每行为一个字典；无数据时返回空列表
        """
        params = {
            "reportName": report_name, "columns": columns,
            "pageNumber": str(page_number), "pageSize": str(page_size),
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

    def _fetch_clist_diff(self, params: dict[str, str], headers: dict | None = None, page_size: int = 100, url: str = EASTMONEY_CLIST_URL) -> list[dict]:
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
            except EastMoneyCooldownError:
                    logger.debug("东方财富 clist 跳过冷却期请求: page=%s", page)
                    break
            except requests.HTTPError as exc:
                    status_code = int(getattr(getattr(exc, "response", None), "status_code", 0) or 0)
                    if status_code in {403, 429} or status_code >= 500:
                        logger.debug(
                            "东方财富 clist 上游错误已由冷却日志记录: page=%s status=%s",
                            page,
                            status_code,
                        )
                    else:
                        logger.warning("东方财富 clist 请求失败: page=%s, error=%s", page, exc)
                    break
            except Exception as exc:
                    logger.warning("东方财富 clist 请求失败: page=%s, error=%s", page, exc)
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
