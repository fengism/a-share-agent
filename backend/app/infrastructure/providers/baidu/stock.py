"""百度个股行情与基础资料能力。"""

import json
import time

import pandas as pd

from app.infrastructure.providers.baidu.transport import BaiduTransport, check_result_code

MAX_PAGES = 60
PAGE_SIZE = 100
NAME_LIST_SLEEP_SECONDS = 0.5


def fetch_stock_kline(
    transport: BaiduTransport,
    code: str,
    start_date: str = "",
    end_date: str = "",
) -> pd.DataFrame:
    params = {
        "all": "1",
        "isIndex": "false",
        "isBk": "false",
        "isBlock": "false",
        "isFutures": "false",
        "isStock": "true",
        "newFormat": "1",
        "group": "quotation_kline_ab",
        "finClientType": "pc",
        "code": code,
        "start_time": start_date,
        "ktype": "1",
    }
    data = transport.get_json("/selfselect/getstockquotation", params)
    keys = data.get("Result", {}).get("newMarketData", {}).get("keys", [])
    rows = data.get("Result", {}).get("newMarketData", {}).get("marketData", "").split(";")
    frame = pd.DataFrame([row.split(",") for row in rows], columns=keys)
    frame["date"] = frame["time"].apply(lambda value: value[:12])
    frame = frame[
        [
            "date",
            "open",
            "close",
            "high",
            "low",
            "volume",
            "amount",
            "range",
            "ratio",
            "turnoverratio",
            "preClose",
        ]
    ]
    frame.columns = [
        "date",
        "open",
        "close",
        "high",
        "low",
        "volume",
        "amount",
        "amplitude",
        "change_pct",
        "turnover_pct",
        "pre_close",
    ]
    return frame


def fetch_stock_names(transport: BaiduTransport) -> list[dict]:
    all_stocks: list[dict] = []
    for page_no in range(MAX_PAGES):
        data = transport.get_json(
            "/selfselect/getmarketrank",
            params={
                "sort_type": "1",
                "sort_key": "14",
                "from_mid": "1",
                "group": "pclist",
                "type": "ab",
                "finClientType": "pc",
                "pn": str(page_no * PAGE_SIZE),
                "rn": str(PAGE_SIZE),
            },
        )
        time.sleep(NAME_LIST_SLEEP_SECONDS)
        if data.get("ResultCode") != "0":
            break
        rank = (
            data.get("Result", {})
            .get("Result", [{}])[0]
            .get("DisplayData", {})
            .get("resultData", {})
            .get("tplData", {})
            .get("result", {})
            .get("rank", [])
        )
        if not rank:
            break
        for item in rank:
            code = str(item.get("code", ""))
            name = str(item.get("name", "")).replace(" ", "")
            if code and name and len(code) == 6 and code.isdigit():
                all_stocks.append({"code": code, "name": name})
        if len(rank) < PAGE_SIZE:
            break
    return all_stocks


def fetch_stock_concept_blocks(transport: BaiduTransport, code: str) -> dict:
    data = transport.get_json(
        "/api/getrelatedblock",
        params={
            "stock": json.dumps({"market": "ab", "type": "stock", "code": code}),
            "finClientType": "pc",
        },
    )
    check_result_code(data)
    result: dict = {"industry": [], "concept": [], "region": [], "concept_tags": []}
    for block in data.get("Result", {}).get(code, []):
        block_name = block.get("name", "")
        for item in block.get("list", []):
            entry = {
                "name": item.get("name", ""),
                "change_pct": item.get("increase", ""),
                "desc": item.get("desc", ""),
            }
            if block_name == "行业":
                result["industry"].append(entry)
            elif block_name == "概念":
                result["concept"].append(entry)
                result["concept_tags"].append(entry["name"])
            elif block_name == "地域":
                result["region"].append(entry)
    return result
