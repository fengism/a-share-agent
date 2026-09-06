"""东方财富交易所价格异动接口。"""

from app.core.market import safe_float, safe_int

ANOMALY_BASE = "https://dycalchis.eastmoney.com/price-anomaly"
ANOMALY_PARAMS = {
    "team": "h5",
    "product": "EastMoney",
    "client": "WAP",
    "version": "9001",
    "name": "WAP",
    "user": "123",
}
ANOMALY_REFERER = "https://vipmoney.eastmoney.com/"

ANOMALY_RULES = {
    1: "主板连续10个交易日内4次出现同向异常波动",
    2: "创业板连续10个交易日内3次出现同向异常波动",
    3: "科创板连续10个交易日内3次出现同向异常波动",
    4: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+100%",
    5: "连续十个交易日内日收盘价涨跌幅偏离值累计达到-50%",
    6: "连续三十个交易日内日收盘价涨跌幅偏离值累计达到+200%",
    7: "连续三十个交易日内日收盘价涨跌幅偏离值累计达到-70%",
    8: "北交所连续10个交易日内3次出现同向异常波动",
    40: "连续十个交易日内日收盘价涨跌幅偏离值累计达到+150%",
    50: "连续十个交易日内日收盘价涨跌幅偏离值累计达到-60%",
    60: "连续30个交易日内日收盘价涨跌幅偏离值累计达到+300%",
    70: "连续30个交易日内日收盘价涨跌幅偏离值累计达到-75%",
}


def _anomaly_market(code: object, market: object, board: object = None) -> str:
    """按代码号段优先识别交易所，避免把 m=0 的北交所误判为深市。"""
    code_text = str(code or "").strip()
    board_code = safe_int(board)
    if code_text.startswith("920") or code_text[:2] in {"43", "83", "87"} or board_code == 8:
        return "BJ"
    return "SH" if safe_int(market) == 1 else "SZ"


class PriceAnomalyMixin:
    """东方财富交易所价格异动接口。"""

    def _fetch_price_anomaly_page(
        self,
        path: str,
        page_size: int,
        page_no: int,
        **extra: str,
    ) -> dict:
        params = {
            **ANOMALY_PARAMS,
            "pageSize": str(page_size),
            "pageNo": str(page_no),
            **extra,
        }
        response = self.em_get_response(
            f"{ANOMALY_BASE}/{path}",
            params=params,
            headers={"Referer": ANOMALY_REFERER},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        result = safe_int(payload.get("result"))
        if result != 0:
            raise RuntimeError(
                f"东财异动接口拒绝: result={payload.get('result')} msg={payload.get('msg')!r}"
            )
        return payload

    def fetch_market_price_anomaly(self, page_size: int = 200, page_no: int = 1) -> dict:
        """获取交易所异动明细。"""
        payload = self._fetch_price_anomaly_page("list", page_size, page_no)
        items = []
        for row in payload.get("data") or []:
            event_code = safe_int(row.get("e"))
            board = safe_int(row.get("s"))
            rule_code = event_code * 10 if board == 6 and event_code in {4, 5, 6, 7} else event_code
            items.append({
                "code": str(row.get("c") or "").strip(),
                "name": str(row.get("n") or "").strip(),
                "market": _anomaly_market(row.get("c"), row.get("m"), board),
                "change_pct": safe_float(row.get("a")),
                "deviation": safe_float(row.get("x")),
                "days": safe_int(row.get("d")),
                "board": board,
                "rule_code": rule_code,
                "rule": ANOMALY_RULES.get(rule_code, f"未知规则码 {rule_code}"),
                "is_today": safe_int(row.get("o")) != 2,
            })
        return {
            "date": str(payload.get("date") or ""),
            "pages": safe_int(payload.get("pages")) or 0,
            "items": items,
        }

    def fetch_market_price_anomaly_count(
        self,
        page_size: int = 50,
        page_no: int = 1,
        sort_key: str = "",
        sort_dir: str = "",
    ) -> dict:
        """获取按标的聚合的交易所异动统计。"""
        payload = self._fetch_price_anomaly_page(
            "count",
            page_size,
            page_no,
            sortKey=sort_key,
            sortDir=sort_dir,
        )
        items = []
        for row in payload.get("data") or []:
            board = safe_int(row.get("s"))
            items.append({
                "code": str(row.get("c") or "").strip(),
                "name": str(row.get("n") or "").strip(),
                "market": _anomaly_market(row.get("c"), row.get("m"), board),
                "price": safe_float(row.get("p")),
                "change_pct": safe_float(row.get("a")),
                "times": safe_int(row.get("t")),
                "deviation": safe_float(row.get("x")),
                "days": safe_int(row.get("d")),
                "board": board,
            })
        return {
            "date": str(payload.get("date") or ""),
            "pages": safe_int(payload.get("pages")) or 0,
            "items": items,
        }
