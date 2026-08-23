import logging

logger = logging.getLogger(__name__)



class MiscMixin:
    """东方财富 misc 数据接口。"""

    def fetch_market_margin_summary(self, page_size: int = 240) -> list[dict]:
        """
        沪深两市融资融券历史合计（日级）。
        Param:
            page_size: 每页条数（约等于返回的交易日数），默认 240（约一年）
        Return:
            按日期升序的 [{date, rzye(融资余额,亿), rqye(融券余额,亿), rzrqye(两融余额,亿), rzmre(融资买入额,亿), rzche(融资偿还额,亿), rzjme(融资净买入,亿)}]
        """
        data = self.fetch_datacenter_report(
            "RPTA_RZRQ_LSHJ",
            columns="ALL",
            page_size=page_size,
            sort_columns="DIM_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("DIM_DATE", ""))[:10],
                "rzye": row.get("RZYE", 0),
                "rqye": row.get("RQYE", 0),
                "rzrqye": row.get("RZRQYE", 0),
                "rzmre": row.get("RZMRE", 0),
                "rzche": row.get("RZCHE", 0),
                "rzjme": row.get("RZJME", 0),
            })
        rows.reverse()
        return rows

    def fetch_margin_trading(self, code: str, page_size: int = 30) -> list[dict]:
        """
        融资融券明细（日级）。
        Param:
            code: 6 位股票代码
            page_size: 每页条数，默认 30
        Return:
           [{date, rzye(融资余额), rzmre(融资买入额), rzche(融资偿还额), rqye(融券余额额), rqmcl(融券卖出量), rzrqye(融资融券余额合计),}]
        """
        data = self.fetch_datacenter_report(
            "RPTA_WEB_RZRQ_GGMX",
            filter_str=f'(SCODE="{code}")',
            page_size=page_size,
            sort_columns="DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("DATE", ""))[:10],
                "rzye": row.get("RZYE", 0),       # 融资余额(元)
                "rzmre": row.get("RZMRE", 0),      # 融资买入额
                "rzche": row.get("RZCHE", 0),      # 融资偿还额
                "rqye": row.get("RQYE", 0),        # 融券余额(元)
                "rqmcl": row.get("RQMCL", 0),      # 融券卖出量
                "rqchl": row.get("RQCHL", 0),      # 融券偿还量
                "rzrqye": row.get("RZRQYE", 0),    # 融资融券余额合计
            })
        return rows

    def fetch_block_trade(self, code: str, page_size: int = 20) -> list[dict]:
        """
        大宗交易记录。
        Param:
            code: 6 位股票代码
            page_size: 每页条数，默认 20
        Return:
            [{date, price, close, premium_pct, vol, amount, buyer, seller}]
        """
        data = self.fetch_datacenter_report(
            "RPT_DATA_BLOCKTRADE",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="TRADE_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            close = row.get("CLOSE_PRICE") or 0
            deal_price = row.get("DEAL_PRICE") or 0
            premium = ((deal_price / close - 1) * 100) if close else 0
            rows.append({
                "date": str(row.get("TRADE_DATE", ""))[:10],
                "price": deal_price,
                "close": close,
                "premium_pct": round(premium, 2),
                "vol": row.get("DEAL_VOLUME", 0),
                "amount": row.get("DEAL_AMT", 0),
                "buyer": row.get("BUYER_NAME", ""),
                "seller": row.get("SELLER_NAME", ""),
            })
        return rows

    def fetch_holder_num_change(self, code: str, page_size: int = 10) -> list[dict]:
        """
        股东户数变化（季度级）, 股东户数持续减少 = 筹码集中 = 主力吸筹信号
        Param:
            code: 6 位股票代码
            page_size: 每页条数，默认 10
        Return:
            [{date, holder_num, change_num, change_ratio, avg_shares}]
        """
        data = self.fetch_datacenter_report(
            "RPT_HOLDERNUMLATEST",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="END_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("END_DATE", ""))[:10],
                "holder_num": row.get("HOLDER_NUM", 0),
                "change_num": row.get("HOLDER_NUM_CHANGE", 0),
                "change_ratio": row.get("HOLDER_NUM_RATIO", 0),  # 环比%
                "avg_shares": row.get("AVG_FREE_SHARES", 0),     # 户均持股
            })
        return rows

    def fetch_dividend_history(self, code: str, page_size: int = 20) -> list[dict]:
        """
        分红送转历史。
        Param:
            code: 6 位股票代码
            page_size: 每页条数，默认 20
        Return:
            [{date, bonus_rmb(每股派息), transfer_ratio(转增比例), bonus_ratio(送股比例), plan(进度)}]
        """
        data = self.fetch_datacenter_report(
            "RPT_SHAREBONUS_DET",
            filter_str=f'(SECURITY_CODE="{code}")',
            page_size=page_size,
            sort_columns="EX_DIVIDEND_DATE", sort_types="-1",
        )
        rows = []
        for row in data:
            rows.append({
                "date": str(row.get("EX_DIVIDEND_DATE", ""))[:10],
                "bonus_rmb": row.get("PRETAX_BONUS_RMB", 0),    # 每股派息(税前)
                "transfer_ratio": row.get("TRANSFER_RATIO", 0),  # 每10股转增
                "bonus_ratio": row.get("BONUS_RATIO", 0),        # 每10股送股
                "plan": row.get("ASSIGN_PROGRESS", ""),           # 进度
            })
        return rows
