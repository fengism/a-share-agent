import json
import logging
import re
import time

import pandas as pd
import requests


logger = logging.getLogger(__name__)

from app.constants.market import EASTMONEY_INDEX_QUOTE_FIELDS, EASTMONEY_FLATTEN_FLAG, EASTMONEY_UT_TRADE, EASTMONEY_API_TOKEN, EASTMONEY_UT_HISTORY, EASTMONEY_INVESTOR_TYPE
from app.utils.data_clean import rename_and_keep_columns, safe_float


class MarketMixin:
    """东方财富 market 数据接口。"""

    def fetch_market_indices(self) -> pd.DataFrame:
        """获取主要市场指数实时行情。

        获取上证指数、深证成指、创业板指等主要指数的实时行情数据。

        Return:
            pd.DataFrame: 包含列: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额, 最高, 最低, 今开, 昨收, 振幅, 量比
        """
        response = self.em_get_response(
            "https://push2delay.eastmoney.com/api/qt/clist/get",
            params={
                "np": "1",
                "invt": EASTMONEY_INVESTOR_TYPE,
                "fltt": EASTMONEY_FLATTEN_FLAG,
                "cb": "jQuery371008276743255053931_1778650747671",
                "fs": "b:MK0010",
                "fields": EASTMONEY_INDEX_QUOTE_FIELDS,
                "fid": "",
                "pn": "1",
                "pz": "50",
                "po": "1",
                "ut": EASTMONEY_API_TOKEN,
                "dect": "1",
                "wbp2u": "|0|0|0|web",
                "_": str(int(time.time() * 1000)),
            },
            headers=self.eastmoney_headers,
            timeout=10,
        )
        response.raise_for_status()
        text = response.text
        start = text.find("(") + 1
        end = text.find(")")
        data_info = json.loads(text[start:end])
        data = data_info.get("data") or {}
        tmp_df = pd.DataFrame(data.get("diff") or {})
        tmp_df.rename(
            columns={
                "f1": "序号",
                "f2": "最新价",
                "f3": "涨跌幅",
                "f4": "涨跌额",
                "f5": "成交量",
                "f6": "成交额",
                "f7": "振幅",
                "f10": "量比",
                "f12": "代码",
                "f13": "-",
                "f14": "名称",
                "f15": "最高",
                "f16": "最低",
                "f17": "今开",
                "f18": "昨收",
                "f152": "-",
            },
            inplace=True,
        )
        index_df = tmp_df[
            ["代码", "名称", "最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "最高", "最低", "今开", "昨收", "振幅", "量比"]
        ]
        for column in ["最新价", "涨跌幅", "涨跌额", "成交量", "成交额", "最高", "最低", "今开", "昨收", "振幅", "量比"]:
            index_df[column] = pd.to_numeric(index_df[column], errors="coerce")
        index_df["最新价"] = index_df["最新价"] / 100.0
        index_df["最高"] = index_df["最高"] / 100.0
        index_df["最低"] = index_df["最低"] / 100.0
        index_df["今开"] = index_df["今开"] / 100.0
        index_df["昨收"] = index_df["昨收"] / 100.0
        index_df["振幅"] = index_df["振幅"] / 100.0
        index_df["量比"] = index_df["量比"] / 100.0
        index_df["涨跌幅"] = index_df["涨跌幅"] / 100.0
        return index_df

    def fetch_spot_snapshot(self) -> pd.DataFrame:
        """获取全市场个股实时行情快照。

        获取所有 A 股的最新价、涨跌幅、成交量、市值等核心指标。

        Return:
            pd.DataFrame: 包含列: 代码, 名称, 最新价, 涨跌幅, 涨跌额, 成交量, 成交额,
                振幅, 换手率, 市盈率-动态, 量比, 最高, 最低, 今开, 昨收, 总市值, 流通市值, 市净率
        """
        diff = self._fetch_clist_diff(
            {
                "po": "1",
                "np": "1",
                "ut": EASTMONEY_UT_TRADE,
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f14,f15,f16,f17,f18,f20,f21,f23",
            },
            page_size=100,
        )
        if not diff:
            return pd.DataFrame()

        df = pd.DataFrame(diff)
        rename_map = {
            "f12": "代码", "f14": "名称", "f2": "最新价", "f3": "涨跌幅",
            "f4": "涨跌额", "f5": "成交量", "f6": "成交额", "f7": "振幅",
            "f8": "换手率", "f9": "市盈率-动态", "f10": "量比",
            "f15": "最高", "f16": "最低", "f17": "今开", "f18": "昨收",
            "f20": "总市值", "f21": "流通市值", "f23": "市净率",
        }
        df = rename_and_keep_columns(df, rename_map)
        if "成交量" in df.columns:
            df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce") * 100
        return df

    def fetch_market_pct_distribution(self, date: str | None = None) -> dict:
        """获取市场涨跌幅分布统计。

        Return:
            dict: 涨跌幅分布数据，包含各涨跌幅区间的股票数量
        """
        response = self.em_get_response(
            "https://push2ex.eastmoney.com/getTopicZDFenBu",
            params={
                "cb": "callbackdata6759488",
                "ut": EASTMONEY_UT_HISTORY,
                "dpt": "wz.ztzt",
                "_": str(int(time.time() * 1000)),
            },
            headers=self.eastmoney_headers,
            timeout=15,
        )
        response.raise_for_status()
        return self._parse_json_from_text(response.text, "分布统计接口返回格式异常").get("data") or {}
