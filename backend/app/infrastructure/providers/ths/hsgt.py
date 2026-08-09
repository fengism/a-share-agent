"""同花顺沪深股通实时流向能力。"""

import json

import pandas as pd

from app.infrastructure.providers.ths.transport import ThsTransport


def get_trade_date(transport: ThsTransport) -> str:
    payload = json.dumps(
        {
            "code_list": [{"codes": ["1A0001"], "market": "16"}],
            "trade_date": 0,
            "gpid": 2,
        }
    )
    data = transport.request_json(
        "GET",
        "https://quota-h.10jqka.com.cn/fuyao/common_hq_aggr/quote/v1/trade_time",
        data=payload,
        headers={
            "Accept": "*/*",
            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
            "Content-Type": "application/json",
        },
    )
    time_info = data.get("data", {}).get("time_info") or []
    return (time_info[0] if time_info else {}).get("trade_date", "")


def fetch_hsgt_realtime(
    transport: ThsTransport,
    trade_date: str,
) -> pd.DataFrame:
    resolved_date = trade_date or pd.Timestamp.now().strftime("%Y-%m-%d")
    data = transport.request_json(
        "GET",
        "https://data.hexin.cn/market/hsgtApi/method/dayChart/",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            ),
            "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/",
        },
        timeout=10,
    )
    times = list(data.get("time") or [])
    hgt_values = list(data.get("hgt") or [])
    sgt_values = list(data.get("sgt") or [])
    count = len(times)
    return pd.DataFrame(
        {
            "time": [f"{resolved_date} {value}" for value in times],
            "hgt_yi": hgt_values[:count] + [None] * (count - len(hgt_values)),
            "sgt_yi": sgt_values[:count] + [None] * (count - len(sgt_values)),
        }
    )
