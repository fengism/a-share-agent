"""策略精选清单（产品口径，单一事实来源）。

「哪些内置策略进入选股扫描、哪些参与潜力股加权评分」属于产品口径，不是策略本身的
信号逻辑，因此不写进 YAML DSL（``quant.strategy/v1`` 是面向策略作者的契约，且已是对外
稳定接口）。

收敛前的状态是同一批 7 个 key 在两个地方各写了一遍，带来三个真实问题：

1. 新增 YAML 策略后，选股页不会列出它、潜力股评分也不会用到它——必须记得再改两处
   Python 名单；
2. 在 YAML 里把某策略改成 ``enabled: false``，选股页仍会列出它（列表只按本地名单
   过滤），用户点进去才在 ``registry.resolve`` 抛「不支持的选股策略」；
3. ``dict.get(key, 1.0)`` 让名单漂移静默发生——权重悄悄退回默认值，不报错也不告警。

现在 key 清单只此一份，权重只登记「偏离默认值」的部分，并由
``tests/test_strategy_curation.py`` 守着「清单里的每个 key 都能在 YAML 定义里找到且已启用」。
"""

from __future__ import annotations

#: 精选策略清单，顺序即前端展示顺序。
CURATED_STRATEGIES: tuple[str, ...] = (
    "bull_trend",
    "ma_golden_cross",
    "volume_breakout",
    "shrink_pullback",
    "bottom_volume",
    "one_yang_three_yin",
    "box_oscillation",
)

#: 精选策略集合（选股页可选范围）。
CURATED_STRATEGY_KEYS: frozenset[str] = frozenset(CURATED_STRATEGIES)

#: 潜力股评分中「未单独标定」的策略权重。
DEFAULT_MINING_WEIGHT = 1.0

#: 潜力股评分权重：只登记偏离 :data:`DEFAULT_MINING_WEIGHT` 的策略。
#: 形态/底部类罕见信号更稀缺，所以权重更高。
MINING_WEIGHTS: dict[str, float] = {
    "ma_golden_cross": 1.2,
    "volume_breakout": 1.2,
    "bottom_volume": 1.5,
    "one_yang_three_yin": 1.5,
}


def mining_weight(key: str) -> float:
    """返回策略的潜力股评分权重。

    未在 :data:`MINING_WEIGHTS` 中单独标定的精选策略按 :data:`DEFAULT_MINING_WEIGHT` 计。

    Param:
        key: 策略 key
    Return:
        该策略的评分权重
    """
    return MINING_WEIGHTS.get(key, DEFAULT_MINING_WEIGHT)
