import json
import re
from datetime import datetime

import pandas as pd
import requests

from app.constants.http import SINA_FINANCE_HEADERS
from app.constants.market import SINA_INDEX_PAGE_COUNT_URL, SINA_INDEX_QUOTE_URL, SINA_MARKET_HQ_URL, SINA_STOCK_KLINE_URL
from app.services.base.data_provider import BaseDataProvider
from app.services.base.intraday_utils import loads_sina_jsonp, normalize_intraday_df
from app.utils.symbol_utils import normalize_code
from app.utils.market_utils import replace_comma
from app.utils.data_clean import coerce_numeric_columns, rename_and_keep_columns, rename_columns


class SinaDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="sina", source_label="新浪")


    def fetch_kline_direct(self, code: str, period: str, start_date: str="", end_date: str="") -> pd.DataFrame:
        sym = normalize_code(code)
        symbol = sym.prefixed_lower
        scale_map = {"daily": "240", "weekly": "1200", "monthly": "5200"}
        scale = scale_map.get(period, "240")

        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d")
            delta_days = (datetime.now() - start_dt).days
            if period == "daily":
                datalen = max(delta_days * 5 // 7 + 20, 30)
            elif period == "weekly":
                datalen = max(delta_days // 7 + 5, 10)
            else:
                datalen = max(delta_days // 30 + 3, 5)
            datalen = min(datalen, 2000)
        except ValueError:
            datalen = 500

        params = {
            "symbol": symbol,
            "scale": scale,
            "ma": "no",
            "datalen": str(datalen),
        }
        r = requests.get(SINA_STOCK_KLINE_URL, params=params, headers=SINA_FINANCE_HEADERS, timeout=10)
        text = r.text.strip()
        if text.startswith("=") or text.startswith("/*"):
            import re
            m = re.search(r"\[.*\]", text)
            if not m:
                return pd.DataFrame()
            records = json.loads(m.group(0))
        else:
            records = json.loads(text)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce") / 100
        df = rename_columns(
            df,
            {"day": "日期", "open": "开盘", "high": "最高", "low": "最低", "close": "收盘", "volume": "成交量"},
        )
        df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
        start_dt = pd.to_datetime(start_date, format="%Y%m%d", errors="coerce")
        end_dt = pd.to_datetime(end_date, format="%Y%m%d", errors="coerce")
        df = df[df["日期"].notna()]
        if pd.notna(start_dt):
            df = df[df["日期"] >= start_dt]
        if pd.notna(end_dt):
            df = df[df["日期"] <= end_dt]
        df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
        return df


    def fetch_market_indices_direct(self) -> pd.DataFrame:
        page_count = self._get_index_page_count()
        payload = {
            "page": "1",
            "num": "80",
            "sort": "symbol",
            "asc": "1",
            "node": "hs_s",
            "_s_r_a": "page",
        }
        big_df = pd.DataFrame()
        for page in range(1, page_count + 1):
            payload.update({"page": page})
            response = requests.get(SINA_INDEX_QUOTE_URL, params=payload, timeout=10)
            response.raise_for_status()
            data_json = json.loads(response.text)
            if not data_json:
                break
            big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)
        big_df = big_df.map(replace_comma)
        big_df = coerce_numeric_columns(big_df, ["trade", "pricechange", "changepercent", "buy", "sell", "settlement", "open", "high", "low"])
        big_df.columns = ["代码", "名称", "最新价", "涨跌额", "涨跌幅", "_", "_", "昨收", "今开", "最高", "最低", "成交量", "成交额", "_", "_"]
        big_df = big_df[["代码", "名称", "最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"]]
        return coerce_numeric_columns(big_df, ["最新价", "涨跌额", "涨跌幅", "昨收", "今开", "最高", "最低", "成交量", "成交额"])

    def _get_index_page_count(self) -> int:
        response = requests.get(SINA_INDEX_PAGE_COUNT_URL, timeout=10)
        response.raise_for_status()
        page_count = int(re.findall(re.compile(r"\d+"), response.text)[0]) / 80
        if isinstance(page_count, int):
            return page_count
        return int(page_count) + 1


    def fetch_stock_names(self) -> list[dict]:
        stocks: list[dict] = []
        for item in self._fetch_market_hq_records():
            code = str(item.get("code", ""))
            name = str(item.get("name", "")).replace(" ", "")
            if code and name:
                stocks.append({"code": code, "name": name})
        return stocks

    def fetch_spot_snapshot_direct(self) -> pd.DataFrame:
        records = self._fetch_market_hq_records()
        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df = rename_and_keep_columns(
            df,
            {
                "code": "代码",
                "name": "名称",
                "trade": "最新价",
                "pricechange": "涨跌额",
                "changepercent": "涨跌幅",
                "buy": "买入",
                "sell": "卖出",
                "settlement": "昨收",
                "open": "今开",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "amount": "成交额",
                "per": "市盈率-动态",
                "pb": "市净率",
                "mktcap": "总市值",
                "nmc": "流通市值",
                "turnoverratio": "换手率",
            },
        )
        if "成交量" in df.columns:
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce") * 100
        if "总市值" in df.columns:
            df["总市值"] = pd.to_numeric(df["总市值"], errors="coerce") * 10000
        if "流通市值" in df.columns:
            df["流通市值"] = pd.to_numeric(df["流通市值"], errors="coerce") * 10000
        return df

    def _fetch_market_hq_records(self) -> list[dict]:
        records: list[dict] = []
        page = 1
        page_size = 80
        while True:
            response = requests.get(
                SINA_MARKET_HQ_URL,
                params={
                    "page": page,
                    "num": page_size,
                    "sort": "symbol",
                    "asc": 1,
                    "node": "hs_a",
                    "_s_r_a": "init",
                },
                timeout=15,
            )
            if response.status_code != 200 or not response.text.strip():
                break
            page_records = json.loads(response.text)
            if not page_records:
                break
            records.extend(page_records)
            if len(page_records) < page_size:
                break
            page += 1
            if page > 80:
                break
        return records

    def fetch_stock_intraday_minute_direct(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        sym = normalize_code(code)
        sina_code = sym.prefixed_lower
        params = {
            "symbol": sina_code,
            "callback": f"var t1{sina_code}",
            "version": "7.11.0",
            "dpc": "1",
        }
        response = requests.get("https://cn.finance.sina.com.cn/minline/getMinlineData", params=params, timeout=10)
        response.raise_for_status()
        payload = loads_sina_jsonp(response.text)
        rows = payload.get("result", {}).get("data", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame()
        trade_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
        result_df = pd.DataFrame({
            "时间": df["m"].map(lambda value: f"{trade_date} {str(value).strip()}"),
            "成交价": pd.to_numeric(df.get("p"), errors="coerce"),
            "均价": pd.to_numeric(df.get("avg_p"), errors="coerce"),
            "成交量": pd.to_numeric(df.get("v"), errors="coerce"),
            "成交额": pd.to_numeric(df.get("p"), errors="coerce") * pd.to_numeric(df.get("v"), errors="coerce"),
        })
        return normalize_intraday_df(result_df)


sina_provider = SinaDataProvider()

if __name__ == "__main__":
    df = sina_provider.fetch_kline_direct("600519", "daily", "20260520", "20260526")
    print(df)
