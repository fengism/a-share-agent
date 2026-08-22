"""金融数据日期参数解析。"""

from datetime import date, datetime


def parse_market_date(value: str, field_name: str) -> date:
    """解析紧凑格式或 ISO 格式的行情日期。"""
    for date_format in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, date_format).date()
        except ValueError:
            continue
    raise ValueError(f"{field_name} 日期格式无效: {value}，支持 YYYYMMDD 或 YYYY-MM-DD")
