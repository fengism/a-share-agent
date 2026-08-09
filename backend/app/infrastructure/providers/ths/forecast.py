"""同花顺机构预测能力。"""

import pandas as pd
from bs4 import BeautifulSoup

from app.infrastructure.providers.ths.transport import ThsTransport


def fetch_stock_forecast_reports(
    transport: ThsTransport,
    code: str,
) -> pd.DataFrame:
    response = transport.request(
        "GET",
        f"https://basic.10jqka.com.cn/new/{code}/worth.html",
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Referer": "https://basic.10jqka.com.cn/",
        },
        timeout=15,
    )
    response.encoding = "gbk"
    soup = BeautifulSoup(response.text, "html.parser")
    reports = []
    all_columns = None
    for table in soup.select("table.m_table.m_hl"):
        caption = table.select_one("caption.hltip.m_cap")
        if not caption:
            continue
        unit_element = caption.select_one("span.fr.tip")
        unit = unit_element.get_text(strip=True) if unit_element else ""
        title = caption.get_text().strip().replace(unit, "").strip()
        if "年报每股收益" in title:
            table_name = "EPS"
        elif "年报净利润" in title:
            table_name = "NET_PROFIT"
        else:
            continue
        table_head = table.select_one("thead")
        columns = (
            [cell.get_text(strip=True) for cell in table_head.select("th")]
            if table_head and table_head.select("th")
            else []
        )
        if not {"年度", "预测机构数", "均值"}.issubset(columns):
            continue
        table_body = table.select_one("tbody")
        if not table_body:
            continue
        for row in table_body.select("tr"):
            year_cell = row.select_one("th")
            if not year_cell:
                continue
            values = [table_name, year_cell.get_text(strip=True)]
            values.extend(cell.get_text(strip=True) for cell in row.select("td"))
            values.append(unit)
            reports.append(values)
        if all_columns is None:
            all_columns = ["指标", *columns, "单位"]
    if not reports or all_columns is None:
        return pd.DataFrame()
    frame = pd.DataFrame(reports, columns=all_columns)
    for column in all_columns:
        if column in ("指标", "年度", "单位"):
            continue
        cleaned = frame[column].astype(str).str.extract(
            r"([-+]?\d+(?:\.\d+)?)",
            expand=False,
        )
        frame[column] = pd.to_numeric(cleaned, errors="coerce")
    return frame
