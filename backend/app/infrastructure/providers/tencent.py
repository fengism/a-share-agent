import json
from datetime import datetime

import pandas as pd

from app.constants.http import TENCENT_FINANCE_HEADERS
from app.constants.market import INDEX_FALLBACKS, TENCENT_STOCK_CONCEPT_URL, TENCENT_STOCK_QUOTE_URL
from app.core.dataframes import rename_columns
from app.core.market import normalize_code, safe_float
from app.domain.stock import StockConcept, StockConceptInfo
from app.infrastructure.http.client import get_provider_session as _get_session


def _quote_number(value: str, multiplier: float = 1) -> float | None:
    number = safe_float(value)
    return number * multiplier if number is not None else None


class TencentDataProvider:
    """Purpose: 对接腾讯财经代理接口的 K线、概念板块、行情快照、板块涨跌排行数据提供器。"""

    name = "tencent"

    def fetch_stock_concepts(self, code: str) -> StockConceptInfo | None:
        """获取个股所属概念、一级与二级行业板块。

        Param:
            code: 6 位股票代码
        Return:
            StockConceptInfo 对象；无数据时返回 None
        """
        normalized_code = normalize_code(code).prefixed_lower
        response = _get_session().get(
            TENCENT_STOCK_CONCEPT_URL,
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
            response = _get_session().get(url, params=params, timeout=10)
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

    def fetch_industry_rankings(self) -> tuple[pd.DataFrame, pd.DataFrame]:
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
        response = _get_session().get(
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

    @staticmethod
    def _parse_stock_quote_line(line: str) -> dict:
        if not line.strip() or "=" not in line or '"' not in line:
            return {}
        key = line.split("=", 1)[0].split("_")[-1]
        vals = line.split('"', 2)[1].split("~")
        if len(vals) < 53:
            return {}
        code = key[2:]
        quoted_at = None
        if vals[30]:
            try:
                quoted_at = datetime.strptime(vals[30], "%Y%m%d%H%M%S").isoformat(timespec="seconds")
            except ValueError:
                pass
        return {
            "code": code,
            "name": vals[1],
            "price": _quote_number(vals[3]),
            "last_close": _quote_number(vals[4]),
            "open": _quote_number(vals[5]),
            "volume": _quote_number(vals[6]),
            "change_amt": _quote_number(vals[31]),
            "change_pct": _quote_number(vals[32]),
            "high": _quote_number(vals[33]),
            "low": _quote_number(vals[34]),
            "amount": _quote_number(vals[37], 10000),
            "turnover_pct": _quote_number(vals[38]),
            "pe_ttm": _quote_number(vals[39]),
            "amplitude_pct": _quote_number(vals[43]),
            "float_mcap": _quote_number(vals[44], 100000000),
            "mcap": _quote_number(vals[45], 100000000),
            "pb": _quote_number(vals[46]),
            "limit_up": _quote_number(vals[47]),
            "limit_down": _quote_number(vals[48]),
            "vol_ratio": _quote_number(vals[49]),
            "pe_static": _quote_number(vals[52]),
            "quoted_at": quoted_at,
        }

    def _fetch_quotes(self, symbols: list[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        url = TENCENT_STOCK_QUOTE_URL + ",".join(symbols)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36",
        }
        response = _get_session().get(url, headers=headers, timeout=10)
        response.raise_for_status()
        quotes = {}
        for line in response.text.split(";"):
            quote = self._parse_stock_quote_line(line)
            if quote.get("code"):
                quotes[quote["code"]] = quote
        return quotes

    def fetch_market_indices(self) -> pd.DataFrame:
        """批量拉取页面关注的大盘指数实时行情。"""
        symbols = [f"{'sh' if secid.startswith('1.') else 'sz'}{code}" for code, _name, secid in INDEX_FALLBACKS]
        quotes = self._fetch_quotes(symbols)
        rows = []
        for code, fallback_name, _secid in INDEX_FALLBACKS:
            quote = quotes.get(code)
            if quote is None:
                continue
            rows.append(
                {
                    "代码": code,
                    "名称": quote.get("name") or fallback_name,
                    "最新价": quote.get("price"),
                    "涨跌幅": quote.get("change_pct"),
                    "成交量": quote.get("volume"),
                    "成交额": quote.get("amount"),
                    "今开": quote.get("open"),
                    "最高": quote.get("high"),
                    "最低": quote.get("low"),
                    "振幅": quote.get("amplitude_pct"),
                    "昨收": quote.get("last_close"),
                }
            )
        return pd.DataFrame(
            rows,
            columns=["代码", "名称", "最新价", "涨跌幅", "成交量", "成交额", "今开", "最高", "最低", "振幅", "昨收"],
        )

    def fetch_stock_quotes(self, codes: list[str]) -> dict[str, dict]:
        """批量拉取腾讯股票实时行情。"""
        symbols = [normalize_code(code) for code in dict.fromkeys(codes)]
        return self._fetch_quotes([symbol.prefixed_lower for symbol in symbols])

    def fetch_stock_quote(self, code: str) -> dict:
        """拉取单只股票的腾讯实时行情。

        Param:
            code: 6 位股票代码（支持个股/指数/ETF）
        Return:
            包含 name、price、pe_ttm、pb、mcap 等字段的字典
        """
        normalized = normalize_code(code).raw
        return self.fetch_stock_quotes([normalized]).get(normalized, {})

tencent_provider = TencentDataProvider()
