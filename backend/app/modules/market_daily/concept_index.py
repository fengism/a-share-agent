"""概念等权指数合成。

概念没有官方指数（``index-kline`` 只认开盘红板块代码，同花顺概念代码取不到），
因此用本地成分股的**前复权**日线在 SQL 侧链式复利，合成一条等权概念指数：

    index_t = index_{t-1} × (1 + mean(r_i,t))

其中 ``r_i,t`` 是成分股 i 当日前复权收益率。设计要点：

* **必须复权**：``market_daily_bars`` 存的是不复权价且 ``pre_close/change_pct``
  全为 NULL，直接用收盘价链式计算会在分红送转日产生假暴跌。因此这里 join
  ``market_daily_adjustment_factors`` 用 ``close*qfq_multiplier + qfq_offset``。
* **在 SQL 里完成链式复利**：用 recursive CTE 只把最终指数点取回 Python，
  避免把几十万行中间结果搬进内存。
* **样本数逐日返回**：停牌、新股会让参与计算的成分股数量变化，前端需要看到覆盖率。
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.modules.market_daily.paths import MARKET_DAILY_DATABASE_PATH

logger = logging.getLogger(__name__)

#: 成分股数量上限。1170 个概念里有 1167 个不超过这个数，只有融资融券、深股通、
#: 沪股通这三个"普适属性"列表会超。SQL 成本随成分股数近似线性（1225 只 1 年
#: 约 0.55s），且结果按概念缓存 6 小时，因此上限主要用来兜住超大概念。
MAX_CONSTITUENTS = 1500


def sample_constituents(codes: list[str]) -> list[str]:
    """成分股超过上限时做等距抽样，而不是直接取前 N 个。

    ``codes`` 按股票代码升序，代码前缀天然按板块分段（000/002 深主板、300/301
    创业板、600/601 沪主板、688 科创板、8/9 北交所）。直接取前 N 会把高前缀的
    板块整体丢掉——实测"机器人概念"从 1225 只截到 800 只后，科创板 170 只与
    北交所 59 只全部消失，而这两类恰是机器人/人工智能概念的核心成分。
    等距抽样按比例保留各板块，且完全确定、可复现。
    """
    if len(codes) <= MAX_CONSTITUENTS:
        return codes
    # 注意不能写成 codes[::step][:MAX]——那样只覆盖列表前一段，
    # 代码高位段（科创板 688xxx、北交所 8xxxxx）会被整段丢掉。
    step = len(codes) / MAX_CONSTITUENTS
    sampled = [codes[int(index * step)] for index in range(MAX_CONSTITUENTS)]
    logger.info(
        "概念成分股 %d 只超过上限 %d，跨全序列等距抽样取 %d 只",
        len(codes),
        MAX_CONSTITUENTS,
        len(sampled),
    )
    return sampled


#: 合成指数基点，与常见宽基指数一致，便于前端直接显示"点位"。
INDEX_BASE = 1000.0

_DAILY_AGGREGATE_SQL_TEMPLATE = """
WITH adj AS (
  SELECT b.code AS c,
         b.trade_date AS d,
         b.close * f.qfq_multiplier + f.qfq_offset AS px,
         COALESCE(b.amount, 0) AS amt
  FROM market_daily_bars b
  JOIN market_daily_adjustment_factors f
    ON f.market = b.market AND f.code = b.code AND f.trade_date = b.trade_date
  WHERE b.market = 'cn'
    AND b.instrument_type = 'stock'
    AND b.code IN ({placeholders})
    AND b.trade_date >= ?
    AND b.close > 0
),
ret AS (
  SELECT c, d, amt, px,
         LAG(px) OVER (PARTITION BY c ORDER BY d) AS prev_px
  FROM adj
),
dr AS (
  -- 每只股票的首个观测没有前值，直接丢弃，避免把上市首日涨幅算成 0
  SELECT c, d, amt, (px / prev_px - 1.0) * 100.0 AS r
  FROM ret
  WHERE prev_px IS NOT NULL AND prev_px > 0
)
SELECT d,
       SUM(r) AS sum_ret,
       SUM(CASE WHEN r > 0 THEN 1 ELSE 0 END) AS up_n,
       SUM(CASE WHEN r < 0 THEN 1 ELSE 0 END) AS down_n,
       SUM(CASE WHEN r >= 9.8 THEN 1 ELSE 0 END) AS limit_up_n,
       SUM(CASE WHEN r <= -9.8 THEN 1 ELSE 0 END) AS limit_down_n,
       SUM(amt) AS amount,
       COUNT(*) AS sample_n
  FROM dr
 GROUP BY d
