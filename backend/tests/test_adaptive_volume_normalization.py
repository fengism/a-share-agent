"""自适应成交量量纲归一化测试（手 vs 股自适应推导与防 100 倍偏差）。"""

import pandas as pd
import pytest

from app.financial_data.market.quotes.normalization import (
    VolumeUnit,
    build_indices_from_sina,
    resolve_adaptive_volume,
)
from app.infrastructure.providers.tencent import TencentDataProvider


class TestAdaptiveVolumeResolution:
    """测试 resolve_adaptive_volume 核心函数的自适应探测与转换。"""

    def test_stock_normal_lots_to_lots(self):
        """普通股票以「手」输入，目标为「手」，应保持手。"""
        # 茅台现价 1400，成交量 50000 手，成交额 70 亿元 (70亿 / 5万手 = 14万元/手 = 1400元/股 x 100)
        vol = resolve_adaptive_volume(
            raw_volume=50000.0,
            amount=7_000_000_000.0,
            price=1400.0,
            target_unit=VolumeUnit.LOTS,
            is_index=False,
            symbol="600519",
        )
        assert vol == 50000.0

    def test_stock_shares_to_lots_adapts(self):
        """科创板股票以「股」输入，目标为「手」，应自适应除以 100。"""
        # 中芯国际现价 100，成交量 30,000,000 股，成交额 30 亿元 (30亿 / 3000万股 = 100元/股)
        vol = resolve_adaptive_volume(
            raw_volume=30_000_000.0,
            amount=3_000_000_000.0,
            price=100.0,
            target_unit=VolumeUnit.LOTS,
            is_index=False,
            symbol="688981",
        )
        assert vol == pytest.approx(300_000.0)  # 30万手

    def test_stock_shares_to_shares_adapts(self):
        """日K线以「股」输入，目标为「股」，应保持不变，不被误乘 100。"""
        vol = resolve_adaptive_volume(
            raw_volume=5_992_729.0,
            amount=8_257_382_000.0,
            price=1392.05,
            target_unit=VolumeUnit.SHARES,
            is_index=False,
            symbol="600519",
        )
        assert vol == pytest.approx(5_992_729.0)

    def test_stock_lots_to_shares_adapts(self):
        """若底层日K线以「手」输入，目标为「股」，应自适应乘以 100。"""
        vol = resolve_adaptive_volume(
            raw_volume=59_927.0,
            amount=8_257_382_000.0,
            price=1392.05,
            target_unit=VolumeUnit.SHARES,
            is_index=False,
            symbol="600519",
        )
        assert vol == pytest.approx(5_992_700.0)

    def test_index_shanghai_lots_stays_lots(self):
        """新浪沪市指数原始输入为「手」，目标为「手」，应保留手，不再被除以 100。"""
        # 上证指数成交量约 4.98 亿手，成交额 7642 亿元 (均价约 1534 元/手)
        vol = resolve_adaptive_volume(
            raw_volume=497_973_940.0,
            amount=764_227_190_865.0,
            price=3599.02,
            target_unit=VolumeUnit.LOTS,
            is_index=True,
            symbol="sh000001",
        )
        assert vol == 497_973_940.0

    def test_index_shenzhen_shares_converts_to_lots(self):
        """新浪深市指数原始输入为「股」，目标为「手」，应自适应除以 100。"""
        # 深证成指成交量约 608 亿股，成交额 9102 亿元 (均价约 14.96 元/股)
        vol = resolve_adaptive_volume(
            raw_volume=60_828_913_431.0,
            amount=910_236_192_243.0,
            price=11000.0,
            target_unit=VolumeUnit.LOTS,
            is_index=True,
            symbol="sz399001",
        )
        assert vol == pytest.approx(608_289_134.31)

    def test_missing_amount_falls_back_gracefully(self):
        """缺少成交额与价格时，退化到基于代码前缀的稳健规则兜底。"""
        # 沪市指数兜底为手 -> 保持手
        vol_sh = resolve_adaptive_volume(
            raw_volume=1000.0,
            target_unit=VolumeUnit.LOTS,
            is_index=True,
            symbol="sh000001",
        )
        assert vol_sh == 1000.0

        # 深市指数兜底为股 -> 除以 100 变手
        vol_sz = resolve_adaptive_volume(
            raw_volume=100000.0,
            target_unit=VolumeUnit.LOTS,
            is_index=True,
            symbol="sz399001",
        )
        assert vol_sz == 1000.0


class TestSinaMarketIndicesNormalization:
    """测试新浪指数行情 DataFrame 解析的量纲一致性。"""

    def test_build_indices_from_sina_aligns_sh_and_sz(self):
        df = pd.DataFrame([
            {
                "代码": "sh000001",
                "名称": "上证指数",
                "最新价": 3599.02,
                "涨跌幅": 0.5,
                "成交量": 497_973_940.0,  # 新浪沪市原始是手
                "成交额": 764_227_190_865.0,
                "今开": 3580.0, "最高": 3610.0, "最低": 3570.0, "振幅": 1.1, "昨收": 3581.0,
            },
            {
                "代码": "sz399001",
                "名称": "深证成指",
                "最新价": 11000.0,
                "涨跌幅": 0.8,
                "成交量": 60_828_913_431.0,  # 新浪深市原始是股
                "成交额": 910_236_192_243.0,
                "今开": 10900.0, "最高": 11050.0, "最低": 10880.0, "振幅": 1.5, "昨收": 10912.0,
            },
        ])
        result = build_indices_from_sina(df)
        items_map = {item.code: item for item in result.indices}

        sh = items_map["000001"]
        sz = items_map["399001"]

        # 上证指数成交量应约为 4.98 亿手（不缩水到 497 万手）
        assert sh.volume == pytest.approx(497_973_940.0)
        # 深证成指成交量应约为 6.08 亿手（与上证指数在同一手量级）
        assert sz.volume == pytest.approx(608_289_134.31)
        # 沪深两市指数成交量比例约为 0.82，在合理范围内，不存在 100 倍偏差
        ratio = sh.volume / sz.volume
        assert 0.5 <= ratio <= 1.5


class TestTencentQuoteNormalization:
    """测试腾讯实时行情快照中科创板与普通股票的量纲对齐。"""

    def test_parse_stock_quote_line_aligns_star_market(self):
        # 模拟腾讯原始行情行：普通股（手）
        line_main = (
            'v_sh600519="1~贵州茅台~600519~1392.05~1390.00~1391.00~59927~'
            + '~' * 23
            + '20261030150000~2.05~0.15~1400.00~1385.00~~825738.2~'
            + '~' * 15
            + '"'
        )
        quote_main = TencentDataProvider._parse_stock_quote_line(line_main)
        # 茅台成交量应为 59927 手
        assert quote_main["volume"] == pytest.approx(59927.0)

        # 模拟腾讯原始行情行：科创板 688981（股）
        # vals[6] 为 29998989 股，vals[37] 为 295750 万元
        line_star = (
            'v_sh688981="1~中芯国际~688981~96.79~96.00~96.50~29998989~'
            + '~' * 23
            + '20261030150000~0.79~0.82~98.00~95.00~~295750.0~'
            + '~' * 15
            + '"'
        )
        quote_star = TencentDataProvider._parse_stock_quote_line(line_star)
        # 科创板成交量应自适应转换为手（约 299,989.89 手），不再是 2999 万！
        assert quote_star["volume"] == pytest.approx(299_989.89)
