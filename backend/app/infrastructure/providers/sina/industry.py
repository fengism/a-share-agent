"""Sina Finance Shenwan industry nodes and constituent mappings."""

import json
import logging
import re
import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from threading import Lock, local
from typing import Any

import requests

from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import SINA_MARKET_HQ_URL, SINA_MARKET_NODES_URL

logger = logging.getLogger(__name__)

_SW_LEVELS = (1, 2, 3)
_SW_NODE_PATTERN = re.compile(r"^sw([123])_(\d{6})$")
_SW_BRANCH_LABELS = {1: "申万一级", 2: "申万二级", 3: "申万三级"}
_SW_MIN_NODE_COUNTS = {1: 30, 2: 120, 3: 300}
_SW_MIN_MAPPING_SIZE = 4000
_SW_MIN_CROSS_LEVEL_COVERAGE = 0.98
_SW_PAGE_SIZE = 100
_SW_MAX_PAGES = 20
_SW_WORKERS = 8
_SW_REQUEST_ATTEMPTS = 3
_SW_RETRY_DELAY_SECONDS = 0.2


@dataclass(frozen=True)
class SinaSwIndustryNode:
    level: int
    name: str
    node: str


@dataclass
class _FetchStats:
    retries: int = 0
    _lock: Any = field(default_factory=Lock, repr=False)

    def record_retry(self) -> None:
        with self._lock:
            self.retries += 1


class _TransientPayloadError(RuntimeError):
    pass


class _ThreadLocalSessionPool:
    """Create one configured requests session per component worker thread."""

    def __init__(
        self,
        base_session: requests.Session,
        session_factory: Callable[[], requests.Session],
    ) -> None:
        self._base_session = base_session
        self._session_factory = session_factory
        self._local = local()
        self._sessions: list[requests.Session] = []
        self._lock = Lock()

    def get(self) -> requests.Session:
        worker_session = getattr(self._local, "session", None)
        if worker_session is not None:
            return worker_session
        worker_session = self._session_factory()
        _copy_session_configuration(self._base_session, worker_session)
        self._local.session = worker_session
        with self._lock:
            self._sessions.append(worker_session)
        return worker_session

    def close(self) -> None:
        for worker_session in self._sessions:
            worker_session.close()


SwNodeMap = dict[int, list[SinaSwIndustryNode]]
SwMappingPair = tuple[dict[str, str], list[str]]
SwMappingMap = dict[int, SwMappingPair]
ComponentLoader = Callable[[str], list[dict[str, Any]]]


def _copy_session_configuration(base_session: requests.Session, worker_session: requests.Session) -> None:
    """Copy immutable request configuration without sharing mutable session state."""
    for attribute in ("trust_env", "verify", "cert", "auth", "max_redirects"):
        if hasattr(base_session, attribute):
            setattr(worker_session, attribute, getattr(base_session, attribute))
    if hasattr(base_session, "headers") and hasattr(worker_session, "headers"):
        worker_session.headers.update(base_session.headers)
    if hasattr(base_session, "proxies") and hasattr(worker_session, "proxies"):
        worker_session.proxies.update(base_session.proxies)


def _find_named_branch(payload: object, name: str) -> list[Any] | None:
    if not isinstance(payload, list):
        return None
    if payload and payload[0] == name:
        return payload
    for child in payload:
        found = _find_named_branch(child, name)
        if found is not None:
            return found
    return None


def _parse_branch_nodes(branch: list[Any], level: int) -> list[SinaSwIndustryNode]:
    raw_nodes = branch[1] if len(branch) > 1 and isinstance(branch[1], list) else []
    nodes: list[SinaSwIndustryNode] = []
    seen: set[str] = set()
    for item in raw_nodes:
        if not isinstance(item, list) or len(item) < 3:
            continue
        name = str(item[0] or "").strip()
        node = str(item[2] or "").strip()
        match = _SW_NODE_PATTERN.fullmatch(node)
        if not name or match is None or int(match.group(1)) != level or node in seen:
            continue
        seen.add(node)
        nodes.append(SinaSwIndustryNode(level=level, name=name, node=node))
    return nodes


def parse_sw_industry_nodes(payload: object) -> SwNodeMap:
    """Extract Shenwan level-one, level-two and level-three nodes below A shares."""
    a_share_branch = _find_named_branch(payload, "A股")
    if a_share_branch is None:
        raise RuntimeError("新浪行情分类缺少 A股 节点")
    children = a_share_branch[1] if len(a_share_branch) > 1 and isinstance(a_share_branch[1], list) else []
    result: SwNodeMap = {}
    for level, label in _SW_BRANCH_LABELS.items():
        branch = next(
            (item for item in children if isinstance(item, list) and item and item[0] == label),
            None,
        )
        if branch is None:
            raise RuntimeError(f"新浪行情分类缺少 {label} 节点")
        nodes = _parse_branch_nodes(branch, level)
        if not nodes:
            raise RuntimeError(f"新浪{label}分类为空")
        result[level] = nodes
    return result