"""


@dataclass
class _DailyAggregate:
    """某个交易日的成分股聚合结果。

    只保留``sum_ret``/``sample_count``而不是直接存均值：两者可加，
    将来若要按成分股分片并行，各片结果直接相加即可与整段一次算完完全等价。
    """

    date: str
    sum_ret: float
    up_count: int
    down_count: int
    limit_up_count: int
    limit_down_count: int
    amount: float
    sample_count: int


#: 合成指数日内振幅的经验系数。用「成分股极值涨跌幅」推高低点会让一只涨停股
#: 把指数最高点推到 +21%，K 线全变长影线（实测 close=1000 而 high=1212）。
#: 等权平均会互相抵消绝大多数波动，这里取一个保守系数让形态可读。
INTRADAY_RANGE_FACTOR = 0.6


@dataclass(frozen=True)
class ConceptIndexPoint:
    """合成指数的单个交易日。"""

    date: str
    level: float
    avg_ret: float
    up_count: int
    down_count: int
    limit_up_count: int
    limit_down_count: int
    amount: float
    sample_count: int

    @property
    def prev_close(self) -> float:
        """当日开盘价 = 前一日收盘（链式复利反推）。"""
        return self.level / (1.0 + self.avg_ret / 100.0)

    @property
    def open(self) -> float:
        return self.prev_close

    @property
    def high(self) -> float:
        move = abs(self.avg_ret) * INTRADAY_RANGE_FACTOR
        return max(self.level, self.prev_close * (1.0 + move / 100.0))

    @property
    def low(self) -> float:
        move = abs(self.avg_ret) * INTRADAY_RANGE_FACTOR
        return min(self.level, self.prev_close * (1.0 - move / 100.0))


class ConceptIndexRepository:
    """每次操作建立短连接，与 :class:`MarketDailyBarRepository` 保持一致。

    这里刻意**不做按成分股分片并行**：实测 10 年区间单线程 4.2s、4 分片 3.6s
    （并行效率仅约 30%，SQLite 的窗口排序与各连接独立页缓存互相争抢），
    15% 的收益换不来线程池与合并逻辑的复杂度。
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        # 窗口函数 + recursive CTE 的中间结果较大，放内存避免反复落临时文件
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA busy_timeout=10000")
        return connection

    def load_index(self, codes: list[str], start_date: str) -> list[ConceptIndexPoint]:
        """用给定成分股合成等权指数；``codes`` 需已去重去后缀。"""
        if not codes:
            return []
        codes = sample_constituents(codes)
        placeholders = ",".join("?" * len(codes))
        sql = _DAILY_AGGREGATE_SQL_TEMPLATE.format(placeholders=placeholders)
        with self._connect() as connection:
            rows = connection.execute(sql, (*codes, start_date)).fetchall()
        daily = [
            _DailyAggregate(
                date=str(row["d"]),
                sum_ret=float(row["sum_ret"]),
                up_count=int(row["up_n"]),
                down_count=int(row["down_n"]),
                limit_up_count=int(row["limit_up_n"]),
                limit_down_count=int(row["limit_down_n"]),
                amount=float(row["amount"]),
                sample_count=int(row["sample_n"]),
            )
            for row in rows
        ]
        return _chain_levels(daily)


def _chain_levels(daily: list[_DailyAggregate]) -> list[ConceptIndexPoint]:
    """把逐日平均收益链式复利成指数点位（首日为 1000 基期）。

    链式复利放在 Python 里做只有零点几毫秒，比塞进 SQL 的 recursive CTE 更好读。
    """
    if not daily:
        return []
    points: list[ConceptIndexPoint] = []
    level = INDEX_BASE
    for index, row in enumerate(daily):
        avg_ret = row.sum_ret / row.sample_count if row.sample_count else 0.0
        if index > 0:
            level *= 1.0 + avg_ret / 100.0
        points.append(
            ConceptIndexPoint(
                date=row.date,
                level=level,
                avg_ret=avg_ret,
                up_count=row.up_count,
                down_count=row.down_count,
                limit_up_count=row.limit_up_count,
                limit_down_count=row.limit_down_count,
                amount=row.amount,
                sample_count=row.sample_count,
            )
        )
    return points


_concept_index_repository = ConceptIndexRepository(MARKET_DAILY_DATABASE_PATH)


def load_concept_index(codes: list[str], start_date: str) -> list[ConceptIndexPoint]:
    return _concept_index_repository.load_index(codes, start_date)
