import logging

import pandas as pd

from app.constants.market import (
    EASTMONEY_API_TOKEN,
    EASTMONEY_KLINE_FIELDS1,
    EASTMONEY_KLINE_FIELDS2,
    EASTMONEY_STOCK_KLINE_URL,
    EASTMONEY_UT_HISTORY,
    INDEX_FALLBACKS,
)
from app.infrastructure.providers.eastmoney.symbols import build_stock_secid

logger = logging.getLogger(__name__)


class KlineMixin:
    """东方财富 kline 数据接口。"""

    def fetch_kline(self, code: str, period: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        """获取个股历史 K 线数据

        Param:
            code: 6 位股票代码
            period: K 线周期，可选 "daily"（日线）、"weekly"（周线）、"monthly"（月线）
            start_date: 起始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            adjust: 复权方式，"qfq"（前复权，默认）、"hfq"（后复权）、""（不复权）
        Return:
            pd.DataFrame: 包含列: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        """
        k_type_map = {"daily": "101", "weekly": "102", "monthly": "103"}
        klt = k_type_map.get(period, "101")
        fqt_map = {"qfq": 1, "hfq": 2, "": 0}
        fqt = fqt_map.get(adjust, 1)

        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": EASTMONEY_UT_HISTORY,
            "klt": klt,
            "fqt": fqt,
            "secid": build_stock_secid(code),
            "beg": start_date,
            "end": end_date,
            "_": "1623766962675",
        }
        r = self.em_get_response(EASTMONEY_STOCK_KLINE_URL, params=params, headers=self.eastmoney_headers, timeout=10)
        data_json = r.json()

        if not data_json.get("data") or not data_json["data"].get("klines"):
            return pd.DataFrame()

        lines = data_json["data"]["klines"]
        data = [item.split(",")[:11] for item in lines]
        df = pd.DataFrame(
            data=data,
            columns=["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"],
        )
        # 东方财富 K 线成交量单位为手；统一为股。
        df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce") * 100
        if "振幅" in df.columns:
            df["振幅"] = pd.to_numeric(df["振幅"], errors="coerce")
        return df

    def fetch_index_kline(self, symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取大盘指数历史 K 线数据。

        Param:
            symbol: 指数代码（如 "000001" 上证指数、"399001" 深证成指）
            period: K 线周期，可选 "daily"、"weekly"、"monthly"
            start_date: 起始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
        Return:
            pd.DataFrame: 包含列: 日期, 开盘, 收盘, 最高, 最低, 成交量(总手), 成交额(元), 振幅, 涨跌幅, 涨跌额, 换手率
        """
        secid_map = {code: secid for code, _name, secid in INDEX_FALLBACKS}
        secid = secid_map.get(symbol)
        if secid is None:
            raise ValueError(f"暂不支持该指数直连回退: {symbol}")

        klt = {"daily": "101", "weekly": "102", "monthly": "103"}.get(period, "101")
        try:
            response = self.em_get_response(
                EASTMONEY_STOCK_KLINE_URL,
                params={
                    "secid": secid,
                    "ut": EASTMONEY_API_TOKEN,
                    "fields1": EASTMONEY_KLINE_FIELDS1,
                    "fields2": EASTMONEY_KLINE_FIELDS2,
                    "klt": klt,
                    "fqt": "1",
                    "beg": start_date or "0",
                    "end": end_date or "20500101",
                    "smplmt": "100000",
                    "lmt": "1000000",
                    "_": "1722235849235",
                },
                headers={},
                timeout=10,
            )
            data = (response.json() or {}).get("data") or {}
        except Exception as exc:
            logger.warning(f"大盘指数K线直连失败: symbol={symbol}, error={exc}")
            raise

        if str(data.get("code", "")) and str(data.get("code", "")) != symbol:
            return pd.DataFrame()

        lines = data.get("klines") or []
        if not lines:
            return pd.DataFrame()

        rows = [item.split(",") for item in lines]

        df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "change_pct", "change", "turnover_pct"])
        df["pre_close"] = df["close"].shift(1) 
        return df