def _is_a_share_code(code: str) -> bool:
    if len(code) != 6 or not code.isdigit():
        return False
    return code.startswith(
        (
            "600",
            "601",
            "603",
            "605",
            "688",
            "689",
            "000",
            "001",
            "002",
            "003",
            "300",
            "301",
            "4",
            "8",
            "920",
        )
    )


def _is_retryable_request_error(error: Exception) -> bool:
    if isinstance(error, _TransientPayloadError):
        return True
    if isinstance(error, requests.HTTPError):
        status_code = error.response.status_code if error.response is not None else None
        return status_code == 429 or (status_code is not None and status_code >= 500)
    return isinstance(error, requests.RequestException)


def _request_json_list(
    session: requests.Session,
    url: str,
    *,
    context: str,
    params: dict[str, Any] | None = None,
    max_attempts: int = _SW_REQUEST_ATTEMPTS,
    retry_delay_seconds: float = _SW_RETRY_DELAY_SECONDS,
    stats: _FetchStats | None = None,
) -> list[Any]:
    if max_attempts <= 0 or retry_delay_seconds < 0:
        raise ValueError("新浪申万行业重试参数无效")

    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(
                url,
                params=params,
                headers=SINA_FINANCE_HEADERS,
                timeout=15,
            )
            response.raise_for_status()
            try:
                payload = json.loads(response.text)
            except json.JSONDecodeError as exc:
                raise _TransientPayloadError(f"{context}返回非 JSON") from exc
            if not isinstance(payload, list):
                raise _TransientPayloadError(f"{context}返回格式异常")
            return payload
        except Exception as error:
            retryable = _is_retryable_request_error(error)
            if not retryable or attempt >= max_attempts:
                if isinstance(error, _TransientPayloadError):
                    raise RuntimeError(str(error)) from error
                raise
            if stats is not None:
                stats.record_retry()
            delay = retry_delay_seconds * (2 ** (attempt - 1))
            logger.warning(
                "新浪申万请求临时失败，准备重试: context=%s attempt=%s/%s delay=%.2fs error=%s",
                context,
                attempt,
                max_attempts,
                delay,
                type(error).__name__,
            )
            if delay > 0:
                time.sleep(delay)

    raise RuntimeError(f"{context}请求未返回结果")


def fetch_sw_industry_components(
    session: requests.Session,
    node: str,
    *,
    page_size: int = _SW_PAGE_SIZE,
    max_pages: int = _SW_MAX_PAGES,
    max_attempts: int = _SW_REQUEST_ATTEMPTS,
    retry_delay_seconds: float = _SW_RETRY_DELAY_SECONDS,
    stats: _FetchStats | None = None,
) -> list[dict[str, Any]]:
    """Fetch every A-share constituent for one validated Sina Shenwan node."""
    if _SW_NODE_PATTERN.fullmatch(node) is None:
        raise ValueError(f"无效新浪申万行业节点: {node}")
    if page_size <= 0 or max_pages <= 0:
        raise ValueError("新浪申万行业分页参数必须为正数")

    records: list[dict[str, Any]] = []
    seen_codes: set[str] = set()
    for page in range(1, max_pages + 1):
        payload = _request_json_list(
            session,
            SINA_MARKET_HQ_URL,
            context=f"新浪申万行业成分 node={node} page={page}",
            params={
                "page": page,
                "num": page_size,
                "sort": "symbol",
                "asc": 1,
                "node": node,
                "symbol": "",
                "_s_r_a": "init",
            },
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
            stats=stats,
        )
        for item in payload:
            if not isinstance(item, Mapping):
                continue
            code = str(item.get("code") or "").strip()
            if not _is_a_share_code(code) or code in seen_codes:
                continue
            seen_codes.add(code)
            record = dict(item)
            record["code"] = code
            records.append(record)
        if len(payload) < page_size:
            return records

    raise RuntimeError(f"新浪申万行业成分未在 {max_pages} 页内结束: node={node}")


