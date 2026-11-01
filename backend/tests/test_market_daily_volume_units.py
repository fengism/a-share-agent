"""每日 K 线入库与读取的成交量量纲兼容性与自适应防线测试。

验证每日K线入库（collectors.py、backfill.py）及本地读取（reader.py）
在面对不同上游源的成交量量纲波动（手 vs 股）时，能够自动识别并统一对齐为【股】（Shares），
杜绝 100 倍脏数据入库或向下游回放。
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, patch

import pandas as pd
import pytest

from app.domain.market import IndexItem, KlineData, KlineItem, MarketIndices
from app.financial_data.stock.quotes.historical import HistoricalBarSet
from app.modules.market_daily.backfill import _records_from_history
from app.modules.market_daily.collectors import (
    fetch_cn_indices,
    normalize_cn_stocks,
    normalize_indices,
)
from app.modules.market_daily.models import MarketDailyBar
from app.modules.market_daily.reader import _to_kline_item


_TRADE_DATE = date(2026, 10, 30)


def test_normalize_cn_stocks_adapts_shares_source():
    """上游返回标准「股」（如新浪全市场快照）时，入库保持为股。"""
    # 贵州茅台：股价 1500，成交量 2,000,000 股，成交额 3,000,000,000 元 (均价 1500)
    df = pd.DataFrame([{
        "代码": "600519",
        "名称": "贵州茅台",
        "最新价": 1500.0,
        "昨收": 1490.0,
        "今开": 1495.0,
        "最高": 1510.0,
        "最低": 1490.0,
        "成交量": 2000000.0,  # 股
        "成交额": 3000000000.0,
    }])
    records = normalize_cn_stocks(df, _TRADE_DATE, "test_source")
    assert len(records) == 1
    assert records[0].volume == 2000000.0
    assert records[0].amount == 3000000000.0


def test_normalize_cn_stocks_adapts_lots_source():
    """上游返回「手」（如某些第三方快照接口）时，自适应识别并自动乘以 100 转换为股。"""
    # 贵州茅台：股价 1500，成交量 20,000 手，成交额 3,000,000,000 元 (implied price = 3e9 / 2e4 = 150000 -> 100倍)
    df = pd.DataFrame([{
        "代码": "600519",
        "名称": "贵州茅台",
        "最新价": 1500.0,
        "昨收": 1490.0,
        "今开": 1495.0,
        "最高": 1510.0,
        "最低": 1490.0,
        "成交量": 20000.0,  # 手
        "成交额": 3000000000.0,
    }])
    records = normalize_cn_stocks(df, _TRADE_DATE, "test_source")
    assert len(records) == 1
    # 必须自适应识别为手并自动转换为股入库，防止少 100 倍
    assert records[0].volume == 2000000.0
    assert records[0].amount == 3000000000.0


def test_normalize_indices_adapts_market_indices_lots_to_shares():
    """从大盘概览 MarketIndices（规范化为手）入库时，自动转换为标准股。"""
    # 上证指数：指数 3600，成交额 7642 亿，MarketIndices 里的 volume 规范为 4.97 亿手
    indices = MarketIndices(
        source="test_indices",
        indices=[
            IndexItem(
                code="000001",
                name="上证指数",
                price=3600.0,
                open=3605.0,
                high=3660.0,
                low=3595.0,
                pre_close=3651.0,
                volume=497973940.0,  # 4.97 亿手
                amount=764227190900.0,  # 7642 亿元
            )
        ],
    )
    records = normalize_indices(indices, market="cn", trade_date=_TRADE_DATE)
    assert len(records) == 1
    # 均价 7642亿 / 4.97亿手 ≈ 1537 元/手 -> 自动判定为手并乘 100 得到 497.9 亿股
    assert records[0].volume == 49797394000.0


@pytest.mark.asyncio
async def test_fetch_cn_indices_adapts_index_kline_volume():
    """从指数日K线采集入库时，自适应对齐为股。"""
    mock_kline_data = KlineData(
        code="000001",
        period="daily",
        adjust="",
        source="mock",
        items=[
            KlineItem(
                code="000001",
                date=_TRADE_DATE.isoformat(),
                open=3605.0,
                close=3600.0,
                high=3660.0,
                low=3595.0,
                pre_close=3650.0,
                volume=497973940.0,  # 假设某上游以手返回
                amount=764227190900.0,
            )
        ],
    )

    with patch("app.modules.market_daily.collectors._verify_cn_trade_date", new=AsyncMock()), \
         patch("app.financial_data.market.quotes.index_kline._load_index_kline", new=AsyncMock(return_value=mock_kline_data)):
        collected = await fetch_cn_indices(_TRADE_DATE)
        assert len(collected.records) == 7
        sh_index = next(r for r in collected.records if r.code == "000001")
        # 自动转为 497 亿股
        assert sh_index.volume == 49797394000.0


def test_records_from_history_adapts_backfill_volume():
    """历史回填任务将 HistoricalBarSet 转换为 MarketDailyBarRecord 时，自适应对齐为股。"""
    # 模拟历史回填候选集若是「手」
    history_lots = HistoricalBarSet(
        code="000001",
        period="daily",
        adjust="none",
        source="mock_tdx",
        adjustment_verified=True,
        data_hash="test",
        items=[
            KlineItem(
                code="000001",
                date=_TRADE_DATE.isoformat(),
                open=10.0,
                close=10.5,
                high=11.0,
                low=9.8,
                pre_close=10.0,
                volume=1000.0,  # 1000 手
                amount=1030000.0,  # 103 万元 (均价约 10.3 元/股 -> 1030 元/手)
            )
        ],
    )
    records = _records_from_history("000001", "平安银行", history_lots)
    assert len(records) == 1
    # 1000 手必须转为 100,000 股
    assert records[0].volume == 100000.0


def test_reader_to_kline_item_adapts_safely():
    """reader 模块从本地 SQLite 读出 MarketDailyBar 转化为 KlineItem 时，确保量纲为股。"""
    from datetime import datetime, UTC
    now = datetime.now(UTC)
    # 正常入库的股
    bar_normal = MarketDailyBar(
        market="cn",
        instrument_type="stock",
        code="000001",
        name="平安银行",
        trade_date=_TRADE_DATE,
        currency="CNY",
        close=10.0,
        volume=100000.0,  # 10万股
        amount=1000000.0,  # 100万元
        source="test",
        verification_status="confirmed",
        revision=1,
        first_refreshed_at=now,
        last_refreshed_at=now,
    )
    item_normal = _to_kline_item(bar_normal)
    assert item_normal.volume == 100000.0

    # 假设数据库存在历史异常脏数据（如误存为手）
    bar_lots_dirty = MarketDailyBar(
        market="cn",
        instrument_type="stock",
        code="000001",
        name="平安银行",
        trade_date=_TRADE_DATE,
        currency="CNY",
        close=10.0,
        volume=1000.0,  # 1000手
        amount=1000000.0,  # 100万元
        source="test",
        verification_status="confirmed",
        revision=1,
        first_refreshed_at=now,
        last_refreshed_at=now,
    )
    item_repaired = _to_kline_item(bar_lots_dirty)
    # reader 端自动自愈为 10万股，杜绝下游分时/K线图渲染塌陷 100 倍
    assert item_repaired.volume == 100000.0
