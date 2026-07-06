import json
import logging
import re
import time

import pandas as pd
import requests


logger = logging.getLogger(__name__)
from app.constants.market import EASTMONEY_UT_HISTORY



class LimitPoolMixin:
    """东方财富 limit_pool 数据接口。"""

    def fetch_market_limit_up_pool(self, date: str | None = None) -> tuple[list[dict], int]:
        """获取涨停池数据。

        Param:
            date: 交易日期，格式 "YYYYMMDD" 或 "YYYY-MM-DD"，默认当日
        Return:
            tuple[list[dict], int]:
                - list: 涨停股票列表，每个字典包含涨停相关字段
                - int: 涨停股票总数
        """
        if date is None:
            date = time.strftime("%Y%m%d", time.localtime())
        if "-" in date:
            date = date.replace("-", "")

        response = self.em_get_response(
            "https://push2ex.eastmoney.com/getTopicZTPool",
            params={
                "cb": "callbackdata2435777",
                "ut": EASTMONEY_UT_HISTORY,
                "dpt": "wz.ztzt",
                "Pageindex": "0",
                "pagesize": "200",
                "sort": "fbt:asc",
                "date": date,
                "_": str(int(time.time() * 1000)),
            },
            headers=self.eastmoney_headers,
            timeout=15,
        )
        response.raise_for_status()
        data = self._parse_json_from_text(response.text, "涨停池接口返回格式异常")
        payload = data.get("data") or {}
        return payload.get("pool") or [], int(payload.get("tc") or 0)

    def fetch_market_limit_down_pool(self, date: str | None = None) -> tuple[list[dict], int]:
        """获取跌停池数据。

        Param:
            date: 交易日期，格式 "YYYYMMDD" 或 "YYYY-MM-DD"，默认当日
        Return:
            tuple[list[dict], int]:
                - list: 跌停股票列表，每个字典包含跌停相关字段
                - int: 跌停股票总数
        """
        if date is None:
            date = time.strftime("%Y%m%d", time.localtime())
        if "-" in date:
            date = date.replace("-", "")

        response = self.em_get_response(
            "https://push2ex.eastmoney.com/getTopicDTPool",
            params={
                "cb": "callbackdata2705894",
                "ut": EASTMONEY_UT_HISTORY,
                "dpt": "wz.ztzt",
                "Pageindex": "0",
                "pagesize": "200",
                "sort": "fund:asc",
                "date": date,
                "_": str(int(time.time() * 1000)),
            },
            headers=self.eastmoney_headers,
            timeout=15,
        )
        response.raise_for_status()
        data = self._parse_json_from_text(response.text, "跌停池接口返回格式异常")
        payload = data.get("data") or {}
        return payload.get("pool") or [], int(payload.get("tc") or 0)
