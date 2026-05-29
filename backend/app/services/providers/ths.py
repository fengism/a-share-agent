import requests
import pandas as pd
from bs4 import BeautifulSoup


from app.constants.http import THS_HEADERS
from app.models.market import MarketVolume
from app.services.base.data_provider import BaseDataProvider
from app.utils.data_clean import safe_float


class ThsDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="ths", source_label="同花顺")

    def fetch_stock_forecast_reports(self, code: str) -> pd.DataFrame:
        """
        同花顺机构一致预期EPS/净利润。
        直连 basic.10jqka.com.cn，解析HTML表格。
        返回 DataFrame: 指标, 年度, 预测机构数, 最小值, 均值, 最大值, 行业平均数, 单位
        "均值" = 机构一致预期值
        """
        url = f"https://basic.10jqka.com.cn/new/{code}/worth.html"
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://basic.10jqka.com.cn/",
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
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
        """
        同花顺热点列表，包含个股和板块两部分。
        https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock?stock_type=a&type=hour&list_type=normal
      
        """

        url = "https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock"
        params = {
            "stock_type": "a",
            "type": "hour", 
            "list_type": "normal", 
        }
        r = requests.get(url, params=params, headers=THS_HEADERS, timeout=10)
        
        stock_list = r.json()["data"]["stock_list"]
        result = []
        for d in stock_list:
            concept_tag = ""
            pop_tag = ""
            if "tag" in d:
                if "concept_tag" in d["tag"]:
                    concept_tag = ";".join(d["tag"]["concept_tag"])
                if "popularity_tag" in d["tag"]:
                    pop_tag = d["tag"]["popularity_tag"].replace("\n", "")
            result.append(
                {
                    "rank": d.get("order"),
                    "code": d.get("code", ""),
                    "name": d.get("name", ""),
                    "change_pct": d.get("rise_and_fall"),
                    "hot_value": safe_float(d.get("rate")),
                    "concept_tag": concept_tag,
                    "pop_tag": pop_tag,
                }
            )
        return result

    def fetch_hot_plate_rank(self, plate_type: str) -> list[dict]:
        url = f"https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate?type={plate_type}"
        r = requests.get(url, headers=THS_HEADERS, timeout=10)
        plate_list = r.json()["data"]["plate_list"]
        result = []
        for d in plate_list:
            result.append(
                {
                    "rank": d.get("order"),
                    "code": d.get("code", ""),
                    "name": d.get("name", ""),
                    "change_pct": d.get("rise_and_fall"),
                    "hot_value": safe_float(d.get("rate")),
                    "hot_tag": d.get("hot_tag", ""),
                    "tag": d.get("tag", ""),
                }
            )
        return result

    def fetch_market_volume_day(self) -> dict:
        return self._fetch_market_volume_chart("turnover_day")

    def fetch_market_volume_minute(self) -> dict:
        return self._fetch_market_volume_chart("turnover_minute")

    def _fetch_market_volume_chart(self, chart_key: str) -> dict:
        req_url = "https://dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data"
        response = requests.get(
            req_url,
            params={"chart_key": chart_key},
            headers={"Accept": "*/*", "User-Agent": "Thunder Client (https://www.thunderclient.com)"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
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
        day_data = self.fetch_market_volume_day()
        minute_data = self.fetch_market_volume_minute()
        minute_data.update(day_data)
        merged_data = {**minute_data}
        return MarketVolume(**merged_data)

    def fetch_hot_stock_reasons(self, date: str = None) -> pd.DataFrame:
        """
        同花顺当日强势股归因。
        date: 'YYYY-MM-DD' 格式，None=今天
        返回 DataFrame，含每只股票的题材标签 (reason)。
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
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
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
        """
        沪深股通当日实时分钟流向（含集合竞价 09:10–15:00，262 个时间点）。
        返回字段: time, hgt(沪股通累计净买入), sgt(深股通累计净买入)
        单位: 亿元
        """
        url = "https://data.hexin.cn/market/hsgtApi/method/dayChart/"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "Chrome/117.0.0.0 Safari/537.36"
            ),
            "Host": "data.hexin.cn",
            "Referer": "https://data.hexin.cn/",
        }
        r = requests.get(url, headers=headers, timeout=10)
        d = r.json()
        times = d.get("time", [])
        hgt = d.get("hgt", [])
        sgt = d.get("sgt", [])

        n = len(times)
        return pd.DataFrame({
            "time": times,
            "hgt_yi": hgt[:n] + [None] * (n - len(hgt)),
            "sgt_yi": sgt[:n] + [None] * (n - len(sgt)),
        })


ths_provider = ThsDataProvider()


if __name__ == "__main__":
    hot_stocks_data = ths_provider.fetch_hsgt_realtime()
    print(hot_stocks_data)  

