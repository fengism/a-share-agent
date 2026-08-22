from app.constants.http import COMMON_HEADERS
from app.constants.market import EASTMONEY_STOCK_PROFILE_URL
from app.infrastructure.providers.eastmoney.symbols import build_stock_secid


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
                - price (float): 最新价（元）
        """
        params = {
            "fltt": "2",
            "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": build_stock_secid(code),
        }

        response = self.em_get_response(
            EASTMONEY_STOCK_PROFILE_URL,
            params=params,
            headers=COMMON_HEADERS,
            timeout=10,
        )
        data = response.json().get("data") or {}
        return {
            "code": data.get("f57", ""),
            "name": data.get("f58", ""),
            "industry": data.get("f127", ""),
            "total_shares": data.get("f84", 0),
            "float_shares": data.get("f85", 0),
            "mcap": data.get("f116", 0),
            "float_mcap": data.get("f117", 0),
            "list_date": str(data.get("f189", "")),
            "price": data.get("f43", 0),
        }
