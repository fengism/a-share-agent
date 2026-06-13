import json
import logging
import random
import re
import threading
import time
from urllib.parse import quote

from bs4 import BeautifulSoup
import pandas as pd
import requests


from app.constants.http import EASTMONEY_HEADERS, COMMON_HEADERS
from app.constants.market import (
    A_SHARE_SEARCH_CLASSIFY,
    EASTMONEY_API_TOKEN,
    EASTMONEY_CLIST_URL,
    INDEX_FALLBACKS,
    EASTMONEY_FLATTEN_FLAG,
    EASTMONEY_INDEX_QUOTE_FIELDS,
    EASTMONEY_INVESTOR_TYPE,
    EASTMONEY_KLINE_FIELDS1,
    EASTMONEY_KLINE_FIELDS2,
    EASTMONEY_SEARCH_SUGGEST_TOKEN,
    EASTMONEY_SEARCH_SUGGEST_URL,
    EASTMONEY_STOCK_KLINE_URL,
)
from app.models.search_item import NewsSearchItem
from app.models.stock import StockSearchItem
from app.services.base.data_provider import BaseDataProvider
from app.utils.intraday_utils import event_stream, normalize_intraday_df
from app.utils.symbol_utils import classify_exchange
from app.utils.symbol_utils import contains_stock_reference
from app.utils.data_clean import rename_and_keep_columns, safe_float
from app.config import get_settings

logger = logging.getLogger(__name__)


