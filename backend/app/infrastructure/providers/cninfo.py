"""Cninfo full-market stock-index provider."""

from collections.abc import Mapping
from typing import Any

from app.core.market import classify_exchange, normalize_stock_name
from app.infrastructure.http.client import provider_get

CNINFO_STOCK_INDEX_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.cninfo.com.cn/",
    "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
}
_REQUEST_TIMEOUT_SECONDS = 5


def _normalize_stock_rows(rows: list[Any]) -> list[dict[str, str]]:
    records_by_code: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, Mapping) or str(row.get("category") or "").strip() != "A股":
            continue
        code = str(row.get("code") or "").strip()
        name = normalize_stock_name(str(row.get("zwjc") or ""))
        if len(code) != 6 or not code.isdigit() or not name:
            continue
        try:
            classify_exchange(code)
        except ValueError:
            continue
        records_by_code.setdefault(code, {"code": code, "name": name})
    return [records_by_code[code] for code in sorted(records_by_code)]


class CninfoDataProvider:
    """Fetch Cninfo's full-market A-share code and name index."""

    name = "cninfo"

    def fetch_stock_names(self) -> list[dict[str, str]]:
        response = provider_get(
            CNINFO_STOCK_INDEX_URL,
            headers=CNINFO_HEADERS,
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        try:
            payload = response.json()
        except ValueError as error:
            raise RuntimeError("巨潮股票索引返回了无效 JSON") from error
        rows = payload.get("stockList") if isinstance(payload, Mapping) else None
        if not isinstance(rows, list):
            raise RuntimeError("巨潮股票索引返回格式无效")
        return _normalize_stock_rows(rows)


cninfo_provider = CninfoDataProvider()
