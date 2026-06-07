import json
from datetime import datetime

import pandas as pd
import requests
from mootdx.quotes import Quotes
from tenacity import retry, stop_after_attempt, wait_exponential

from app.services.base.data_provider import BaseDataProvider
from app.utils.symbol_utils import normalize_code
from app.utils.data_clean import rename_columns


class TdxDataProvider(BaseDataProvider):
    """Purpose: 基于 mootdx 客户端封装通达信本地行情接口，提供股票与指数 K 线、F10 信息。"""
    def __init__(self):
        """初始化 TdxDataProvider，创建多线程 mootdx 客户端。"""
        super().__init__(name="tdx", source_label="通达信")
        self.client = Quotes.factory(market='std', multithread=True, heartbeat=True)

    def fetch_basic_info(self, code: str):
        """通过通达信 F10 接口打印个股各类基本信息（用于调试）。

        Param:
            code: 6 位股票代码
        Return:
            无返回值，结果直接打印到 stdout
        """
        categories = [
            "最新提示", "公司概况", "财务分析",
            "股东研究", "股本结构", "资本运作",
            "业内点评", "行业分析", "公司大事",
        ]
        for cat in categories:
            text = self.client.F10(symbol=code, name=cat)
            print(f"=== {cat} ===")
            print(text if text else "(空)")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信本地接口获取个股 K 线并衍生昨收与涨跌幅。

        Param:
            code: 6 位股票代码
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
        Return:
            包含日期、OHLCV、昨收、涨跌幅的 DataFrame
        """
        offset = (datetime.strptime(end_date, "%Y%m%d") - datetime.strptime(start_date, "%Y%m%d")).days + 1 if start_date and end_date else 10
        sym = normalize_code(code)
        big_df = self.client.bars(symbol=sym.raw, frequency=9, offset=offset)
        big_df.drop(columns=["datetime"], inplace=True)
        big_df.reset_index(inplace=True)
        big_df["date"] = big_df["datetime"].dt.strftime("%Y-%m-%d")
        data = big_df[["date", "open", "close", "high", "low", "volume", "amount"]]
        data["pre_close"] = data["close"].shift(1)
        data["change_pct"] = (data["close"] - data["pre_close"]) /  data["pre_close"] * 100
        return data

    def fetch_index_kline(self, symbol: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """通过通达信本地接口获取指数 K 线并衍生昨收与涨跌幅。

        Param:
            symbol: 指数代码
            start_date: 起始日期，格式 YYYYMMDD
            end_date: 结束日期，格式 YYYYMMDD
        Return:
            包含日期、OHLCV、昨收、涨跌幅的 DataFrame
        """
        offset = (datetime.strptime(end_date, "%Y%m%d") - datetime.strptime(start_date, "%Y%m%d")).days  if start_date and end_date else 10
        sym = normalize_code(symbol)
        big_df = self.client.index(symbol=sym.raw, frequency=9, offset=offset)
        big_df.drop(columns=["datetime"], inplace=True)
        big_df.reset_index(inplace=True)
        big_df["date"] = big_df["datetime"].dt.strftime("%Y-%m-%d")
        data = big_df[["date", "open", "close", "high", "low", "volume", "amount"]]
        data["pre_close"] = data["close"].shift(1)
        data["change_pct"] = (data["close"] - data["pre_close"]) /  data["pre_close"] * 100
        return data


tdx_provider = TdxDataProvider()

if __name__ == "__main__":
    print(tdx_provider.fetch_index_kline("000001", start_date="20260520", end_date="20260522"))
