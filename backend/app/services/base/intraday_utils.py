import json

import pandas as pd
import requests


def normalize_intraday_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    rename_map = {
        "时间": "time",
        "日期时间": "time",
        "date": "time",
        "时间戳": "time",
        "最新价": "price",
        "成交价": "price",
        "收盘": "price",
        "close": "price",
        "均价": "avg_price",
        "成交均价": "avg_price",
        "均均价": "avg_price",
        "成交量": "volume",
        "手数": "volume",
        "volume": "volume",
        "成交额": "amount",
        "amount": "amount",
        "涨跌幅": "change_pct",
    }
    df = df.rename(columns={key: value for key, value in rename_map.items() if key in df.columns})

    if "time" not in df.columns or "price" not in df.columns:
        return pd.DataFrame()
    return df


def event_stream(url: str, params: dict):
    response = requests.get(url, params=params, stream=True)
    event_data = ""

    for line in response.iter_lines():
        if line:
            event_data += line.decode() + "\n"
        elif event_data:
            yield event_data
            event_data = ""


def loads_sina_jsonp(text: str) -> dict:
    payload = text.strip()
    if payload.startswith("var "):
        start = payload.find("(")
        end = payload.rfind(")")
        if start == -1 or end <= start:
            raise ValueError("新浪分时 JSONP 格式无效")
        payload = payload[start + 1:end]
    return json.loads(payload)
