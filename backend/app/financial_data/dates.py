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


MAX_KLINE_HISTORY_YEARS = 10


def clamp_kline_history_start_date(
    parsed_start_date: date,
    parsed_end_date: date,
    *,
    max_years: int = MAX_KLINE_HISTORY_YEARS,
) -> date:
    """把起始日期收敛到 [结束日期 - max_years 年, 结束日期]。"""
    try:
        earliest = parsed_end_date.replace(year=parsed_end_date.year - max_years)
    except ValueError:
        earliest = parsed_end_date.replace(
            year=parsed_end_date.year - max_years, day=28
        )
    return max(parsed_start_date, earliest)