class EastMoneyDataProvider(BaseDataProvider):
    """东方财富数据提供者。

    封装东方财富公开 API，提供 A 股行情、K 线、分时、财务、研报、
    龙虎榜、涨停跌停池、行业板块、新闻资讯、资金流向等数据接口。
    所有请求通过 em_get_response 统一处理和 session 复用。

    属性:
        REPORT_API: 研报列表 API 地址
        PDF_TPL: 研报 PDF 下载模板 URL
        UA: 默认 User-Agent
        DATACENTER_URL: 东方财富数据中心 API 地址
        _em_last_call: 上次请求时间戳（用于节流）
        em_session: 复用的 requests.Session
        EM_MIN_INTERVAL: 两次请求最小间隔（秒）
    """

    def __init__(self):
        super().__init__(name="eastmoney", source_label="东方财富")
        self.REPORT_API = "https://reportapi.eastmoney.com/report/list"
        self.PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        self.UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self.DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
        self._em_last_call = 0.0
        self._em_lock = threading.Lock()
        self.em_session = requests.Session()
        self.em_session.trust_env = get_settings().http_trust_env
        self.em_session.headers.update({"User-Agent": self.UA})
        self.EM_MIN_INTERVAL = 1.0
        self.eastmoney_headers = EASTMONEY_HEADERS.copy()
        # 支持自定义 cookie（配置为空时使用 http.py 中的内置默认值）
        custom_cookie = get_settings().eastmoney_cookie
        if custom_cookie:
            self.eastmoney_headers["cookie"] = custom_cookie

    def em_get_response(self, url, params=None, headers=None, timeout=15, **kwargs):
        """东财统一请求入口：自动节流 + 复用 session。

        Param:
            url: 请求地址
            params: URL 查询参数
            headers: 请求头
            timeout: 超时秒数
        Return:
            requests.Response 响应对象
        """
        with self._em_lock:
            wait = self.EM_MIN_INTERVAL - (time.time() - self._em_last_call)
            if wait > 0:
                time.sleep(wait + random.uniform(0.1, 0.5))
            try:
                return self.em_session.get(url, params=params, headers=headers, timeout=timeout, **kwargs)
            finally:
                self._em_last_call = time.time()

    def fetch_datacenter_report(self, report_name: str, columns: str = "ALL",
                                filter_str: str = "", page_size: int = 50,
                                sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
        """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用。

        Param:
            report_name: 报表名称，对应东财数据中心的 reportName 参数
            columns: 返回字段，默认 "ALL"
            filter_str: 过滤条件字符串
            page_size: 每页条数
            sort_columns: 排序字段
            sort_types: 排序方向（-1 倒序，1 正序）
        Return:
            list[dict]: 报表数据行列表，每行为一个字典；无数据时返回空列表
        """
        params = {
            "reportName": report_name, "columns": columns,
            "pageNumber": "1", "pageSize": str(page_size),
            "sortColumns": sort_columns, "sortTypes": sort_types,
            "source": "WEB", "client": "WEB",
        }
        # filter 需要手工拼入 URL：requests 不编码 ' " < > 等字符，
        # 但东财 ANTLR 解析器要求 %27 %22 %3C %3E 形式。
        url = self.DATACENTER_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        if filter_str:
            url += "&filter=" + quote(filter_str, safe="")
        r = self.em_get_response(url, headers={"User-Agent": self.UA}, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
        return []
    

    def search_stocks(self, query: str, count: int = 10) -> list[StockSearchItem]:
        """搜索股票。

        根据关键词（代码、名称、拼音）搜索 A 股股票。

        Param:
            query: 搜索关键词（如 "600519"、"贵州茅台"、"GZMT"）
            count: 返回结果数量上限，默认 10
        Return:
            list[StockSearchItem]: 搜索结果列表，每个元素包含 code 和 name
        """
        params = {
            "input": query,
            "type": "14",
            "token": EASTMONEY_SEARCH_SUGGEST_TOKEN,
            "count": str(max(count, 5)),
        }
        response = self.em_get_response(EASTMONEY_SEARCH_SUGGEST_URL, params=params, headers=self.eastmoney_headers, timeout=10)
        data = response.json().get("QuotationCodeTable", {}).get("Data") or []
        results: list[StockSearchItem] = []
        seen_codes: set[str] = set()
        for item in data:
            parsed = self._parse_search_item(item)
            if parsed is None or parsed.code in seen_codes:
                continue
            results.append(parsed)
            seen_codes.add(parsed.code)
            if len(results) >= count:
                break
        return results


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

    def fetch_kline(self, code: str, period: str, start_date: str, end_date: str, adjust: str = "qfq") -> pd.DataFrame:
        """获取个股历史 K 线数据

        Param:
            code: 6 位股票代码
            period: K 线周期，可选 "daily"（日线）、"weekly"（周线）、"monthly"（月线）
            start_date: 起始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
            adjust: 复权方式，"qfq"（前复权，默认）、"hfq"（后复权）、""（不复权）
        Return:
            pd.DataFrame: 包含列: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, 振幅, 涨跌幅, 涨跌额, 换手率
        """
        se_cid = 1 if code.startswith("6") else 0
        k_type_map = {"daily": "101", "weekly": "102", "monthly": "103"}
        klt = k_type_map.get(period, "101")
        fqt_map = {"qfq": 1, "hfq": 2, "": 0}
        fqt = fqt_map.get(adjust, 1)

        params = {
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116",
            "ut": "7eea3edcaed734bea9cbfc24409ed989",
            "klt": klt,
            "fqt": fqt,
            "secid": f"{se_cid}.{code}",
            "beg": start_date,
            "end": end_date,
            "_": "1623766962675",
        }
        r = self.em_get_response(EASTMONEY_STOCK_KLINE_URL, params=params, headers=self.eastmoney_headers, timeout=10)
        data_json = r.json()

        if not data_json.get("data") or not data_json["data"].get("klines"):
            return pd.DataFrame()

        lines = data_json["data"]["klines"]
        data = [item.split(",")[:11] for item in lines]
        df = pd.DataFrame(
            data=data,
            columns=["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"],
        )
        df["成交量"] = pd.to_numeric(df["成交量"], errors="coerce")
        if "振幅" in df.columns:
            df["振幅"] = pd.to_numeric(df["振幅"], errors="coerce")
        return df

    def fetch_index_kline(self, symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取大盘指数历史 K 线数据。

        Param:
            symbol: 指数代码（如 "000001" 上证指数、"399001" 深证成指）
            period: K 线周期，可选 "daily"、"weekly"、"monthly"
            start_date: 起始日期，格式 "YYYYMMDD"
            end_date: 结束日期，格式 "YYYYMMDD"
        Return:
            pd.DataFrame: 包含列: 日期, 开盘, 收盘, 最高, 最低, 成交量(总手), 成交额(元), 振幅, 涨跌幅, 涨跌额, 换手率
        """
        secid_map = {code: secid for code, _name, secid in INDEX_FALLBACKS}
        secid = secid_map.get(symbol)
        if secid is None:
            raise ValueError(f"暂不支持该指数直连回退: {symbol}")

        klt = {"daily": "101", "weekly": "102", "monthly": "103"}.get(period, "101")
        try:
            response = self.em_get_response(
                EASTMONEY_STOCK_KLINE_URL,
                params={
                    "secid": secid,
                    "ut": EASTMONEY_API_TOKEN,
                    "fields1": EASTMONEY_KLINE_FIELDS1,
                    "fields2": EASTMONEY_KLINE_FIELDS2,
                    "klt": klt,
                    "fqt": "1",
                    "beg": start_date or "0",
                    "end": end_date or "20500101",
                    "smplmt": "100000",
                    "lmt": "1000000",
                    "_": "1722235849235",
                },
                headers={},
                timeout=10,
            )
            data = (response.json() or {}).get("data") or {}
        except Exception as exc:
            logger.warning(f"大盘指数K线直连失败: symbol={symbol}, error={exc}")
            raise

        if str(data.get("code", "")) and str(data.get("code", "")) != symbol:
            return pd.DataFrame()

        lines = data.get("klines") or []
        if not lines:
            return pd.DataFrame()

        rows = [item.split(",") for item in lines]

        df = pd.DataFrame(rows, columns=["date", "open", "close", "high", "low", "volume", "amount", "amplitude", "change_pct", "change", "turnover_pct"])
        df["pre_close"] = df["close"].shift(1) 
        return df


    def fetch_stock_intraday_transactions(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """获取个股分时成交明细（逐笔成交）。

        通过 SSE 推送接口获取当日逐笔成交数据。

        Param:
            code: 6 位股票代码，默认 "000001"
            date: 交易日期，格式 "YYYY-MM-DD"，默认当日
        Return:
            pd.DataFrame: 包含列: 时间, 成交价, 成交量, 成交额, 买卖盘性质
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://61.push2delay.eastmoney.com/api/qt/stock/details/sse"
        params = {
            "fields1": "f1,f2,f3,f4",
            "fields2": "f51,f52,f53,f54,f55",
            "mpi": "2000",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "pos": "-0",
            "secid": f"{market_code}.{code}",
            "wbp2u": "|0|0|0|web",
        }

        big_df = pd.DataFrame()
        for event in event_stream(url, params):
            event_json = json.loads(event.replace("data: ", ""))
            details = event_json.get("data", {}).get("details") or []
            if not details:
                continue
            temp_df = pd.DataFrame([item.split(",") for item in details])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
            break

        if big_df.empty or len(big_df.columns) < 5:
            return pd.DataFrame()
        big_df.columns = ["时间", "成交价", "成交量", "-", "买卖盘性质"]
        big_df["买卖盘性质"] = big_df["买卖盘性质"].map({"2": "买盘", "1": "卖盘", "4": "中性盘"})
        if not big_df.empty:
            trade_date = date or pd.Timestamp.now().strftime("%Y-%m-%d")
            big_df["时间"] = big_df["时间"].map(lambda value: f"{trade_date} {str(value).strip()}")
        big_df = big_df[["时间", "成交价", "成交量", "买卖盘性质"]]
        big_df["成交价"] = pd.to_numeric(big_df["成交价"], errors="coerce")
        big_df["成交量"] = pd.to_numeric(big_df["成交量"], errors="coerce") * 100
        big_df["成交额"] = pd.to_numeric(big_df["成交价"], errors="coerce") * pd.to_numeric(big_df["成交量"], errors="coerce")
        return normalize_intraday_df(big_df)

    def fetch_stock_intraday_minute(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
        """获取个股分时分钟数据（1 分钟级别）。

        通过 SSE 推送接口获取分时走势的分钟级数据。

        Param:
            code: 6 位股票代码，默认 "000001"
            date: 交易日期，格式 "YYYY-MM-DD"，默认当日
        Return:
            pd.DataFrame: 包含列: 时间, 成交价, 手数, 成交额
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://69.push2.eastmoney.com/api/qt/stock/trends2/sse"
        params = {
            "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f17",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            "mpi": "1000",
            "ut": "fa5fd1943c7b386f172d6893dbfba10b",
            "ndays": "1",
            "iscr": "0",
            "iscca": "0",
            "secid": f"{market_code}.{code}",
            "wbp2u": "1849325530509956|0|1|0|web",
        }

        big_df = pd.DataFrame()
        for event in event_stream(url, params):
            event_json = json.loads(event.replace("data: ", ""))
            temp_df = pd.DataFrame([item.split(",") for item in event_json["data"]["trends"]])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
            break

        if big_df.empty or len(big_df.columns) < 7:
            return pd.DataFrame()
        result_df = pd.DataFrame({
            "时间": big_df.iloc[:, 0],
            "成交价": big_df.iloc[:, 4],
            "手数": big_df.iloc[:, 5],
            "成交额": big_df.iloc[:, 6],
        })
        result_df["成交价"] = pd.to_numeric(result_df["成交价"], errors="coerce")
        result_df["手数"] = pd.to_numeric(result_df["手数"], errors="coerce") * 100
        return normalize_intraday_df(result_df)


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

    def _parse_search_item(self, item: dict) -> StockSearchItem | None:
        """解析搜索结果项。

        Param:
            item: 东财搜索接口返回的原始字典
        Return:
            StockSearchItem | None: 解析成功返回 StockSearchItem，无效数据返回 None
        """
        code = str(item.get("Code") or item.get("SecurityCode") or "").strip()
        name = str(item.get("Name") or item.get("SecurityName") or item.get("PinYin") or "").strip()
        if not code or not name or len(code) != 6 or not code.isdigit():
            return None
        if not self._is_a_share_search_item(item):
            return None
        return StockSearchItem(code=code, name=name)

    def _is_a_share_search_item(self, item: dict) -> bool:
        """判断搜索结果是否为 A 股。

        通过代码、分类和市场信息综合判断。

        Param:
            item: 东财搜索接口返回的原始字典
        Return:
            bool: True 表示是 A 股，False 表示不是
        """
        classify = str(item.get("Classify") or item.get("SecurityTypeName") or "").strip()
        market = str(item.get("MarketType") or item.get("Market") or "").strip().upper()
        code = str(item.get("Code") or item.get("SecurityCode") or "").strip()
        if len(code) == 6 and code.isdigit():
            try:
                return classify_exchange(code) in {"SH", "SZ", "BJ"}
            except ValueError:
                return False
        if classify in A_SHARE_SEARCH_CLASSIFY:
            return True
        return market in {"SH", "SZ", "BJ", "CN"}

    def fetch_stock_names(self) -> list[dict]:
        """获取全市场股票代码和名称列表。

        通过东方财富 clist 接口分页获取所有 A 股的代码和名称。

        Return:
            list[dict]: 股票列表，每个字典包含:
                - code (str): 6 位股票代码
                - name (str): 股票名称（去除空格）
        """
        params={
                "pn": "1",
                "pz": "100",
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f14",
            }

        all_data = self._fetch_clist_diff(params, headers=self.eastmoney_headers, page_size=100)
        stocks: list[dict] = []
        for item in all_data:
            code = str(item.get("f12", ""))
            name = str(item.get("f14", "")).replace(" ", "")
            if code and name and len(code) == 6 and code.isdigit():
                stocks.append({"code": code, "name": name})
        return stocks

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
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
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

    def _fetch_clist_diff(self, params: dict[str, str], headers: dict = None, page_size: int = 100, url: str = EASTMONEY_CLIST_URL) -> list[dict]:
        """分页获取东方财富 clist 接口的全部 diff 数据。

        自动处理分页，直到数据取完或达到上限。

        Param:
            params: 请求参数字典（不含分页参数 pn/pz，由本方法自动添加）
            headers: 可选的自定义请求头，默认使用实例级东财请求头
            page_size: 每页条数，默认 100
            url: clist 接口 URL，默认使用 EASTMONEY_CLIST_URL
        Return:
            list[dict]: 所有页的 diff 数据合并列表
        """
        all_data: list[dict] = []
        page = 1
        while True:
            req_params = {**params, "pn": str(page), "pz": str(page_size)}
            try:
                response = self.em_get_response(url, params=req_params, headers=headers, timeout=15)
                if response.status_code != 200:
                    logger.warning(f"东方财富 clist HTTP 错误: page={page}, status={response.status_code}")
                    break
                data_json = response.json()
            except Exception as exc:
                logger.warning(f"东方财富 clist 请求失败: page={page}, error={exc}")
                break
            data = data_json.get("data") or {}
            diff = data.get("diff") or []
            if not diff:
                break

            all_data.extend(diff)
            total = int(data.get("total") or 0)
            if total and page * page_size >= total:
                break
            if len(diff) < page_size:
                break
            page += 1
        return all_data

    def fetch_industry_boards(self) -> pd.DataFrame:
        """获取东财行业板块列表。

        Return:
            pd.DataFrame: 包含列: 板块代码, 板块名称
        """
        params = {
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90 t:2 f:!50",
            "fields": "f12,f14",
        }
        diff = self._fetch_clist_diff(params, page_size=200)
        if not diff:
            return pd.DataFrame(columns=["板块代码", "板块名称"])

        df = pd.DataFrame(diff).rename(columns={"f12": "板块代码", "f14": "板块名称"})
        keep_cols = [column for column in ["板块代码", "板块名称"] if column in df.columns]
        return df[keep_cols]

    def fetch_industry_components(self, board_code: str) -> pd.DataFrame:
        """获取指定行业板块的成分股列表。

        Param:
            board_code: 行业板块代码
        Return:
            pd.DataFrame: 包含列: 代码, 名称
        """
        params = {
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": f"b:{board_code} f:!50",
            "fields": "f12,f14",
        }
        diff = self._fetch_clist_diff(params, page_size=200)
        if not diff:
            return pd.DataFrame(columns=["代码", "名称"])

        df = pd.DataFrame(diff).rename(columns={"f12": "代码", "f14": "名称"})
        keep_cols = [column for column in ["代码", "名称"] if column in df.columns]
        return df[keep_cols]

    def build_industry_mapping(self) -> tuple[dict[str, str], list[str]]:
        """构建股票代码到行业板块的映射关系。

        遍历所有行业板块，获取每个板块的成分股，建立映射。

        Return:
            tuple[dict[str, str], list[str]]:
                - dict: 股票代码 -> 行业板块名称 的映射
                - list: 所有行业板块名称列表
        """
        boards_df = self.fetch_industry_boards()
        mapping: dict[str, str] = {}
        industries: list[str] = []
        if "板块名称" in boards_df.columns:
            industries = boards_df["板块名称"].dropna().astype(str).tolist()

        if boards_df.empty or "板块代码" not in boards_df.columns or "板块名称" not in boards_df.columns:
            return mapping, industries

        for _, row in boards_df.iterrows():
            board_code = str(row["板块代码"])
            board_name = str(row["板块名称"])
            try:
                cons_df = self.fetch_industry_components(board_code)
                if "代码" not in cons_df.columns:
                    continue
                for code in cons_df["代码"]:
                    stock_code = str(code).strip().zfill(6)
                    if stock_code and stock_code.isdigit():
                        mapping[stock_code] = board_name
            except Exception as exc:
                logger.warning(f"东方财富直连获取行业成分失败: {board_name}({board_code}), error={exc}")
                continue
        return mapping, industries

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富财经新闻（中国+国际+导读）。

        Param:
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 新闻列表
        """
        news_ids: list[str] = []
        all_news: list[NewsSearchItem] = []
        for column, label in [("350", "中国新闻"), ("351", "国际新闻"), ("366", "导读新闻")]:
            try:
                items, news_ids = self._fetch_finance_news(
                    column=column, news_ids=news_ids, code=code, code_name=code_name,
                )
                all_news.extend(items)
            except Exception as e:
                logger.warning(f"东方财富{label}获取失败: {e}")
        return all_news

    def _fetch_finance_news(self, column: str = "", news_ids: list[str] | None = None,
                            code: str = "", code_name: str = "") -> tuple[list[NewsSearchItem], list[str]]:
        """获取东方财富单分类新闻。

        Param:
            column: 新闻分类 ID（如 "350" 中国新闻、"351" 国际新闻、"366" 导读新闻）
            news_ids: 已有的新闻 ID 列表，用于去重
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            tuple[list[NewsSearchItem], list[str]]:
                - list: 新闻列表
                - list: 更新后的新闻 ID 列表（含本次新增）
        """
        if news_ids is None:
            news_ids = []
        trace = str(int(time.time() * 1000))
        url = "https://np-listapi.eastmoney.com/comm/web/getNewsByColumns"
        params = {
            "client": "web", "biz": "web_news_col", "column": str(column),
            "order": "1", "needInteractData": "0", "page_index": "1", "page_size": "20",
            "req_trace": trace,
            "fields": "code,showTime,title,mediaName,summary,image,url,uniqueUrl,Np_dst",
            "types": "1,20", "_": trace,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows: list[NewsSearchItem] = []
        for item in d.get("data", {}).get("list", []):
            title = str(item.get("title") or "").strip()
            content = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            news_id = item.get("code", title)
            if news_id in news_ids:
                continue
            news_ids.append(news_id)
            rows.append(NewsSearchItem(
                title=title, content=content,
                publish_time=item.get("showTime", ""),
                url=item.get("url", ""),
                source="东方财富",
                author=item.get("mediaName", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            ))
        return rows, news_ids

    def fetch_stock_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富个股新闻（column=107）。

        Param:
            code: 股票代码
            code_name: 股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 新闻列表
        """
        url = "http://search-api-web.eastmoney.com/search/jsonp"
        inner_param = {
            "uid": "",
            "keyword": code,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": 10,
                    "preTag": "<em>",
                    "postTag": "</em>",
                }
            },
        }
        params = {
            "cb": "jQuery35101792940631092459_1764599530165",
            "param": json.dumps(inner_param, ensure_ascii=False),  # 保留中文,
            "_": "1764599530176",
        }
        headers = {
            "accept": "*/*",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en,zh-CN;q=0.9,zh;q=0.8",
            "cache-control": "no-cache",
            "connection": "keep-alive",
            **({"cookie": self.eastmoney_headers["cookie"]} if "cookie" in self.eastmoney_headers else {}),
            "host": "search-api-web.eastmoney.com",
            "pragma": "no-cache",
            "referer": f"https://so.eastmoney.com/news/s?keyword={code}",
            "sec-ch-ua": '"Chromium";v="142", "Google Chrome";v="142", "Not_A Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "script",
            "sec-fetch-mode": "no-cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        data_text = r.text
        data_json = self._parse_json_from_text(data_text, "个股新闻接口返回格式异常")
        temp_df = pd.DataFrame(data_json.get("result", {}).get("cmsArticleWebOld") or [])
        if temp_df.empty:
            return []
        temp_df["url"] = "http://finance.eastmoney.com/a/" + temp_df["code"] + ".html"
        temp_df.rename(
            columns={
                "date": "publish_time",
                "mediaName": "source",
                "code": "-",
                "title": "title",
                "content": "content",
                "url": "url",
                "image": "-",
            },
            inplace=True,
        )
        temp_df["code"] = code
        temp_df = temp_df[
            [
                "code",
                "title",
                "content",
                "publish_time",
                "source",
                "url",
            ]
        ]
        temp_df["title"] = (
            temp_df["title"]
            .str.replace(r"\(<em>", "", regex=True)
            .str.replace(r"</em>\)", "", regex=True)
        )
        temp_df["title"] = (
            temp_df["title"]
            .str.replace(r"<em>", "", regex=True)
            .str.replace(r"</em>", "", regex=True)
        )
        temp_df["content"] = (
            temp_df["content"]
            .str.replace(r"\(<em>", "", regex=True)
            .str.replace(r"</em>\)", "", regex=True)
        )
        temp_df["content"] = (
            temp_df["content"]
            .str.replace(r"<em>", "", regex=True)
            .str.replace(r"</em>", "", regex=True)
        )
        temp_df["content"] = temp_df["content"].str.replace(r"\u3000", "", regex=True)
        temp_df["content"] = temp_df["content"].str.replace(r"\r\n", " ", regex=True)
        results: list[NewsSearchItem] = []
        if temp_df is not None and not temp_df.empty:
            for _, row in temp_df.head(20).iterrows():
                results.append(
                    NewsSearchItem(
                        title=str(row.get("title", "")),
                        content=str(row.get("content", "")),
                        source=str(row.get("source", "")),
                        publish_time=str(row.get("publish_time", "")),
                        url=str(row.get("url", "")),
                        author=str(row.get("author", "")),
                        read_count=int(row.get("read", 0)),
                        comment_count=int(row.get("comment", 0)),
                    )
                )
        return results

    def fetch_market_kuaixun(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富 7x24 快讯。

        Param:
            code: 可选，股票代码，用于过滤相关新闻
            code_name: 可选，股票名称，用于过滤相关新闻
        Return:
            list[NewsSearchItem]: 快讯列表
        """
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {
            "client": "web", "biz": "web_724", "fastColumn": "102",
            "sortEnd": "", "req_trace": str(int(time.time() * 1000)), "pageSize": "50",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://kuaixun.eastmoney.com/",
        }
        r = self.em_get_response(url, params=params, headers=headers, timeout=10)
        d = r.json()
        rows = []
        for item in d.get("data", {}).get("fastNewsList", []):
            title = str(item.get("title") or "").strip()
            content_text = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content_text}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            rows.append(NewsSearchItem(
                title=title, content=content_text,
                publish_time=item.get("showTime", ""),
                url=item.get("url", ""),
                source=item.get("mediaName", "") or "东方财富快讯",
                author=item.get("author", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            ))
        return rows

    def fetch_stock_comments(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """获取东方财富股吧评论。

        Param:
            code: 股票代码
            code_name: 股票名称，用于过滤相关评论
        Return:
            list[NewsSearchItem]: 评论列表
        """
        params = {
            "code": "cjpl",
            "sorttype": "1",
            "ps": "24",
            "from": "CommonBaPost",
            "deviceid": "quoteweb",
            "version": "200",
            "product": "Guba",
            "plat": "Web",
            "needzd": "true",
            "callback": "jsonp_1778666941893_8qj7w84su07",
        }
        response = self.em_get_response(
            "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist",
            params=params,
            headers=self.eastmoney_headers,
            timeout=10,
        )
        response.raise_for_status()
        text = response.text.strip()
        start = text.find("(") + 1
        end = text.find(")")
        payload = json.loads(text[start:end])
        results: list[NewsSearchItem] = []
        for item in payload.get("re", []):
            title = str(item.get("post_title") or "").strip()
            content = str(item.get("content") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:500],
                    source=item.get("stockbar_name", ""),
                    publish_time=str(item.get("post_publish_time", "")),
                    url=item.get("url", ""),
                    author=item.get("user_nickname", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def fetch_stock_guba_posts(self, code: str = "600519", page: int = 1) -> list[NewsSearchItem]:
        """获取东方财富股吧帖子列表。

        通过解析股吧 HTML 页面获取帖子数据。

        Param:
            code: 股票代码，默认 "600519"
            page: 页码，默认 1
        Return:
            list[NewsSearchItem]: 帖子列表
        """
        url = f"http://guba.eastmoney.com/list,{code},f_{page}.html"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"http://guba.eastmoney.com/list,{code}.html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        response = self.em_get_response(url, headers=headers, timeout=15)
        response.raise_for_status()
        response.encoding = "utf-8"

        posts = self._extract_guba_article_list(response.text).get("re") or []
        results: list[NewsSearchItem] = []
        for post in posts:
            post_id = post.get("post_id", "")
            results.append(
                NewsSearchItem(
                    title=post.get("post_title", ""),
                    content=post.get("post_content", ""),
                    url=f"https://guba.eastmoney.com/news,{code},{post_id}.html",
                    publish_time=post.get("post_publish_time", ""),
                    source="eastmoney_guba",
                    author=post.get("user_nickname", "") or (post.get("post_user") or {}).get("user_nickname", ""),
                    read_count=post.get("post_click_count", 0),
                    comment_count=post.get("post_comment_count", 0),
                )
            )
        return results

    def _extract_guba_article_list(self, html: str) -> dict:
        """从股吧 HTML 中提取 article_list 数据。

        Param:
            html: 股吧页面 HTML 内容
        Return:
            dict: 包含 "re" 键的文章列表字典
        """
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            text = script.string or script.get_text()
            if not text or "var article_list" not in text:
                continue
            match = re.search(r"var\s+article_list\s*=\s*(\{.*?\})\s*;\s*var\s+other_list", text, re.S)
            if match:
                return json.loads(match.group(1))
        raise ValueError("未找到 article_list")

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
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
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
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
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

    def fetch_market_pct_distribution(self, date: str | None = None) -> dict:
        """获取市场涨跌幅分布统计。

        Return:
            dict: 涨跌幅分布数据，包含各涨跌幅区间的股票数量
        """
        response = self.em_get_response(
            "https://push2ex.eastmoney.com/getTopicZDFenBu",
            params={
                "cb": "callbackdata6759488",
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
                "dpt": "wz.ztzt",
                "_": str(int(time.time() * 1000)),
            },
            headers=self.eastmoney_headers,
            timeout=15,
        )
        response.raise_for_status()
        return self._parse_json_from_text(response.text, "分布统计接口返回格式异常").get("data") or {}

    def _parse_json_from_text(self, text: str, error_message: str) -> dict:
        """从可能包含 JSONP 包装的文本中提取 JSON 数据。

        Param:
            text: 原始响应文本，可能包含 callback 包装
            error_message: 解析失败时的错误提示
        Return:
            dict: 解析后的 JSON 字典
        """
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(error_message)
        return json.loads(text[start:end + 1])


    def _fmt_amount(self, value) -> float | None:
        """格式化金额为万元单位。

        Param:
            value: 原始金额值（元）
        Return:
            float | None: 万元为单位的金额，保留 2 位小数；输入无效返回 None
        """
        result = safe_float(value)
        if result is None:
            return None
        return round(result / 10000, 2)

    def fetch_stock_forecast_reports(self, code: str, max_pages: int = 5) -> pd.DataFrame:
        """获取指定股票的机构研报预测数据。

        拉取近 100 天内的机构研报，汇总 EPS 和 PE 预测统计。

        Param:
            code: 股票代码
            max_pages: 最大拉取页数，默认 5
        Return:
            pd.DataFrame: 包含列: 指标, 年度, 预测机构数, 最小值, 平均值, 最大值, 行业平均数, 单位
        """
        all_records = []
        end_time = time.strftime("%Y-%m-%d")
        begin_time = time.strftime("%Y-%m-%d", time.localtime(time.time() - 100 * 24 * 3600))
        for page in range(1, max_pages + 1):
            params = {
                "industryCode": "*", "pageSize": "100", "industry": "*",
                "rating": "*", "ratingChange": "*",
                "beginTime": begin_time, "endTime": end_time,
                "pageNo": str(page), "fields": "", "qType": "0",
                "orgCode": "", "code": code, "rcode": "",
                "p": str(page), "pageNum": str(page), "pageNumber": str(page),
            }
            r = self.em_get_response(self.REPORT_API, params=params,
                                     headers={"Referer": "https://data.eastmoney.com/"}, timeout=30)
            d = r.json()
            rows = d.get("data") or []
            if not rows:
                break
            
            all_records.extend([{"code": code,  
                                 "indvInduName": row.get("indvInduName", ""),
                                 "publishDate": row.get("publishDate", ""), 
                                 "orgName": row.get("orgName", ""),
                                 "recomend_rating": row.get("emRatingName", ""),
                                 "predictThisYearEps": row.get("predictThisYearEps", ""),
                                 "predictThisYearPe": row.get("predictThisYearPe", ""),
                                 "predictNextYearEps": row.get("predictNextYearEps", ""),
                                 "predictNextYearPe": row.get("predictNextYearPe", "")
                                 } 
                                for row in rows])
            
            if page >= (d.get("TotalPage", 1) or 1):
                break
            
            time.sleep(0.3)
        df = pd.DataFrame(all_records)
        predict_stat_dict = []
        predict_stat_df = pd.DataFrame(columns=["指标", "年度", "预测机构数", "最小值", "平均值", "最大值", "行业平均数", "单位"])
        if not df.empty:
            num_orgs = df["orgName"].nunique()
            this_year = str(time.localtime().tm_year)
            next_year = str(time.localtime().tm_year + 1)
            year_labels = {
                "predictThisYearEps": ("EPS", this_year),
                "predictThisYearPe": ("PE", this_year),
                "predictNextYearEps": ("EPS", next_year),
                "predictNextYearPe": ("PE", next_year),
            }
            for col in year_labels:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            predict_stat_dict = []
            for col, (metric, year) in year_labels.items():
                label = f"{metric}"
                valid = df[col].dropna()
                if valid.empty:
                    logger.debug("东方财富研报预测无有效数据: code=%s, metric=%s", code, label)
                else:
                    min_value = f"{valid.min():.2f}"
                    max_value = f"{valid.max():.2f}"
                    mean = f"{valid.mean():.2f}"
                    predict_stat_dict.append({"指标": label, "年度": year, "预测机构数": num_orgs,"最小值": min_value, "平均值": mean, "最大值": max_value, "行业平均数": None, "单位": "单位：元"})
            predict_stat_df = pd.DataFrame(predict_stat_dict)
        return predict_stat_df

    def fetch_industry_rankings(self, top_n: int = 20) -> dict:
        """获取全行业涨跌幅排名。

        获取东财行业板块（约 100 个行业）的涨跌幅排名。

        Param:
            top_n: 返回前 N 名和后 N 名，默认 20
        Return:
            dict: 包含以下字段:
                - top (list): 涨幅前 N 名列表，每个元素包含 rank, name, change_pct, code, up_count, down_count, leader, leader_change
                - bottom (list): 跌幅前 N 名列表（同上结构）
                - total (int): 行业总数
        """
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers)
        if not items:
            return {"top": [], "bottom": [], "total": 0}

        rows = []
        for i, item in enumerate(items):
            rows.append({
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            })

        return {
            "top": rows[:top_n],
            "bottom": rows[-top_n:],
            "total": len(rows),
        }
        
    def fetch_concept_rankings(self, top_n: int = 20) -> dict:
        """获取全概念涨跌幅排名。

        获取东财概念板块（约 100 个概念）的涨跌幅排名。

        Param:
            top_n: 返回前 N 名和后 N 名，默认 20
        Return:
            dict: 包含以下字段:
                - top (list): 涨幅前 N 名列表，每个元素包含 rank, name, change_pct, code, up_count, down_count, leader, leader_change
                - bottom (list): 跌幅前 N 名列表（同上结构）
                - total (int): 行业总数
        """
        url = "https://push2.eastmoney.com/webguest/api/qt/clist/get"
        params = {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f3",
            "fs": "m:90+t:3+f:!50",
            "dect": "1",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers, url=url)
        if not items:
            return {"top": [], "bottom": [], "total": 0}

        rows = []
        for i, item in enumerate(items):
            rows.append({
                "rank": i + 1,
                "name": item.get("f14", ""),
                "change_pct": item.get("f3", 0),
                "code": item.get("f12", ""),
                "up_count": item.get("f104", 0),
                "down_count": item.get("f105", 0),
                "leader": item.get("f140", ""),
                "leader_change": item.get("f136", 0),
            })

        return {
            "top": rows[:top_n],
            "bottom": rows[-top_n:],
            "total": len(rows),
        }
    
    @staticmethod
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

    @staticmethod
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
            "ut": "b2884a393a59ad64002292a3e90d46a5",
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
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
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
            "ut": "8dec03ba335b81bf4ebdf7b29ec27d15",
            "fs": "m:90+t:3",
            "fields": "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124,f1,f13",
        }
        try:
            items = self._fetch_clist_diff(params=params, headers=self.eastmoney_headers, page_size=100)
        except Exception as e:
            logger.warning("东方财富概念资金流请求失败: %s", e)
            return []
        return self._parse_fund_flow_items(items)

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
    

    def fetch_china_cpi(self):
        """
        中国CPI数据。
        https://datacenter-web.eastmoney.com/api/data/v1/get?columns=REPORT_DATE%2CTIME%2CNATIONAL_SAME%2CNATIONAL_BASE%2CNATIONAL_SEQUENTIAL%2CNATIONAL_ACCUMULATE%2CCITY_SAME%2CCITY_BASE%2CCITY_SEQUENTIAL%2CCITY_ACCUMULATE%2CRURAL_SAME%2CRURAL_BASE%2CRURAL_SEQUENTIAL%2CRURAL_ACCUMULATE&pageNumber=1&pageSize=20&sortColumns=REPORT_DATE&sortTypes=-1&source=WEB&client=WEB&reportName=RPT_ECONOMY_CPI&_=1780832254645
        Return:
            list[dict]: 中国CPI数据列表，每个字典包含:
                - date (str): 日期
                - CITY_SAME (float): 城市CPI
                - CITY_BASE (float): 城市CPI（基数）
                - CITY_SEQUENTIAL (float): 城市CPI(环比)
                - CITY_ACCUMULATE (float): 城市CPI(累计)
                - RURAL_SAME (float): 农村CPI
                - RURAL_BASE (float): 农村CPI（基数）
                - RURAL_SEQUENTIAL (float): 农村CPI(环比)
                - RURAL_ACCUMULATE (float): 农村CPI(累计)
                - NATIONAL_SAME (float): 国家CPI
                - NATIONAL_BASE (float): 国家CPI（基数）、            
                - NATIONAL_SEQUENTIAL (float): 国家CPI(环比)
                - NATIONAL_ACCUMULATE (float): 国家CPI(累计)
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CPI",
            filter_str="(REPORT_DATE >= '2023-01-01')",
            columns="REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL,NATIONAL_ACCUMULATE,CITY_SAME,CITY_BASE,CITY_SEQUENTIAL,CITY_ACCUMULATE,RURAL_SAME,RURAL_BASE,RURAL_SEQUENTIAL,RURAL_ACCUMULATE",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        
        return data
    

    def fetch_china_ppi(self):
        """
        中国工业品出厂价格指数（PPI）
        Return:
            list[dict]: 中国工业品出厂价格指数（PPI）数据列表，每个字典包含:
                - TIME (str): 日期
                - BASE (float): 当月PPI
                - BASE_SAME (float): 当月PPI同比增长
                - BASE_ACCUMULATE (float): PPI累计
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_PPI",
            filter_str="(REPORT_DATE >= '2023-01-01')",
            columns="REPORT_DATE,TIME,BASE,BASE_SAME,BASE_ACCUMULATE",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data
    

    def fetch_china_pmi(self):
        """
        中国采购经理人指数（PMI）
        Return:
            list[dict]: 中国采购经理人指数（PMI）数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - TIME (str): 日期
                - MAKE_INDEX (float): 制造业指数
                - MAKE_SAME (float): 制造业指数(环比)
                - NMAKE_INDEX (float): 非制造业指数
                - NMAKE_SAME (float): 非制造业指数(环比)
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_PMI",
            filter_str="(REPORT_DATE >= '2025-01-01')",
            columns="REPORT_DATE,TIME,MAKE_INDEX,MAKE_SAME,NMAKE_INDEX,NMAKE_SAME",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data
    
    def fetch_china_economy_currency_supply(self):
        """
        中国货币供应指数（货币供应）
        Return:
            list[dict]: 中国货币供应指数（货币供应指数）数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - TIME (str): 日期
                - BASIC_CURRENCY (float): M2数量(亿元)
                - BASIC_CURRENCY_SAME (float): M2数量同比增长
                - BASIC_CURRENCY_SEQUENTIAL (float): M2数量环比
                - CURRENCY (float): 货币供应指数M1(亿元)
                - CURRENCY_SAME (float): 货币供应指数M1同比增长
                - CURRENCY_SEQUENTIAL (float): 货币供应指数M1(环比)
                - FREE_CASH (float): 流通中现金指数M0(亿元)
                - FREE_CASH_SAME (float): 流通中现金指数M0同比增长
                - FREE_CASH_SEQUENTIAL (float): 流通中现金指数M0环比    
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CURRENCY_SUPPLY",
            filter_str="(REPORT_DATE >= '2025-01-01')",
            columns="REPORT_DATE,TIME,BASIC_CURRENCY,BASIC_CURRENCY_SAME,BASIC_CURRENCY_SEQUENTIAL,CURRENCY,CURRENCY_SAME,CURRENCY_SEQUENTIAL,FREE_CASH,FREE_CASH_SAME,FREE_CASH_SEQUENTIAL",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_lpr(self):
        """
        中国贷款市场报价利率（LPR）
        Return:
            list[dict]: LPR数据列表，每个字典包含:
                - TRADE_DATE (str): 日期
                - LPR1Y (float): 1年期LPR
                - LPR5Y (float): 5年期以上LPR
                - RATE_1 (float): 短期贷款利率
                - RATE_2 (float): 中长期贷款利率
        """
        data = self.fetch_datacenter_report(
            "RPTA_WEB_RATE",
            columns="ALL",
            page_size=20,
            sort_columns="TRADE_DATE", sort_types="-1",
        )
        return data
    
    def fetch_china_gdp(self):
        """
        中国GDP数据
        Return:
            list[dict]: GDP数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - DOMESTICL_PRODUCT_BASE (float): 国内生产总值
                - FIRST_PRODUCT_BASE (float): 第一产业生产总值
                - FIRST_SAME (float): 第一产业生产总值同比增长
                - SECOND_PRODUCT_BASE (float): 第二产业生产总值
                - SECOND_SAME (float): 第二产业生产总值同比增长
                - THIRD_PRODUCT_BASE (float): 第三产业生产总值
                - THIRD_SAME (float): 第三产业生产总值同比增长
                - SUM_SAME (float): GDP同比增长
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_GDP",
            columns="REPORT_DATE,TIME,DOMESTICL_PRODUCT_BASE,FIRST_PRODUCT_BASE,SECOND_PRODUCT_BASE,THIRD_PRODUCT_BASE,SUM_SAME,FIRST_SAME,SECOND_SAME,THIRD_SAME",
            page_size=20,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_shibor(self):
        """
        上海银行间同业拆放利率（SHIBOR）
        Return:
            list[dict]: SHIBOR数据列表，每个字典包含:
                - REPORT_DATE (str): 日期
                - REPORT_PERIOD (str): 报告周期
                - IR_RATE (float): 利率
                - CHANGE_RATE (float): 利率(环比)
                - INDICATOR_ID (str): 指标ID
                - LATEST_RECORD (int): 最新记录标志
                - MARKET (str): 市场
                - MARKET_CODE (str): 市场代码
                - CURRENCY (str): 货币
                - CURRENCY_CODE (str): 货币代码
        """
        data = self.fetch_datacenter_report(
            "RPT_IMP_INTRESTRATEN",
            filter_str="(LATEST_RECORD=1)(MARKET_CODE='001')",
            columns="REPORT_DATE,REPORT_PERIOD,IR_RATE,CHANGE_RATE,INDICATOR_ID,LATEST_RECORD,MARKET,MARKET_CODE,CURRENCY,CURRENCY_CODE",
            page_size=20,
            sort_columns="INDICATOR_ID", sort_types="-1",
        )
        return data

    def fetch_china_trade(self):
        """
        中国进出口贸易数据
        Return:
            list[dict]: 进出口数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - EXIT_ACCUMULATE (float): 出口累计
                - EXIT_ACCUMULATE_SAME (float): 出口累计同比
                - EXIT_BASE (float): 出口量
                - EXIT_BASE_SAME (float): 出口同比
                - EXIT_BASE_SEQUENTIAL (float): 出口环比
                - IMPORT_ACCUMULATE (float): 进口累计
                - IMPORT_ACCUMULATE_SAME (float): 进口累计同比
                - IMPORT_BASE (float): 进口量
                - IMPORT_BASE_SAME (float): 进口同比
                - IMPORT_BASE_SEQUENTIAL (float): 进口环比
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_CUSTOMS",
            columns="REPORT_DATE,TIME,EXIT_BASE,IMPORT_BASE,EXIT_BASE_SAME,IMPORT_BASE_SAME,EXIT_BASE_SEQUENTIAL,IMPORT_BASE_SEQUENTIAL,EXIT_ACCUMULATE,IMPORT_ACCUMULATE,EXIT_ACCUMULATE_SAME,IMPORT_ACCUMULATE_SAME",
            page_size=24,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

    def fetch_china_social_financing(self):
        """
        中国社会融资规模
        Return:
            list[dict]: 社融数据列表，每个字典包含:
                - TIME (str): 日期
                - REPORT_DATE (str): 日期
                - RMB_LOAN (float): 新增贷款
                - RMB_LOAN_SAME (float): 新增贷款同比
                - RMB_LOAN_SEQUENTIAL (float): 新增贷款环比
                - RMB_LOAN_ACCUMULATE (float): 新增贷款累计
                - LOAN_ACCUMULATE_SAME (float): 新增贷款累计同比
        """
        data = self.fetch_datacenter_report(
            "RPT_ECONOMY_RMB_LOAN",
            columns="REPORT_DATE,TIME,RMB_LOAN,RMB_LOAN_SAME,RMB_LOAN_SEQUENTIAL,RMB_LOAN_ACCUMULATE,LOAN_ACCUMULATE_SAME",
            page_size=24,
            sort_columns="REPORT_DATE", sort_types="-1",
        )
        return data

eastmoney_provider = EastMoneyDataProvider()

if __name__ == "__main__":
    
    eastmoney_reports = eastmoney_provider.fetch_china_shibor()
    print(eastmoney_reports)
