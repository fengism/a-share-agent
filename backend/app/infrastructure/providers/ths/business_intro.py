"""同花顺股票主营介绍抓取能力。"""

import pandas as pd
from bs4 import BeautifulSoup

from app.infrastructure.providers.ths.transport import ThsTransport


def _compact_text(value: str) -> str:
    """移除页面排版空白，保留标点和正文内容。"""
    return "".join(value.split())


def fetch_stock_business_intro(
    transport: ThsTransport,
    code: str,
) -> pd.DataFrame:
    """从同花顺主营介绍页提取单只股票的动态字段。"""
    response = transport.request(
        "GET",
        f"https://basic.10jqka.com.cn/new/{code}/operate.html",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://basic.10jqka.com.cn/",
        },
        timeout=15,
    )
    response.encoding = "gb2312"
    soup = BeautifulSoup(response.text, "html.parser")
    intro_list = soup.select_one("ul.main_intro_list")
    if intro_list is None:
        return pd.DataFrame()

    values: dict[str, str] = {}
    for item in intro_list.select("li"):
        text = item.get_text().strip()
        if "：" not in text:
            continue
        column, value = text.split("：", maxsplit=1)
        column = column.strip()
        value = _compact_text(value)
        if not column or not value or column in values:
            continue
        values[column] = value

    if not values:
        return pd.DataFrame()
    return pd.DataFrame([{"股票代码": code, **values}])
