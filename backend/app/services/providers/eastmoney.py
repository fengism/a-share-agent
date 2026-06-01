import json
import logging
import re
import time

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
from app.services.providers.akshare import akshare_provider
from app.services.base.intraday_utils import event_stream, normalize_intraday_df
from app.utils import http_client
from app.utils.symbol_utils import classify_exchange
from app.utils.symbol_utils import contains_stock_reference
from app.utils.data_clean import rename_and_keep_columns, safe_float

logger = logging.getLogger(__name__)


class EastMoneyDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="eastmoney", source_label="东方财富")
        self.REPORT_API = "https://reportapi.eastmoney.com/report/list"
        self.PDF_TPL = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
        self.UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self.DATACENTER_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"

    def fetch_datacenter_report(self, report_name: str, columns: str = "ALL",
                                filter_str: str = "", page_size: int = 50,
                                sort_columns: str = "", sort_types: str = "-1") -> list[dict]:
        """东财数据中心统一查询 — 龙虎榜/解禁/融资融券/大宗交易/股东户数/分红 共用"""
        params = {
            "reportName": report_name, "columns": columns,
            "filter": filter_str, "pageNumber": "1", "pageSize": str(page_size),
            "sortColumns": sort_columns, "sortTypes": sort_types,
            "source": "WEB", "client": "WEB",
        }
        r = requests.get(self.DATACENTER_URL, params=params, headers={"User-Agent": self.UA}, timeout=15)
        d = r.json()
        if d.get("result") and d["result"].get("data"):
            return d["result"]["data"]
        return []

    def fetch_stock_basic_info(self, code: str) -> dict:
        """
        东财个股基本面信息。
        返回: {code, name, industry, total_shares, float_shares, mcap, float_mcap, list_date}
        """
        market_code = 1 if code.startswith("6") else 0
        url = "https://push2.eastmoney.com/api/qt/stock/get"
        params = {
            "fltt": "2", "invt": "2",
            "fields": "f57,f58,f84,f85,f127,f116,f117,f189,f43",
            "secid": f"{market_code}.{code}",
        }

        r = requests.get(url, params=params, headers=COMMON_HEADERS, timeout=10)
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

    def fetch_kline(self, code: str, period: str, start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
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
        r = requests.get(EASTMONEY_STOCK_KLINE_URL, params=params, headers=EASTMONEY_HEADERS, timeout=10)
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

    def fetch_index_kline_direct(self, symbol: str, period: str, start_date: str, end_date: str) -> pd.DataFrame:
        secid_map = {code: secid for code, _name, secid in INDEX_FALLBACKS}
        secid = secid_map.get(symbol)
        if secid is None:
            raise ValueError(f"暂不支持该指数直连回退: {symbol}")

        klt = {"daily": "101", "weekly": "102", "monthly": "103"}.get(period, "101")
        try:
            response = http_client.post(
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
        return pd.DataFrame(rows, columns=["日期", "开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"])


    def fetch_stock_intraday_transactions(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
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
            temp_df = pd.DataFrame([item.split(",") for item in event_json["data"]["details"]])
            big_df = pd.concat(objs=[big_df, temp_df], ignore_index=True)
            break

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

    def fetch_stock_intraday_minute_direct(self, code: str = "000001", date: str | None = None) -> pd.DataFrame:
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


    def fetch_market_indices_direct(self) -> pd.DataFrame:
        response = requests.get(
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
            headers=EASTMONEY_HEADERS,
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
        return index_df

    def search_stocks(self, query: str, count: int = 10) -> list[StockSearchItem]:
        params = {
            "input": query,
            "type": "14",
            "token": EASTMONEY_SEARCH_SUGGEST_TOKEN,
            "count": str(max(count, 5)),
        }
        response = requests.get(EASTMONEY_SEARCH_SUGGEST_URL, params=params, headers=EASTMONEY_HEADERS, timeout=10)
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

    def _parse_search_item(self, item: dict) -> StockSearchItem | None:
        code = str(item.get("Code") or item.get("SecurityCode") or "").strip()
        name = str(item.get("Name") or item.get("SecurityName") or item.get("PinYin") or "").strip()
        if not code or not name or len(code) != 6 or not code.isdigit():
            return None
        if not self._is_a_share_search_item(item):
            return None
        return StockSearchItem(code=code, name=name)

    def _is_a_share_search_item(self, item: dict) -> bool:
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
        response = requests.get(
            EASTMONEY_CLIST_URL,
            params={
                "pn": "1",
                "pz": "6000",
                "po": "1",
                "np": "1",
                "ut": "bd1d9ddb04089700cf9c27f6f7426281",
                "fltt": "2",
                "invt": "2",
                "fid": "f3",
                "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
                "fields": "f12,f14",
            },
            timeout=15,
        )
        data = response.json()
        stocks: list[dict] = []
        for item in data.get("data", {}).get("diff", []):
            code = str(item.get("f12", ""))
            name = str(item.get("f14", "")).replace(" ", "")
            if code and name and len(code) == 6 and code.isdigit():
                stocks.append({"code": code, "name": name})
        return stocks

    def fetch_spot_snapshot_direct(self) -> pd.DataFrame:
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
            page_size=5000,
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

    def _fetch_clist_diff(self, params: dict[str, str], page_size: int = 200) -> list[dict]:
        all_data: list[dict] = []
        page = 1
        while True:
            req_params = {**params, "pn": str(page), "pz": str(page_size)}
            try:
                response = http_client.get(EASTMONEY_CLIST_URL, params=req_params, headers=EASTMONEY_HEADERS, timeout=15)
                data_json = response.json()
            except Exception as exc:
                logger.warning(f"东方财富 clist 请求失败: page={page}, error={exc}")
                raise

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

    def fetch_industry_boards_direct(self) -> pd.DataFrame:
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

    def fetch_industry_components_direct(self, board_code: str) -> pd.DataFrame:
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

    def build_industry_mapping_direct(self) -> tuple[dict[str, str], list[str]]:
        boards_df = self.fetch_industry_boards_direct()
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
                cons_df = self.fetch_industry_components_direct(board_code)
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
        timestamp = str(int(time.time() * 1000))
        params = {
            "client": "web",
            "biz": "web_news_col",
            "column": "366",
            "order": "1",
            "needInteractData": "0",
            "page_index": "1",
            "page_size": "50",
            "req_trace": timestamp,
            "fields": "code,showTime,title,mediaName,summary,image,url,uniqueUrl,Np_dst",
            "types": "1,20",
            "callback": "jQuery1830008903121921045032_1778650747671",
            "_": timestamp,
        }
        response = requests.get("https://np-listapi.eastmoney.com/comm/web/getNewsByColumns", params=params, timeout=10)
        response.raise_for_status()
        text = response.text.strip()
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("东方财富新闻接口返回格式异常")
        payload = json.loads(text[start:end + 1])

        results: list[NewsSearchItem] = []
        for item in payload.get("data", {}).get("list", []) or []:
            title = str(item.get("title") or "").strip()
            content = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    source=item.get("mediaName", ""),
                    publish_time=item.get("showTime") or "",
                    url=item.get("url", ""),
                    author=item.get("author", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def fetch_stock_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        return akshare_provider.fetch_stock_news(code=code)

    def fetch_stock_comments(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
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
        response = requests.get(
            "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist",
            params=params,
            headers=EASTMONEY_HEADERS,
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
        url = f"http://guba.eastmoney.com/list,{code},f_{page}.html"
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"http://guba.eastmoney.com/list,{code}.html",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }
        response = requests.get(url, headers=headers, timeout=15)
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
        if date is None:
            date = time.strftime("%Y%m%d", time.localtime())
        if "-" in date:
            date = date.replace("-", "")

        response = requests.get(
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
            headers=EASTMONEY_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = self._parse_json_from_text(response.text, "涨停池接口返回格式异常")
        payload = data.get("data") or {}
        return payload.get("pool") or [], int(payload.get("tc") or 0)

    def fetch_market_limit_down_pool(self, date: str | None = None) -> tuple[list[dict], int]:
        if date is None:
            date = time.strftime("%Y%m%d", time.localtime())
        if "-" in date:
            date = date.replace("-", "")

        response = requests.get(
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
            headers=EASTMONEY_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        data = self._parse_json_from_text(response.text, "跌停池接口返回格式异常")
        payload = data.get("data") or {}
        return payload.get("pool") or [], int(payload.get("tc") or 0)

    def fetch_market_pct_distribution(self, date: str | None = None) -> dict:
        response = requests.get(
            "https://push2ex.eastmoney.com/getTopicZDFenBu",
            params={
                "cb": "callbackdata6759488",
                "ut": "7eea3edcaed734bea9cbfc24409ed989",
                "dpt": "wz.ztzt",
                "_": str(int(time.time() * 1000)),
            },
            headers=EASTMONEY_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        return self._parse_json_from_text(response.text, "分布统计接口返回格式异常").get("data") or {}

    def _parse_json_from_text(self, text: str, error_message: str) -> dict:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(error_message)
        return json.loads(text[start:end + 1])

    def fetch_dragon_tiger_daily_list(self, report_date: str) -> list[dict]:
        url = (
            "https://datacenter-web.eastmoney.com/api/data/v1/get?"
            "sortColumns=SECURITY_CODE,TRADE_DATE&sortTypes=1,-1&pageSize=500&pageNumber=1"
            "&reportName=RPT_DAILYBILLBOARD_DETAILSNEW"
            "&columns=SECURITY_CODE,SECUCODE,SECURITY_NAME_ABBR,TRADE_DATE,EXPLAIN,CLOSE_PRICE,"
            "CHANGE_RATE,BILLBOARD_NET_AMT,BILLBOARD_BUY_AMT,BILLBOARD_SELL_AMT,BILLBOARD_DEAL_AMT,"
            "ACCUM_AMOUNT,DEAL_NET_RATIO,DEAL_AMOUNT_RATIO,TURNOVERRATE,FREE_MARKET_CAP,EXPLANATION,"
            "D1_CLOSE_ADJCHRATE,D2_CLOSE_ADJCHRATE,D5_CLOSE_ADJCHRATE,D10_CLOSE_ADJCHRATE,SECURITY_TYPE_CODE"
            f"&source=WEB&client=WEB"
            f"&filter=(TRADE_DATE<=%27{report_date}%27)(TRADE_DATE>=%27{report_date}%27)"
        )
        response = requests.get(url, timeout=15)
        text = response.text

        if text.lstrip().startswith(("jQuery", "jquery", "json")):
            start = text.index("{")
            data = json.loads(text[start:-2])
        else:
            data = json.loads(text)

        if not data.get("result") or not data["result"].get("data"):
            return []

        result = []
        for row in data["result"]["data"]:
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
        result = []
        for side, report_name, sort_col in [
            ("buy", "RPT_BILLBOARD_DAILYDETAILSBUY", "BUY"),
            ("sell", "RPT_BILLBOARD_DAILYDETAILSSELL", "SELL"),
        ]:
            url = (
                f"https://datacenter-web.eastmoney.com/api/data/v1/get?"
                f"reportName={report_name}&columns=ALL"
                f"&filter=(TRADE_DATE=%27{report_date}%27)(SECURITY_CODE=%22{code}%22)"
                f"&pageNumber=1&pageSize=50&sortTypes=-1&sortColumns={sort_col}"
                f"&source=WEB&client=WEB"
            )
            try:
                response = requests.get(url, timeout=10)
                data = response.json()
                if not data.get("result") or not data["result"].get("data"):
                    continue
                for row in data["result"]["data"]:
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
            except Exception:
                continue
        return result

    def _fmt_amount(self, value) -> float | None:
        result = safe_float(value)
        if result is None:
            return None
        return round(result / 10000, 2)
    
    
    def fetch_global_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """
        东方财富全球财经资讯（7x24 滚动）。
        https://np-weblist.eastmoney.com/comm/web/getFastNewsList?client=web&biz=web_724&fastColumn=102&sortEnd=&pageSize=50&req_trace=1779180355624&_=1779180355625&callback=jQuery183022672122379995496_1779180355554
        返回: [{title, summary, time}]
        """
        url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"
        params = {
            "client": "web", 
            "biz": "web_724",
            "fastColumn": "102", 
            "sortEnd": "",
            "req_trace": str(int(time.time() * 1000)),
            "pageSize": "50",
        }
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36", 
                   "Referer": "https://kuaixun.eastmoney.com/"
                }
        r = requests.get(url, params=params, headers=headers, timeout=10)
        d = r.json()
        

        rows = []
        for item in d.get("data", {}).get("fastNewsList", []):
            title = str(item.get("title") or "").strip()
            content = str(item.get("summary") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            rows.append(
                NewsSearchItem(
                    title=title,
                    content=content,
                    publish_time=item.get("showTime", ""),
                    url=item.get("url", ""),
                    source=item.get("mediaName", "") or "东方财富快讯",
                author=item.get("author", ""),
                read_count=int(item.get("read_count", 0)),
                comment_count=int(item.get("comment_count", 0)),
            ))
        return rows

    def fetch_stock_forecast_reports(self, code: str, max_pages: int = 5) -> pd.DataFrame:
        """拉取指定股票的研报列表"""
        session = requests.Session()
        session.headers.update({"User-Agent": self.UA, "Referer": "https://data.eastmoney.com/"})
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
            r = session.get(self.REPORT_API, params=params, timeout=30)
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
                    print(f"{label}: 无有效数据")
                else:
                    min = f"{valid.min():.2f}"
                    max = f"{valid.max():.2f}"
                    mean = f"{valid.mean():.2f}"
                    predict_stat_dict.append({"指标": label, "年度": year, "预测机构数": num_orgs,"最小值": min, "平均值": mean, "最大值": max, "行业平均数": None, "单位": "单位：元"})
            predict_stat_df = pd.DataFrame(predict_stat_dict)
        return predict_stat_df

    def fetch_industry_rankings(self, top_n: int = 20) -> dict:
        """
        全行业涨跌幅排名（东财行业板块，~100 个行业）。
        返回: {top: [...], bottom: [...], total: int}
        """
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": "1", "pz": "100", "po": "1", "np": "1",
            "fltt": "2", "invt": "2",
            "fs": "m:90+t:2",
            "fields": "f2,f3,f4,f12,f13,f14,f104,f105,f128,f136,f140,f141,f207",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        }

        r = requests.get(url, params=params, headers=headers, timeout=15)
        d = r.json()
        items = d.get("data", {}).get("diff", [])
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
        
    def fetch_stock_fund_flow(self, code: str) -> list[dict]:
        """
        个股资金流（日级，最近120个交易日）。
        返回: [{date, main_net(主力净流入), small_net, mid_net, large_net, super_net}]
        单位: 元
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
            r = requests.get(url, params=params, headers=EASTMONEY_HEADERS, timeout=15)
            d = r.json()
        except Exception as e:
            print(f"[WARN] push2 资金流请求失败: {e}")
            return []
        klines = d.get("data", {}).get("klines", [])

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


eastmoney_provider = EastMoneyDataProvider()


if __name__ == "__main__":
    #news = eastmoney_provider.fetch_stock_info("603228")
    #print(news)
    
    eastmoney_reports = eastmoney_provider.fetch_stock_fund_flow("600519")
    print(eastmoney_reports)