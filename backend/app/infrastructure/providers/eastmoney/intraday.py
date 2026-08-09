import json
import logging

import pandas as pd

from app.constants.market import EASTMONEY_API_TOKEN, EASTMONEY_UT_TRADE
from app.core.dataframes import normalize_intraday_df
from app.infrastructure.http.sse import event_stream

logger = logging.getLogger(__name__)


class IntradayMixin:
    """东方财富 intraday 数据接口。"""

    def fetch_stock_intraday_transactions(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """获取个股分时成交明细（逐笔成交）。

        通过 SSE 推送接口获取当日逐笔成交数据。

        Param:
            code: 6 位股票代码，默认 "000001"
            date: 交易日期，格式 "YYYY-MM-DD"，默认当日
        Return:
            pd.DataFrame: 包含列: 时间, 成交价, 成交量, 成交额, 买卖盘性质
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://61.push2delay.eastmoney.com/api/qt/stock/details/sse"
        params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54,f55",
            "mpi": "2000",
            "ut": EASTMONEY_UT_TRADE,
            "fltt": "2",
            "pos": "-0",
            "secid": f"{market_code}.{code}",
            "wbp2u": "|0|0|0|web",
        }

        big_df = pd.DataFrame()
        for event in event_stream(url, params):
            event_json = json.loads(event.replace("data: ", ""))
            details = event_json.get("data", {}).get("details") or []
            if not details:
                continue
            temp_df = pd.DataFrame([item.split(",") for item in details])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
            break

        if big_df.empty or len(big_df.columns) < 5:
            return pd.DataFrame()
        big_df.columns = ["时间", "成交价", "成交量", "-", "买卖盘性质"]
        big_df["买卖盘性质"] = big_df["买卖盘性质"].map({"2": "买盘", "1": "卖盘", "4": "中性盘"})
        if not big_df.empty:
            trade_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
            big_df["时间"] = big_df["时间"].map(lambda value: f"{trade_date} {str(value).strip()}")
        big_df = big_df[["时间", "成交价", "成交量", "买卖盘性质"]]
        big_df["成交价"] = pd.to_numeric(big_df["成交价"], errors="coerce")
        big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce") * 100
        big_df["成交额"] = pd.to_numeric(big_df["成交价"], errors="coerce") * pd.to_numeric(big_df["成交量"], errors="coerce")
        return normalize_intraday_df(big_df)

    def fetch_stock_intraday_minute(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """获取个股分时分钟数据（1 分钟级别）。

        通过 SSE 推送接口获取分时走势的分钟级数据。

        Param:
            code: 6 位股票代码，默认 "000001"
            date: 交易日期，格式 "YYYY-MM-DD"，默认当日
        Return:
            pd.DataFrame: 包含列: 时间, 成交价, 手数, 成交额
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://69.push2.eastmoney.com/api/qt/stock/trends2/sse"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f17",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "mpi": "1000",
            "ut": EASTMONEY_API_TOKEN,
            "ndays": "1",
            "iscr": "0",
            "iscca": "0",
            "secid": f"{market_code}.{code}",
            "wbp2u": "1849325530509956|0|1|0|web",
        }

        big_df = pd.DataFrame()
        for event in event_stream(url, params):
            event_json = json.loads(event.replace("data: ", ""))
            temp_df = pd.DataFrame([item.split(",") for item in event_json["data"]["trends"]])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
            break

        if big_df.empty or len(big_df.columns) < 7:
            return pd.DataFrame()
        result_df = pd.DataFrame({
            "时间": big_df.iloc[:, 0],
            "成交价": big_df.iloc[:, 4],
            "手数": big_df.iloc[:, 5],
            "成交额": big_df.iloc[:, 6],
        })
        result_df["成交价"] = pd.to_numeric(result_df["成交价"], errors="coerce")
        result_df["手数"] = pd.to_numeric(result_df["手数"], errors="coerce") * 100
        return normalize_intraday_df(result_df)
