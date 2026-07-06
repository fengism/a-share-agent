import json
import logging
import re

import pandas as pd
import requests


logger = logging.getLogger(__name__)
from app.utils.data_clean import safe_float



class DragonTigerMixin:
    """东方财富 dragon_tiger 数据接口。"""

    def fetch_dragon_tiger_daily_list(self, report_date: str) -> list[dict]:
        """获取龙虎榜当日上榜股票列表。

        Param:
            report_date: 报告日期，格式 "YYYY-MM-DD"
        Return:
            list[dict]: 龙虎榜股票列表，每个字典包含:
                - code (str): 股票代码
                - name (str): 股票名称
                - trade_date (str): 交易日期
                - close (float): 收盘价
                - change_pct (float): 涨跌幅
                - turnover_pct (float): 换手率
                - net_amount (float): 龙虎榜净买入（万元）
                - buy_amount (float): 买入金额（万元）
                - sell_amount (float): 卖出金额（万元）
                - deal_amount (float): 成交金额（万元）
                - total_amount (float): 总成交额（万元）
                - net_amount_rate (float): 净买入占比
                - deal_amount_rate (float): 成交占比
                - reason (str): 上榜原因
                - explain (str): 解释说明
                - d1_chg (float): D1 涨跌幅
                - d2_chg (float): D2 涨跌幅
                - d5_chg (float): D5 涨跌幅
        """
        columns = (
            "SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLAIN,CLOSE_PRICE,"
            "CHANGE_RATE,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,BILLBOARD_DEAL_AMT,"
            "ACCUM_AMOUNT,DEAL_NET_RATIO,DEAL_AMOUNT_RATIO,TURNOVERRATE,FREE_MARKET_CAP,EXPLANATION,"
            "D1_CLOSE_ADJCHRATE,D2_CLOSE_ADJCHRATE,D5_CLOSE_ADJCHRATE,D10_CLOSE_ADJCHRATE,SECURITY_TYPE_CODE"
        )
        filter_str = f"(TRADE_DATE<='{report_date}')(TRADE_DATE>='{report_date}')"
        data = self.fetch_datacenter_report(
            "RPT_DAILYBILLBOARD_DETAILSNEW", columns=columns,
            filter_str=filter_str, page_size=500,
            sort_columns="SECURITY_CODE,TRADE_DATE", sort_types="1,-1",
        )

        result = []
        for row in data:
            result.append(
                {
                    "code": row.get("SECURITY_CODE", ""),
                    "name": (row.get("SECURITY_NAME_ABBR") or "").replace(" ", ""),
                    "trade_date": report_date,
                    "close": safe_float(row.get("CLOSE_PRICE")),
                    "change_pct": safe_float(row.get("CHANGE_RATE")),
                    "turnover_pct": safe_float(row.get("TURNOVERRATE")),
                    "net_amount": self._fmt_amount(row.get("BILLBOARD_NET_AMT")),
                    "buy_amount": self._fmt_amount(row.get("BILLBOARD_BUY_AMT")),
                    "sell_amount": self._fmt_amount(row.get("BILLBOARD_SELL_AMT")),
                    "deal_amount": self._fmt_amount(row.get("BILLBOARD_DEAL_AMT")),
                    "total_amount": self._fmt_amount(row.get("ACCUM_AMOUNT")),
                    "net_amount_rate": safe_float(row.get("DEAL_NET_RATIO")),
                    "deal_amount_rate": safe_float(row.get("DEAL_AMOUNT_RATIO")),
                    "reason": row.get("EXPLANATION", ""),
                    "explain": row.get("EXPLAIN", ""),
                    "d1_chg": safe_float(row.get("D1_CLOSE_ADJCHRATE")),
                    "d2_chg": safe_float(row.get("D2_CLOSE_ADJCHRATE")),
                    "d5_chg": safe_float(row.get("D5_CLOSE_ADJCHRATE")),
                }
            )
        return result

    def fetch_dragon_tiger_stock_detail(self, code: str, report_date: str) -> list[dict]:
        """获取龙虎榜个股买卖明细。

        Param:
            code: 股票代码
            report_date: 报告日期，格式 "YYYY-MM-DD"
        Return:
            list[dict]: 买卖明细列表，每个字典包含:
                - side (str): "buy" 或 "sell"
                - code (str): 股票代码
                - operate_name (str): 营业部名称
                - buy_amount (float): 买入金额（万元）
                - sell_amount (float): 卖出金额（万元）
                - net_amount (float): 净买入（万元）
                - buy_ratio (float): 买入占比
                - sell_ratio (float): 卖出占比
        """
        result = []
        filter_str = f"(TRADE_DATE='{report_date}')(SECURITY_CODE=\"{code}\")"
        for side, report_name, sort_col in [
            ("buy", "RPT_BILLBOARD_DAILYDETAILSBUY", "BUY"),
            ("sell", "RPT_BILLBOARD_DAILYDETAILSSELL", "SELL"),
        ]:
            try:
                rows = self.fetch_datacenter_report(
                    report_name, filter_str=filter_str,
                    sort_columns=sort_col, sort_types="-1",
                )
                for row in rows:
                    result.append(
                        {
                            "side": side,
                            "code": row.get("SECURITY_CODE", ""),
                            "operate_name": row.get("OPERATEDEPT_NAME", ""),
                            "buy_amount": self._fmt_amount(row.get("BUY")),
                            "sell_amount": self._fmt_amount(row.get("SELL")),
                            "net_amount": self._fmt_amount(row.get("NET")),
                            "buy_ratio": safe_float(row.get("TOTAL_BUYRIO")),
                            "sell_ratio": safe_float(row.get("TOTAL_SELLRIO")),
                        }
                    )
            except Exception as e:
                logger.warning("龙虎榜明细[%s]获取失败: code=%s, date=%s, error=%s", side, code, report_date, e)
                continue
        return result
