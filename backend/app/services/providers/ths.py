import json
import logging
from concurrent.futures import ThreadPoolExecutor

from bs4 import BeautifulSoup
import pandas as pd
import requests


from app.config import get_settings

def _get_ths_headers():
    """动态构建同花顺请求头，从 .env 配置获取 cookie。"""
    from app.constants.http import THS_HEADERS
    settings = get_settings()
    headers = dict(THS_HEADERS)
    if settings.ths_cookie:
        headers["cookie"] = settings.ths_cookie
    return headers
from app.models.market import MarketVolume
from app.services.base.data_provider import BaseDataProvider
from app.utils.data_clean import safe_float


logger = logging.getLogger(__name__)


class ThsDataProvider(BaseDataProvider):
    """Purpose: 封装同花顺 basic.10jqka、dq.10jqka、hexin 等多个域名接口，提供机构预期、热点、资金流向、沪深股通等数据。"""
    def __init__(self):
        """初始化 ThsDataProvider，固定 name 与 source_label。"""
        super().__init__(name="ths", source_label="同花顺")
        self._session = requests.Session()
        self._session.trust_env = get_settings().http_trust_env

    def _get_session(self) -> requests.Session:
        """获取当前 Session，并在运行时配置变更后同步 trust_env。"""
        trust_env = get_settings().http_trust_env
        if self._session.trust_env != trust_env:
            self._session.trust_env = trust_env
        return self._session

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict | None = None,
        data=None,
        json_body=None,
        headers: dict | None = None,
        timeout: int | float = 10,
    ) -> requests.Response:
        """通过复用的 Session 发起 HTTP 请求并检查状态码。"""
        response = self._get_session().request(
            method,
            url,
            params=params,
            data=data,
            json=json_body,
            headers=headers,
            timeout=timeout,
        )
        response.raise_for_status()
        return response

    def _request_json(self, method: str, url: str, **kwargs) -> dict:
        """发起请求并解析 JSON。"""
        return self._request(method, url, **kwargs).json()

    @staticmethod
    def _normalize_hot_rank_items(items: list[dict], *, plate: bool = False) -> list[dict]:
        """规范化同花顺热点榜单数据。"""
        result = []
        for item in items or []:
            tag_info = item.get("tag") or {}
            concept_tag = ""
            pop_tag = ""
            if not plate:
                concept_tag = ";".join(tag_info.get("concept_tag") or [])
                pop_tag = str(tag_info.get("popularity_tag") or "").replace("\n", "")
            result.append(
                {
                    "rank": item.get("order"),
                    "code": item.get("code", ""),
                    "name": item.get("name", ""),
                    "change_pct": item.get("rise_and_fall"),
                    "hot_value": safe_float(item.get("rate")),
                    **(
                        {
                            "concept_tag": concept_tag,
                            "pop_tag": pop_tag,
                        }
                        if not plate
                        else {
                            "hot_tag": item.get("hot_tag", ""),
                            "tag": item.get("tag", ""),
                        }
                    ),
                }
            )
        return result

    def fetch_stock_forecast_reports(self, code: str) -> pd.DataFrame:
        """同花顺机构一致预期 EPS/净利润。

        Param:
            code: 6 位股票代码
        Return:
            包含指标、年度、预测机构数、最小值、均值、最大值、行业平均数、单位等列的 DataFrame
        """
        url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://basic.10jqka.com.cn/",
        }

        response = self._request("GET", url, headers=headers, timeout=15)
        response.encoding = "gbk"
        soup = BeautifulSoup(response.text, "html.parser")
        reports = []
        all_columns = None
        for table in soup.select("table.m_table.m_hl"):
            table_caption = table.select_one("caption.hltip.m_cap")
            if not table_caption:
                continue
            table_caption_text = table_caption.get_text().strip()
            table_unit = table_caption.select_one("span.fr.tip").get_text(strip=True) if table_caption.select_one("span.fr.tip") else ""
            table_title = table_caption_text.replace(table_unit, "").strip()
            table_name = ""
            if "年报每股收益" in table_title:
                table_name = "EPS"
            elif "年报净利润" in table_title:
                table_name = "NET_PROFIT"
            else:
                continue
            tabel_thead = table.select_one("thead")
            column_mapping = [cell.get_text(strip=True) for cell in tabel_thead.select('th')] if tabel_thead and tabel_thead.select('th') else []
            if "年度" not in column_mapping or "预测机构数" not in column_mapping or "均值" not in column_mapping:
                continue
            table_body = table.select_one("tbody")
            if not table_body:
                continue
            rows = table_body.select("tr")
            if not rows:
                continue
            for row in rows:
                year_cell = row.select_one("th")
                if not year_cell:
                    continue
                year = year_cell.get_text(strip=True)
                cells = [cell.get_text(strip=True) for cell in row.select("td")]
                values = [table_name, year] + cells + [table_unit]
                reports.append(values)
            if all_columns is None:
                all_columns = ["指标"] + column_mapping + ["单位"]

        if not reports or all_columns is None:
            return pd.DataFrame()

        df = pd.DataFrame(reports, columns=all_columns)
        numeric_columns = [c for c in all_columns if c not in ("指标", "年度", "单位")]
        for column in numeric_columns:
            cleaned = df[column].astype(str).str.extract(r"([-+]?\d+(?:\.\d+)?)", expand=False)
            df[column] = pd.to_numeric(cleaned, errors="coerce")
        return df

    def fetch_hot_stock_rank(self) -> list[dict]:
        """同花顺热点列表，包含个股和板块两部分（小时级）。

        Return:
            包含 rank、code、name、change_pct、hot_value、concept_tag、pop_tag 的字典列表
        """
        payload = self._request_json(
            "GET",
            "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock",
            params={
                "stock_type": "a",
                "type": "hour",
                "list_type": "normal",
            },
            headers=_get_ths_headers(),
            timeout=10,
        )
        stock_list = payload.get("data", {}).get("stock_list", [])
        return self._normalize_hot_rank_items(stock_list)

    def fetch_hot_plate_rank(self, plate_type: str) -> list[dict]:
        """同花顺热点板块排行（按指定板块类型）。

        Param:
            plate_type: 板块类型
        Return:
            包含 rank、code、name、change_pct、hot_value、hot_tag、tag 的字典列表
        """
        payload = self._request_json(
            "GET",
            "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate",
            params={"type": plate_type},
            headers=_get_ths_headers(),
            timeout=10,
        )
        plate_list = payload.get("data", {}).get("plate_list", [])
        return self._normalize_hot_rank_items(plate_list, plate=True)

    def fetch_market_volume_day(self) -> dict:
        """获取市场日内成交额（按日维度）。

        Return:
            包含 date、amount、amount_average_60_day、amount_before_one_day 的字典
        """
        return self._fetch_market_volume_chart("turnover_day")

    def fetch_market_volume_minute(self) -> dict:
        """获取市场日内成交额（按分钟维度）。

        Return:
            包含 amount 等字段的字典
        """
        return self._fetch_market_volume_chart("turnover_minute")

    def _fetch_market_volume_chart(self, chart_key: str) -> dict:
        """拉取同花顺 chart 接口数据并提取指定键的成交额信息。

        Param:
            chart_key: turnover_day/turnover_minute
        Return:
            提取后的成交额字典
        """
        payload = self._request_json(
            "GET",
            "https://dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data",
            params={"chart_key": chart_key},
            headers={"Accept": "*/*", "User-Agent": "Thunder Client (https://www.thunderclient.com)"},
            timeout=10,
        )
        if payload.get("status_code") != 0:
            return {}
        charts = payload.get("data", {}).get("charts", {})
        headers = charts.get("header", [])
        amount_data = {}
        if chart_key == "turnover_day":
            amount_data["date"] = charts.get("mtime", "").split(" ")[0]
        for header in headers:
            if header.get("key") == "average_turnover":
                amount_data["amount_average_60_day"] = header.get("val", 0)
            if header.get("key") == "turnover":
                amount_data["amount"] = header.get("val", 0)
            if header.get("key") == "turnover_pre":
                amount_data["amount_before_one_day"] = header.get("val", 0)
        return amount_data

    def fetch_market_volume(self) -> MarketVolume:
        """汇总分钟级与日级成交额数据，构造 MarketVolume 对象。

        Return:
            MarketVolume 模型实例
        """
        with ThreadPoolExecutor(max_workers=2) as executor:
            day_future = executor.submit(self.fetch_market_volume_day)
            minute_future = executor.submit(self.fetch_market_volume_minute)
            try:
                day_data = day_future.result()
            except Exception as exc:
                logger.warning("同花顺日级成交额获取失败: %s", exc)
                day_data = {}
            try:
                minute_data = minute_future.result()
            except Exception as exc:
                logger.warning("同花顺分钟级成交额获取失败: %s", exc)
                minute_data = {}
        minute_data.update(day_data)
        merged_data = {**minute_data}
        return MarketVolume(**merged_data)

    def fetch_hot_stock_reasons(self, date: str = None) -> pd.DataFrame:
        """同花顺当日强势股归因（含题材标签）。

        Param:
            date: 'YYYY-MM-DD' 格式，None=今天
        Return:
            含每只股票的题材归因等中文列名的 DataFrame
        """
        from datetime import date as _date
        if date is None:
            date = _date.today().strftime("%Y-%m-%d")

        url = (
            f"http://zx.10jqka.com.cn/event/api/getharden/"
            f"date/{date}/orderby/date/orderway/desc/charset/GBK/"
        )
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            )
        }
        data = self._request_json("GET", url, headers=headers, timeout=10)
        if data.get("errocode", 0) != 0:
            raise RuntimeError(f"同花顺热点错误: {data.get('errormsg', '')}")

        rows = data.get("data") or []
        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # 字段重命名（中文友好）
        rename_map = {
            "name": "名称", "code": "代码", "reason": "题材归因",
            "close": "收盘价", "zhangdie": "涨跌额", "zhangfu": "涨幅%",
            "huanshou": "换手率%", "chengjiaoe": "成交额",
            "chengjiaoliang": "成交量", "ddejingliang": "大单净量"
        }
        df = df.rename(columns=rename_map)
        return df
    

    def fetch_hsgt_realtime(self) -> pd.DataFrame:
        """沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）。

        Return:
            包含 time、hgt_yi(沪股通累计净买入)、sgt_yi(深股通累计净买入) 的 DataFrame（单位：亿元）
        """
        trade_date = self.get_trade_date()
        if not trade_date:
            trade_date = pd.Timestamp.now().strftime("%Y-%m-%d")

        url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            ),
            "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/",
        }
        d = self._request_json("GET", url, headers=headers, timeout=10)
        times = list(d.get("time") or [])
        hgt = list(d.get("hgt") or [])
        sgt = list(d.get("sgt") or [])

        n = len(times)
        full_times = [f"{trade_date} {t}" for t in times]
        return pd.DataFrame({
            "time": full_times,
            "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
            "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
        })
    
    def get_trade_date(self) -> str:
        """获取当前交易日期，格式 YYYY-MM-DD。

        Return:
            当前交易日期字符串
        """
        reqUrl = "https://quota-h.10jqka.com.cn/fuyao/common_hq_aggr/quote/v1/trade_time"

        headersList = {
            "Accept": "*/*",
            "User-Agent": "Thunder Client (https://www.thunderclient.com)",
            "Content-Type": "application/json" 
        }

        payload = json.dumps({
            "code_list": [
                {
                "codes": [
                    "1A0001"
                ],
                "market": "16"
                }
            ],
            "trade_date": 0,
            "gpid": 2
        })

        data = self._request_json("GET", reqUrl, data=payload, headers=headersList)
        time_info = data.get("data", {}).get("time_info") or []
        first_time_info = time_info[0] if time_info else {}
        trade_date = first_time_info.get("trade_date", "")
        return trade_date
        

ths_provider = ThsDataProvider()


if __name__ == "__main__":
    hot_stocks_data = ths_provider.fetch_hot_stock_reasons("2026-06-07")
    print(hot_stocks_data)  
