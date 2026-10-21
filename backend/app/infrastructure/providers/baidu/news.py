"""百度 7x24 快讯能力。"""

from collections.abc import Callable
from typing import Any

from app.core.market import contains_stock_reference
from app.domain.news import NewsSearchItem
from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


def _join_express_content(content: dict) -> str:
    items = content.get("items", []) if isinstance(content, dict) else []
    return "".join(str(item.get("data", "")) for item in items)


def fetch_market_kuaixun(
    transport: BaiduTransport,
    timestamp_parser: Callable[[Any], Any],
    code: str = "",
    code_name: str = "",
) -> list[NewsSearchItem]:
    data = transport.get_json(
        "/selfselect/expressnews",
        params={
            "rn": "20",
            "pn": "0",
            "tag": "",
            "filterByUserStocks": "0",
            "finClientType": "pc",
        },
    )
    check_result_code(data)
    results: list[NewsSearchItem] = []
    for item in data.get("Result", {}).get("content", {}).get("list", []):
        title = str(item.get("title") or "").strip()
        content = _join_express_content(item.get("content", {}))
        if (code_name or code) and not contains_stock_reference(
            f"{title}\n{content}",
            code,
            code_name,
        ):
            continue
        parsed_publish_time = timestamp_parser(item.get("publish_time"))
        results.append(
            NewsSearchItem(
                title=title,
                content=content[:500],
                source="百度 7x24 快讯",
                publish_time=(
                    parsed_publish_time.isoformat(sep=" ")
                    if hasattr(parsed_publish_time, "isoformat")
                    else str(parsed_publish_time or "")
                ),
                url=item.get("third_url", ""),
                author=item.get("author", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            )
        )
    return results
