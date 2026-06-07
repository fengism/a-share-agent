import json
from datetime import datetime

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

from app.constants.http import TENCENT_FINANCE_HEADERS
from app.models.stock import StockConcept, StockConceptInfo
from app.services.base.data_provider import BaseDataProvider
from app.utils.symbol_utils import normalize_code
from app.utils.symbol_utils import normalize_index_symbol_v2
from app.utils.data_clean import rename_columns


class TencentDataProvider(BaseDataProvider):
    """Purpose: 对接腾讯财经代理接口的 K线、概念板块、行情快照、板块涨跌排行数据提供器。"""
    def __init__(self):
        """初始化 TencentDataProvider，固定 name 与 source_label。"""
        super().__init__(name="tencent", source_label="腾讯")

    def fetch_stock_concepts(self, code: str) -> StockConceptInfo | None:
        """获取个股所属概念、一级与二级行业板块。

        Param:
            code: 6 位股票代码
        Return:
            StockConceptInfo 对象；无数据时返回 None
        """
        normalized_code = normalize_index_symbol_v2(code).lower()
        response = requests.get(
            "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/stockinfo/plateNew",
            params={"code": normalized_code, "app": "wzq", "zdf": 1},
            headers=TENCENT_FINANCE_HEADERS,
            timeout=5,
        )
        response.raise_for_status()
        payload = json.loads(response.text).get("data")
        if payload is None:
            return None

        concepts = [StockConcept(code=item["id"], name=item["name"]) for item in payload.get("concept", [])]
        first_concept: StockConcept | None = None
        second_concept: StockConcept | None = None
        for plate in payload.get("plate", []):
            if plate.get("level", "0") == "1":
                first_concept = StockConcept(code=plate["code"], name=plate["name"])
            if plate.get("level", "0") == "2":
                second_concept = StockConcept(code=plate["code"], name=plate["name"])
        return StockConceptInfo(concepts=concepts, first_concept=first_concept, second_concept=second_concept)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def fetch_stock_kline(self, code: str, start_date: str, end_date: str, adjust: str="qfq") -> pd.DataFrame:
        """按年分片拉取腾讯个股 K 线，合并后计算振幅并重命名列。

        Param:
            code: 6 位股票代码
            start_date: 起始日期，格式 YYYY-MM-DD
            end_date: 结束日期，格式 YYYY-MM-DD
            adjust: 复权方式，默认 qfq
        Return:
            中文列名的 K线 DataFrame
        """
        sym = normalize_code(code)
        normalized_start = start_date.replace("-", "")
        normalized_end = end_date.replace("-", "")
        range_start = int(normalized_start[:4])
        current_year = datetime.now().year
        range_end = min(int(normalized_end[:4]) + 1, current_year + 1)
        url = "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get"

        big_df = pd.DataFrame()
        for year in range(range_start, range_end):
            params = {
                "_var": f"kline_day{adjust}{year}",
                "param": f"{sym.prefixed_lower},day,{year}-01-01,{year + 1}-12-31,640,{adjust}",
                "r": "0.8205512681390605",
            }
            response = requests.get(url, params=params, timeout=10)
            text = response.text
            json_start = text.find("={")
            if json_start < 0:
                continue
            payload = json.loads(text[json_start + 1 :])
            data_json = payload.get("data", {}).get(sym.prefixed_lower, {})
            if "day" in data_json:
                temp_df = pd.DataFrame(data_json["day"])
            elif "hfqday" in data_json:
                temp_df = pd.DataFrame(data_json["hfqday"])
            else:
                temp_df = pd.DataFrame(data_json.get("qfqday", []))
            if temp_df.empty:
                continue
            big_df = pd.concat([big_df, temp_df], ignore_index=True)

        if big_df.empty:
            return pd.DataFrame()

        big_df = big_df.iloc[:, :10].copy()
        big_df.columns = ["date", "open", "close", "high", "low", "volume", "field_1", "turnover_pct", "amount", "field_2"]
        del big_df["field_1"]
        del big_df["field_2"]
        big_df["date"] = pd.to_datetime(big_df["date"], errors="coerce")
        big_df["open"] = pd.to_numeric(big_df["open"], errors="coerce")
        big_df["close"] = pd.to_numeric(big_df["close"], errors="coerce")
        big_df["high"] = pd.to_numeric(big_df["high"], errors="coerce")
        big_df["low"] = pd.to_numeric(big_df["low"], errors="coerce")
        big_df["volume"] = pd.to_numeric(big_df["volume"], errors="coerce")
        big_df["amount"] = pd.to_numeric(big_df["amount"], errors="coerce") * 10000
        big_df["turnover_pct"] = pd.to_numeric(big_df["turnover_pct"], errors="coerce")
        big_df = big_df.dropna(subset=["date"]).drop_duplicates(ignore_index=True)
        big_df = big_df.sort_values("date")
        big_df = big_df[(big_df["date"] >= pd.to_datetime(normalized_start)) & (big_df["date"] <= pd.to_datetime(normalized_end))]
        big_df["date"] = big_df["date"].dt.strftime("%Y-%m-%d")
        big_df["amplitude"] = 100 * (big_df["high"] - big_df["low"]) / big_df["low"]
        return rename_columns(
            big_df,
            {
                "date": "日期",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量",
                "turnover_pct": "换手率",
                "amount": "成交额",
                "amplitude": "振幅",
            },
        )

    def fetch_market_sector_rankings(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """获取市场板块涨跌排行榜（涨与跌各一份）。

        Return:
            (涨榜 DataFrame, 跌榜 DataFrame)
        """
        return self._fetch_sector_ranking("0"), self._fetch_sector_ranking("1")

    def _fetch_sector_ranking(self, order: str) -> pd.DataFrame:
        """按指定排序方向拉取腾讯板块行情并重命名列。

        Param:
            order: 排序方向，"0" 升序/涨，"1" 降序/跌
        Return:
            板块行情 DataFrame
        """
        response = requests.get(
            "https://proxy.finance.qq.com/ifzqgtimg/appstock/app/mktHs/rank",
            params={
                "l": "10",
                "p": "1",
                "t": "01/averatio",
                "ordertype": "",
                "o": order,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()["data"]
        df = pd.DataFrame(data)
        df.rename(
            columns={
                "bd_name": "板块名称",
                "bd_code": "板块代码",
                "bd_zd": "涨跌额",
                "bd_zdf": "涨跌幅",
                "bd_zdf5": "5日涨跌幅",
                "bd_zdf20": "20日涨跌幅",
                "bd_zs": "bd_zs",
                "bd_zxj": "最新价",
                "nzg_code": "领涨跌股票代码",
                "nzg_name": "领涨跌股票名称",
                "nzg_zd": "领涨股票-涨跌额",
                "nzg_zdf": "领涨股票-涨跌幅",
                "nzg_zxj": "领涨股票-最新价",
            },
            inplace=True,
        )
        return df

    def fetch_stock_quote(self, code: str) -> dict:
        """批量拉取腾讯股票实时行情。

        Param:
            code: 6 位股票代码（支持个股/指数/ETF）
        Return:
            包含 name、price、pe_ttm、pb、mcap 等字段的字典
        """
        sym = normalize_code(code)
        prefixed = sym.prefixed_lower

        url = "https://qt.gtimg.cn/q=" + prefixed
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        }
        
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.text

        result = {}
        line = data.strip().split(";")[0]
        if not line.strip() or "=" not in line or '"' not in line:
            return result
        key = line.split("=")[0].split("_")[-1]
        vals = line.split('"')[1].split("~")
        if len(vals) < 53:
            return result
        code = key[2:]
        result = {
            "code":         code,
            "name":         vals[1],
            "price":        float(vals[3]) if vals[3] else 0,
            "last_close":   float(vals[4]) if vals[4] else 0,
            "open":         float(vals[5]) if vals[5] else 0,
            "change_amt":   float(vals[31]) if vals[31] else 0,
            "change_pct":   float(vals[32]) if vals[32] else 0,         
            "high":         float(vals[33]) if vals[33] else 0,
            "low":          float(vals[34]) if vals[34] else 0,                                                 
            "amount":       10000 * float(vals[37]) if vals[37] else 0,
            "turnover_pct": float(vals[38]) if vals[38] else 0,
            "pe_ttm":       float(vals[39]) if vals[39] else 0,
            "amplitude_pct":float(vals[43]) if vals[43] else 0,
            "float_mcap":   100000000 * float(vals[44]) if vals[44] else 0,
            "mcap":         100000000 * float(vals[45]) if vals[45] else 0,
            "pb":           float(vals[46]) if vals[46] else 0,
            "limit_up":     float(vals[47]) if vals[47] else 0,
            "limit_down":   float(vals[48]) if vals[48] else 0,
            "vol_ratio":    float(vals[49]) if vals[49] else 0,
            "pe_static":    float(vals[52]) if vals[52] else 0,
        }
        return result


tencent_provider = TencentDataProvider()

if __name__ == "__main__":
    print(tencent_provider.fetch_stock_kline("600519", "2026-06-01", "2026-06-07", "qfq"))
    #print(tencent_provider.fetch_market_sector_rankings())
    print(tencent_provider.fetch_stock_quote("600519"))