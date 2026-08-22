"""东方财富证券代码格式适配。"""

from app.core.market import normalize_code


def build_stock_secid(code: str) -> str:
    """构造东方财富股票 secid，沪市为 1，其余支持市场为 0。"""
    symbol = normalize_code(code)
    market_code = 1 if symbol.exchange == "SH" else 0
    return f"{market_code}.{symbol.raw}"
