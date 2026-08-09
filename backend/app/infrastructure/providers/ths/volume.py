"""同花顺市场成交额能力。"""

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor

from app.contracts.market import MarketVolume
from app.infrastructure.providers.ths.transport import ThsTransport

logger = logging.getLogger(__name__)


def fetch_market_volume_chart(transport: ThsTransport, chart_key: str) -> dict:
    payload = transport.request_json(
        "GET",
        "https://dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data",
        params={"chart_key": chart_key},
        headers={
            "Accept": "*/*",
            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
        },
        timeout=10,
    )
    if payload.get("status_code") != 0:
        return {}
    charts = payload.get("data", {}).get("charts", {})
    amount_data = {}
    if chart_key == "turnover_day":
        amount_data["date"] = charts.get("mtime", "").split(" ")[0]
    for header in charts.get("header", []):
        key = header.get("key")
        if key == "average_turnover":
            amount_data["amount_average_60_day"] = header.get("val", 0)
        elif key == "turnover":
            amount_data["amount"] = header.get("val", 0)
        elif key == "turnover_pre":
            amount_data["amount_before_one_day"] = header.get("val", 0)
    return amount_data


def fetch_market_volume(
    day_loader: Callable[[], dict],
    minute_loader: Callable[[], dict],
) -> MarketVolume:
    with ThreadPoolExecutor(max_workers=2) as executor:
        day_future = executor.submit(day_loader)
        minute_future = executor.submit(minute_loader)
        try:
            day_data = day_future.result()
        except Exception as exc:
            logger.warning("同花顺日级成交额获取失败: %s", exc)
            day_data = {}
        try:
            minute_data = minute_future.result()
        except Exception as exc:
            logger.warning("同花顺分钟级成交额获取失败: %s", exc)
            minute_data = {}
    minute_data.update(day_data)
    return MarketVolume(**minute_data)