def build_sw_industry_mappings(
    nodes_by_level: SwNodeMap,
    component_loader: ComponentLoader,
    *,
    max_workers: int = _SW_WORKERS,
) -> SwMappingMap:
    """Build deterministic stock-to-industry mappings for all Shenwan levels."""
    ordered_nodes = [node for level in _SW_LEVELS for node in nodes_by_level.get(level, [])]
    members_by_node: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="sina-sw-industry") as executor:
        futures = {node.node: executor.submit(component_loader, node.node) for node in ordered_nodes}
        for node in ordered_nodes:
            members = futures[node.node].result()
            if not members:
                raise RuntimeError(f"新浪申万行业成分为空: node={node.node}, name={node.name}")
            members_by_node[node.node] = members

    result: SwMappingMap = {}
    for level in _SW_LEVELS:
        mapping: dict[str, str] = {}
        industry_names: list[str] = []
        for node in nodes_by_level.get(level, []):
            industry_names.append(node.name)
            for item in members_by_node[node.node]:
                code = str(item.get("code") or "").strip()
                if not _is_a_share_code(code):
                    continue
                previous = mapping.get(code)
                if previous is not None and previous != node.name:
                    raise RuntimeError(f"新浪申万{level}级股票重复归属: code={code}, industries={previous},{node.name}")
                mapping[code] = node.name
        result[level] = (mapping, sorted(set(industry_names)))
    return result


def validate_sw_mapping_coverage(
    mappings: SwMappingMap,
    *,
    minimum_coverage: float = _SW_MIN_CROSS_LEVEL_COVERAGE,
) -> float:
    """Require adjacent Shenwan levels to describe nearly the same stock universe."""
    if not 0 <= minimum_coverage <= 1:
        raise ValueError("申万行业跨级覆盖率阈值必须在 0 到 1 之间")
    coverage_by_pair: list[float] = []
    for lower_level, upper_level in zip(_SW_LEVELS[:-1], _SW_LEVELS[1:], strict=True):
        lower_codes = set(mappings.get(lower_level, ({}, []))[0])
        upper_codes = set(mappings.get(upper_level, ({}, []))[0])
        if not lower_codes or not upper_codes:
            raise RuntimeError(
                "新浪申万跨级股票覆盖率无法计算："
                f"level{lower_level}={len(lower_codes)}, level{upper_level}={len(upper_codes)}"
            )
        common_count = len(lower_codes & upper_codes)
        coverage = min(common_count / len(lower_codes), common_count / len(upper_codes))
        if coverage < minimum_coverage:
            raise RuntimeError(
                "新浪申万跨级股票覆盖率不足: "
                f"coverage={coverage:.4f}, minimum={minimum_coverage:.4f}, "
                f"level{lower_level}={len(lower_codes)}, level{upper_level}={len(upper_codes)}, "
                f"common={common_count}"
            )
        coverage_by_pair.append(coverage)
    return min(coverage_by_pair)


def fetch_sw_industry_mappings(
    session: requests.Session,
    *,
    session_factory: Callable[[], requests.Session] = requests.Session,
) -> SwMappingMap:
    """Fetch and validate complete Sina Shenwan level-one through level-three mappings."""
    started_at = time.perf_counter()
    stats = _FetchStats()
    payload = _request_json_list(
        session,
        SINA_MARKET_NODES_URL,
        context="新浪申万行业分类",
        stats=stats,
    )
    nodes_by_level = parse_sw_industry_nodes(payload)
    for level, minimum in _SW_MIN_NODE_COUNTS.items():
        count = len(nodes_by_level.get(level, []))
        if count < minimum:
            raise RuntimeError(f"新浪申万{level}级分类不足: {count} < {minimum}")

    session_pool = _ThreadLocalSessionPool(session, session_factory)
    try:
        mappings = build_sw_industry_mappings(
            nodes_by_level,
            lambda node: fetch_sw_industry_components(
                session_pool.get(),
                node,
                stats=stats,
            ),
        )
    finally:
        session_pool.close()

    for level in _SW_LEVELS:
        mapping, _ = mappings[level]
        if len(mapping) <= _SW_MIN_MAPPING_SIZE:
            raise RuntimeError(f"新浪申万{level}级股票映射不足: {len(mapping)} <= {_SW_MIN_MAPPING_SIZE}")
    coverage = validate_sw_mapping_coverage(mappings)
    logger.info(
        "新浪申万行业映射获取成功: level1_nodes=%s level2_nodes=%s level3_nodes=%s "
        "level1_stocks=%s level2_stocks=%s level3_stocks=%s "
        "cross_level_coverage=%.4f retries=%s elapsed_ms=%.2f",
        len(nodes_by_level[1]),
        len(nodes_by_level[2]),
        len(nodes_by_level[3]),
        len(mappings[1][0]),
        len(mappings[2][0]),
        len(mappings[3][0]),
        coverage,
        stats.retries,
        (time.perf_counter() - started_at) * 1000,
    )
    return mappings
