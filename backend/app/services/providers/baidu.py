import requests
import pandas as pd
import json


from app.services.base.data_provider import BaseDataProvider


class BaiduDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="baidu", source_label="百度")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://gushitong.baidu.com",
            "Accept": "application/json",
            "Origin": "https://gushitong.baidu.com",
            "Host": "finance.pae.baidu.com",
        }
        
        
    def fetch_stock_kline(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """百度股市通K线 — 独有能力: 返回时自带 ma5/ma10/ma20 均价"""
        url = "https://finance.pae.baidu.com/selfselect/getstockquotation"
        params = {
            "all": "1", "isIndex": "false", "isBk": "false", "isBlock": "false",
            "isFutures": "false", "isStock": "true", "newFormat": "1",
            "group": "quotation_kline_ab", "finClientType": "pc",
            "code": code, "start_time": start_date, "ktype": "1",
        }
        r = requests.get(url, params=params, headers=self.headers, timeout=10)
        d = r.json()
        result = d.get("Result", {})
        md = result.get("newMarketData", {})
        keys = md.get("keys", [])  # includes: ma5avgprice, ma10avgprice, ma20avgprice
        rows = md.get("marketData", "").split(";")
        data = pd.DataFrame([row.split(",") for row in rows], columns=keys)
        data["date"] = data["time"].apply(lambda x: x[:12])
        clumns = ["date", "open", "close", "high", "low", "volume", "amount","range", "ratio", "turnoverratio", "preClose"]
        data = data[clumns]
        data.columns = [
            "date",
            "open",
            "close",
            "high",
            "low",
            "volume",
            "amount",
            "amplitude",
            "change_pct",
            "turnover_pct",
            "pre_close",
        ]
        return data


    def fetch_stock_names(self) -> list[dict]:
        all_stocks: list[dict] = []
        page_size = 200
        for page_no in range(30):
            response = requests.get(
                "https://finance.pae.baidu.com/selfselect/getmarketrank",
                params={
                    "sort_type": "1",
                    "sort_key": "14",
                    "from_mid": "1",
                    "group": "pclist",
                    "type": "ab",
                    "finClientType": "pc",
                    "pn": str(page_no * page_size),
                    "rn": str(page_size),
                },
                headers=self.headers,
                timeout=15,
            )
            data = response.json()
            if data.get("ResultCode") != "0":
                break
            result_list = data.get("Result", {}).get("Result", [])
            if not result_list:
                break
            display_data = result_list[0].get("DisplayData", {})
            tpl_data = display_data.get("resultData", {}).get("tplData", {})
            rank = tpl_data.get("result", {}).get("rank", [])
            if not rank:
                break
            for item in rank:
                code = str(item.get("code", ""))
                name = str(item.get("name", "")).replace(" ", "")
                if code and name and len(code) == 6 and code.isdigit():
                    all_stocks.append({"code": code, "name": name})
            if len(rank) < page_size:
                break
        return all_stocks

    def fetch_stock_concept_blocks(self, code: str) -> dict:
        """
        百度股市通概念板块归属。
        https://finance.pae.baidu.com/api/getrelatedblock?stock={"market":"ab","type":"stock","code":"600519"}&finClientType=pc
        返回: {industry: [...], concept: [...], region: [...], concept_tags: [...]}
        """
        url = "https://finance.pae.baidu.com/api/getrelatedblock"
        
        params = {
            "stock": json.dumps({"market": "ab", "type": "stock", "code": code}),
            "finClientType": "pc"
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            raise RuntimeError(f"百度PAE错误: {d}")

        result = {"industry": [], "concept": [], "region": [], "concept_tags": []}
        data = d.get("Result", {})
        blocks = data.get(code, [])
        for block in blocks:
            name = block.get("name", "")
            for item in block.get("list", []):
                entry = {
                    "name": item.get("name", ""),
                    "change_pct": item.get("increase", ""),
                    "desc": item.get("desc", ""),
                }
                if name == "行业":
                    result["industry"].append(entry)
                elif name == "概念":    
                    result["concept"].append(entry)
                    result["concept_tags"].append(entry["name"])
                elif name == "地域":
                    result["region"].append(entry)
        return result
    
    
    def fetch_stock_fund_flow(self, code: str):
        """
        获取股票资金流数据
        https://finance.pae.baidu.com/vapi/v1/fundflow?finance_type=stock&fund_flow_type=&market=ab&code=600519&type=stock&finClientType=pc
        """
        url = "https://finance.pae.baidu.com/vapi/v1/fundflow"
        params = {
            "finance_type": "stock",
            "fund_flow_type": "",
            "market": "ab",
            "code": code,
            "type": "stock",
            "finClientType": "pc"
        }
        r = requests.get(url, headers=self.headers, params=params, timeout=10)
        d = r.json()
        if str(d.get("ResultCode", -1)) != "0":
            raise RuntimeError(f"百度PAE错误: {d}")
        result = d.get("Result", {})
        return result
        


baidu_provider = BaiduDataProvider()

if __name__ == "__main__":
    data = baidu_provider.fetch_stock_fund_flow("600519")
    print(data)

