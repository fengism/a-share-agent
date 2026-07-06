import json
import logging
import re
import time

import pandas as pd
import requests


logger = logging.getLogger(__name__)
from app.utils.data_clean import safe_float
from app.constants.market import EASTMONEY_UT_TOKEN, EASTMONEY_UT_TOKEN_ALT



class FundFlowMixin:
    """东方财富 fund_flow 数据接口。"""

    def _parse_fund_flow_klines(klines: list[str]) -> list[dict]:
        """解析资金流向 kline 字符串列表为结构化字典列表。

        Param:
            klines: 逗号分隔的 kline 字符串列表
        Return:
            资金流向字典列表，包含 date/main_net/small_net/mid_net/large_net/super_net
        """
        rows = []
        for line in klines:
            parts = line.split(",")
            if len(parts) >= 7:
                rows.append({
                    "date": parts[0],
                    "main_net": float(parts[1]) if parts[1] != "-" else 0,
                    "small_net": float(parts[2]) if parts[2] != "-" else 0,
                    "mid_net": float(parts[3]) if parts[3] != "-" else 0,
                    "large_net": float(parts[4]) if parts[4] != "-" else 0,
                    "super_net": float(parts[5]) if parts[5] != "-" else 0,
                })
        return rows

    def _parse_fund_flow_items(items: list[dict]) -> list[dict]:
        """解析 clist 接口返回的资金流向 item 列表。

        Param:
            items: 东财 clist 接口返回的 item 字典列表
        Return:
            资金流向字典列表，包含 industry_code/industry_name/change_pct 及各级净流入
        """
        rows = []
        for item in items:
            rows.append({
                "industry_code": item.get("f12", ""),
                "industry_name": item.get("f14", ""),
                "change_pct": safe_float(item.get("f3", "")),
                "main_net": safe_float(item.get("f62", "")),
                "small_net": safe_float(item.get("f84", "")),
                "mid_net": safe_float(item.get("f78", "")),
                "large_net": safe_float(item.get("f72", "")),
                "super_net": safe_float(item.get("f66", "")),
            })
        return rows

    def fetch_stock_fund_flow(self, code: str) -> list[dict]:
        """获取个股，最近 120 个交易日）。

        Param:
            code: 6 位股票代码
        Return:
            list[dict]: 资金流向列表，每个字典包含:
                - date (str): 日期
                - main_net (float): 主力净流入（元）
                - small_net (float): 小单净流入（元）
                - mid_net (float): 中单净流入（元）
                - large_net (float): 大单净流入（元）
                - super_net (float): 超大单净流入（元）
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"
        params = {
            "secid": f"{market_code}.{code}",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "lmt": "120",
        }
        try:
            r = self.em_get_response(url, params=params, headers=self.eastmoney_headers, timeout=15)
            d = r.json()
        except Exception as e:
            logger.warning("东方财富个股资金流请求失败: code=%s, error=%s", code, e)
            return []
        klines = d.get("data", {}).get("klines", [])
        return self._parse_fund_flow_klines(klines)

    def fetch_market_fund_flow(self) -> list[dict]:
        """获取市场资金流入日级，最近 120 个交易日）。

        Param:
            code: 6 位股票代码
        Return:
            list[dict]: 资金流向列表，每个字典包含:
                - date (str): 日期
                - main_net (float): 主力净流入（元）
                - small_net (float): 小单净流入（元）
                - mid_net (float): 中单净流入（元）
                - large_net (float): 大单净流入（元）
                - super_net (float): 超大单净流入（元）
        """
        url = "https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get"    
        params = {
            "lmt": "0",
            "kit": "101",
            "fields1": "f1,f2,f3,f7",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f62,f63,f64,f65",
            "secid": "1.000001",
            "secid2": "0.399001",
            "ut": EASTMONEY_UT_TOKEN,
            "_": int(time.time() * 1000),
        }
        try:
            r = self.em_get_response(url, params=params, headers=self.eastmoney_headers, timeout=15)
            d = r.json()
        except Exception as e:
            logger.warning("东方财富市场资金流请求失败: %s", e)
            return []
        klines = d.get("data", {}).get("klines", [])
        return self._parse_fund_flow_klines(klines)

    def fetch_industry_fund_flow(self) -> list[dict]:
        """获取市场行业资金流入情况
        https://push2.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz=50&pn=1&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A90+s%3A4&fields=f12%2Cf14%2Cf2%2Cf3%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13
        Param:
            code: 6 位股票代码
        Return:
            list[dict]: 资金流向列表，每个字典包含:
                - industry_code (str): 行业代码
                - industry_name (str): 行业名称
                - change_pct (float): 涨跌幅
                - main_net (float): 主力净流入（元）
                - small_net (float): 小单净流入（元）
                - mid_net (float): 中单净流入（元）
                - large_net (float): 大单净流入（元）
                - super_net (float): 超大单净流入（元）
        """
        params = {
            "fid": "f62",
            "po": "1",
            "pz": "50",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": EASTMONEY_UT_TOKEN_ALT,
            "fs": "m:90+s:4",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
            "_": int(time.time() * 1000),
        }
        try:
            items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers, page_size=100)
        except Exception as e:
            logger.warning("东方财富行业资金流请求失败: %s", e)
            return []
        return self._parse_fund_flow_items(items)

    def fetch_concept_fund_flow(self) -> list[dict]:
        """获取市场行业资金流入情况
        https://push2.eastmoney.com/api/qt/clist/get?fid=f62&po=1&pz=50&pn=1&np=1&fltt=2&invt=2&ut=8dec03ba335b81bf4ebdf7b29ec27d15&fs=m%3A90+t%3A3&fields=f12%2Cf14%2Cf2%2Cf3%2Cf62%2Cf184%2Cf66%2Cf69%2Cf72%2Cf75%2Cf78%2Cf81%2Cf84%2Cf87%2Cf204%2Cf205%2Cf124%2Cf1%2Cf13
        Param:
            code: 6 位股票代码
        Return:
            list[dict]: 资金流向列表，每个字典包含:
                - industry_code (str): 行业代码
                - industry_name (str): 行业名称
                - change_pct (float): 涨跌幅
                - main_net (float): 主力净流入（元）
                - small_net (float): 小单净流入（元）
                - mid_net (float): 中单净流入（元）
                - large_net (float): 大单净流入（元）
                - super_net (float): 超大单净流入（元）
        """ 
        params = {
            "fid": "f62",
            "po": "1",
            "pz": "50",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": EASTMONEY_UT_TOKEN_ALT,
            "fs": "m:90+t:3",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
        }
        try:
            items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers, page_size=100)
        except Exception as e:
            logger.warning("东方财富概念资金流请求失败: %s", e)
            return []
        return self._parse_fund_flow_items(items)
