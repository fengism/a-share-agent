"""百度个股与板块资金流能力。"""

from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code


def fetch_stock_fund_flow(transport: BaiduTransport, code: str) -> list[dict]:
    data = transport.get_json(
        "/vapi/v1/fundflow",
        params={
            "finance_type": "stock",
            "fund_flow_type": "",
            "market": "ab",
            "code": code,
            "type": "stock",
            "finClientType": "pc",
        },
    )
    check_result_code(data)
    return data.get("Result", {}).get("content", {}).get("fundFlowSpread", {}).get("result", [])


def fetch_block_fund_flow(transport: BaiduTransport, block_type: str) -> list[dict]:
    data = transport.get_json(
        "/sapi/v1/ranks",
        params={
            "bizType": "fundflow_rank",
            "style": "tablelist",
            "fundflowRankTarget": "block",
            "market": "ab",
            "sortKey": "",
            "sortType": "",
            "blockType": block_type,
            "pn": "0",
            "rn": "200",
            "finClientType": "pc",
        },
        headers=transport.cookie_headers(),
    )
    check_result_code(data)
    return [
        {
            "code": item.get("code", ""),
            "name": item.get("name", ""),
            "mainNetIn": item.get("mainNetIn", 0),
            "mainTotalIn": item.get("mainTotalIn", 0),
            "totalAmount": item.get("totalAmount", 0),
        }
        for item in data.get("Result", {}).get("list", {}).get("body", [])
    ]
