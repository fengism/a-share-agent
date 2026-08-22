"""同花顺热点排行与强势股归因能力。"""

from datetime import date as current_date

import pandas as pd

from app.core.market import safe_float
from app.infrastructure.providers.ths.transport import ThsTransport


def _tag_text(value) -> str:
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, (list, tuple, set)):
        return ";".join(str(item) for item in value if item)
    return str(value or "")


def normalize_items(items: list[dict], *, plate: bool = False) -> list[dict]:
    result = []
    for item in items or []:
        tag_info = item.get("tag") or {}
        if plate:
            tags = {
                "hot_tag": _tag_text(item.get("hot_tag")),
                "tag": _tag_text(item.get("tag")),
            }
        else:
            tags = {
                "concept_tag": ";".join(tag_info.get("concept_tag") or []),
                "pop_tag": str(tag_info.get("popularity_tag") or "").replace("\n", ""),
            }
        result.append(
            {
                "rank": item.get("order"),
                "code": item.get("code", ""),
                "name": item.get("name", ""),
                "change_pct": item.get("rise_and_fall"),
                "hot_value": safe_float(item.get("rate")),
                **tags,
            }
        )
    return result


def fetch_hot_stock_rank(transport: ThsTransport) -> list[dict]:
    payload = transport.request_json(
        "GET",
        "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
        params={"stock_type": "a", "type": "hour", "list_type": "normal"},
        headers=transport.headers(),
        timeout=10,
    )
    return normalize_items(payload.get("data", {}).get("stock_list", []))


def fetch_hot_plate_rank(transport: ThsTransport, plate_type: str) -> list[dict]:
    payload = transport.request_json(
        "GET",
        "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate",
        params={"type": plate_type},
        headers=transport.headers(),
        timeout=10,
    )
    return normalize_items(payload.get("data", {}).get("plate_list", []), plate=True)


def fetch_hot_stock_reasons(
    transport: ThsTransport,
    date: str | None = None,
) -> pd.DataFrame:
    resolved_date = date or current_date.today().strftime("%Y-%m-%d")
    url = (
        "http://zx.10jqka.com.cn/event/api/getharden/"
        f"date/{resolved_date}/orderby/date/orderway/desc/charset/GBK/"
    )
    data = transport.request_json(
        "GET",
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            )
        },
        timeout=10,
    )
    if data.get("errocode", 0) != 0:
        raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")
    frame = pd.DataFrame(data.get("data") or [])
    if frame.empty:
        return frame
    return frame.rename(
        columns={
            "name": "名称",
            "code": "代码",
            "reason": "题材归因",
            "close": "收盘价",
            "zhangdie": "涨跌额",
            "zhangfu": "涨幅%",
            "huanshou": "换手率%",
            "chengjiaoe": "成交额",
            "chengjiaoliang": "成交量",
            "ddejingliang": "大单净量",
        }
    )
