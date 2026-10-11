"""新浪全市场行情快照字段单位测试。"""

import pytest

from app.infrastructure.providers.sina.provider import SinaDataProvider


def test_sina_spot_snapshot_keeps_volume_in_shares() -> None:
    """getHQNodeData 的 volume 已是股数，不应再次乘以 100。"""
    provider = SinaDataProvider()
    frame = provider._records_to_snapshot_df(
        [
            {
                "code": "600519",
                "name": "贵州茅台",
                "trade": "1258.62",
                "volume": "3833098",
                "amount": "4797246636",
                "mktcap": "157337770.46506",
                "nmc": "157337770.46506",
            }
        ]
    )

    row = frame.iloc[0]
    assert row["成交量"] == pytest.approx(3_833_098)
    assert row["成交额"] == "4797246636"
    # 成交额 / (成交量 × 价格) 应接近 1；若成交量被错误放大 100 倍则约为 0.01。
    assert float(row["成交额"]) / (float(row["成交量"]) * float(row["最新价"])) == pytest.approx(1, rel=0.02)
