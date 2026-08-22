"""新浪行情接口的交易日期查询。"""

import re
from collections.abc import Callable
from typing import Any

from app.core.market import normalize_code
from app.infrastructure.http.client import get_provider_session as get_session


def get_last_trade_date(
    code: str,
    *,
    session_provider: Callable[[], Any] = get_session,
) -> str:
    symbol = normalize_code(code).prefixed_lower
    response = session_provider().get(
        f"https://hq.sinajs.cn/list={symbol}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/114.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
            "Host": "hq.sinajs.cn",
            "Referer": "https://finance.sina.com.cn",
        },
        timeout=10,
    )
    if response.status_code != 200:
        return ""
    match = re.search(r"\d{4}-\d{2}-\d{2}", response.text)
    return match.group(0) if match else ""
