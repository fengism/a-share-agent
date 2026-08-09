"""百度行业与概念排名能力。"""

from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


def fetch_trade_dates(transport: BaiduTransport) -> list[dict]:
    data = transport.get_json(
        "/sapi/v1/marketquote",
        params={"bizType": "marketStatus", "finClientType": "pc"},
        headers=transport.cookie_headers(),
    )
    check_result_code(data)
    return data.get("Result", {}).get("index", {}).get("ab", {}).get("marketDate", [])


def fetch_block_rankings(
    transport: BaiduTransport,
    block_type: str,
    top_n: int,
) -> dict:
    response = transport.get_json(
        "https://finance.pae.baidu.com/vapi/v2/blocks",
        params={
            "style": "tablelist",
            "pn": "0",
            "rn": "200",
            "market": "ab",
            "typeCode": block_type,
            "finClientType": "pc",
        },
        headers=transport.cookie_headers(),
    )
    check_result_code(response)
    result = []
    for index, item in enumerate(
        response.get("Result", {}).get("list", {}).get("body", [])
    ):
        leaders = item.get("riseFirst") or []
        if not leaders:
            continue
        leader = leaders[0]
        change_pct = str(item.get("pxChangeRate", 0) or 0).replace("%", "")
        leader_change = str(leader.get("ratio", {}).get("value", 0) or 0).replace("%", "")
        result.append(
            {
                "rank": index + 1,
                "name": item.get("name", ""),
                "code": item.get("code", ""),
                "change_pct": float(change_pct),
                "up_count": int(item.get("riseCount", 0) or 0),
                "down_count": (
                    int(item.get("memberCount", 0) or 0)
                    - int(item.get("riseCount", 0) or 0)
                    - int(item.get("flatCount", 0) or 0)
                ),
                "leader": leader.get("name", ""),
                "leader_change": float(leader_change),
            }
        )
    return {"top": result[:top_n], "bottom": result[-top_n:], "total": len(result)}
