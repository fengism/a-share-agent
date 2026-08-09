from app.constants.http import COMMON_HEADERS


class FinancialsMixin:
    """东方财富 financials 数据接口。"""

    def fetch_stock_basic_info(self, code: str) -> dict:
        """获取个股基本面信息。

        通过东方财富推送接口获取单只股票的基础数据。

        Param:
            code: 6 位股票代码（如 "600519"）
        Return:
            dict: 包含以下字段:
                - code (str): 股票代码
                - name (str): 股票名称
                - industry (str): 所属行业
                - total_shares (int): 总股本（股）
                - float_shares (int): 流通股本（股）
                - mcap (int): 总市值（元）
                - float_mcap (int): 流通市值（元）
                - list_date (str): 上市日期（YYYYMMDD）
                - price (int): 最新价（分）
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{market_code}.{code}",
        }

        r = self.em_get_response(url, params=params, headers=COMMON_HEADERS, timeout=10)
        d = r.json().get("data", {})
        return {
            "code": d.get("f57", ""),
            "name": d.get("f58", ""),
            "industry": d.get("f127", ""),       # 所属行业
            "total_shares": d.get("f84", 0),     # 总股本(股)
            "float_shares": d.get("f85", 0),     # 流通股(股)
            "mcap": d.get("f116", 0),            # 总市值(元)
            "float_mcap": d.get("f117", 0),      # 流通市值(元)
            "list_date": str(d.get("f189", "")), # 上市日期 YYYYMMDD
            "price": d.get("f43", 0),
        }
