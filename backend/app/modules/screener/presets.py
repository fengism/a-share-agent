"""经典选股与题材挖掘预设模版定义。"""

from app.modules.screener.schemas import ScreenerFilter, ScreenerPreset

SCREENER_PRESETS: list[ScreenerPreset] = [
    ScreenerPreset(
        key="deep_broken_net",
        name="深度破净与资产重估",
        category="value",
        description="市净率 PB <= 1.0 的破净标的，剔除 ST 及微盘流动性不足个股，专注安全边际与重置价值修复。",
        filters=ScreenerFilter(
            is_broken_net=True,
            exclude_st=True,
            market_cap_min=30.0,
            min_amount_yi=0.5,
            sort_by="pb",
            sort_order="asc",
            page_size=50,
        ),
    ),
    ScreenerPreset(
        key="theme_volume_expansion",
        name="题材启动·放量突破",
        category="theme",
        description="日内换手 3%~15%、振幅 4%~15% 且适度收红的活跃题材标的，捕捉资金抢筹与风向扩散拐点。",
        filters=ScreenerFilter(
            change_pct_min=1.5,
            change_pct_max=8.5,
            turnover_pct_min=3.0,
            turnover_pct_max=16.0,
            amplitude_min=4.0,
            amplitude_max=15.0,
            exclude_st=True,
            min_amount_yi=1.0,
            sort_by="turnover_pct",
            sort_order="desc",
            page_size=50,
        ),
    ),
    ScreenerPreset(
        key="low_pe_growth_cross",
        name="低估值蓝筹白马 (老树发新芽)",
        category="value",
        description="动态 PE < 25、PB < 3.0 的百亿市值中大盘标的，防范估值陷阱，兼具基本面护城河与估值安全垫。",
        filters=ScreenerFilter(
            pe_min=1.0,
            pe_max=25.0,
            pb_min=0.3,
            pb_max=3.0,
            market_cap_min=100.0,
            exclude_st=True,
            min_amount_yi=1.0,
            sort_by="market_cap",
            sort_order="desc",
            page_size=50,
        ),
    ),
    ScreenerPreset(
        key="active_growth_rebound",
        name="中小盘活跃弹性反转",
        category="growth",
        description="市值 30~200 亿、换手活跃且波动弹性充分的中小盘成长股，适合挖掘细分赛道弹性隐形冠军。",
        filters=ScreenerFilter(
            market_cap_min=30.0,
            market_cap_max=200.0,
            turnover_pct_min=4.0,
            turnover_pct_max=20.0,
            amplitude_min=5.0,
            exclude_st=True,
            min_amount_yi=0.8,
            sort_by="turnover_pct",
            sort_order="desc",
            page_size=50,
        ),
    ),
    ScreenerPreset(
        key="high_dividend_defense",
        name="红利防守·深度破净高安全垫",
        category="value",
        description="市净率 PB <= 1.2 且 PE 3~15 的中大盘优质标的，抗跌防守属性强，具备较高的股息率与重置价值支撑。",
        filters=ScreenerFilter(
            pe_min=3.0,
            pe_max=15.0,
            pb_min=0.3,
            pb_max=1.2,
            market_cap_min=80.0,
            exclude_st=True,
            min_amount_yi=1.0,
            sort_by="pb",
            sort_order="asc",
            page_size=50,
        ),
    ),
    ScreenerPreset(
        key="ultra_oversold_pulse",
        name="超跌低位异动·题材试盘",
        category="theme",
        description="低估值中低位个股中出现量价脉冲异动（振幅≥4%、换手≥3%），常见于主力试盘或热点题材发酵初期的弹性标的。",
        filters=ScreenerFilter(
            pb_min=0.3,
            pb_max=2.5,
            turnover_pct_min=3.0,
            turnover_pct_max=15.0,
            amplitude_min=4.0,
            amplitude_max=16.0,
            market_cap_min=25.0,
            exclude_st=True,
            min_amount_yi=0.8,
            sort_by="amplitude",
            sort_order="desc",
            page_size=50,
        ),
    ),
]


def list_screener_presets() -> list[ScreenerPreset]:
    """返回所有开箱即用的经典题材与低估值选股预设模版。"""
    return SCREENER_PRESETS
