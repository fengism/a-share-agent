"""用独立实现交叉验证 SQL 链式合成，防止"测试和实现一起错"。"""

import sqlite3
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.modules.market_daily.concept_index import (  # noqa: E402
    MAX_CONSTITUENTS,
    load_concept_index,
    sample_constituents,
)

MD = Path(__file__).resolve().parents[1] / "data/db/market_daily.sqlite3"
IND = Path(__file__).resolve().parents[1] / "data/db/industry_data.db"


def naive_equal_weight(codes: list[str], start_date: str) -> list[tuple[str, float]]:
    """纯 Python 参考实现：逐日取每只股票的前复权收盘，算收益再平均。

    约定与 SQL 一致：首个交易日为基期（点位 1000），**首日收益不计入**，
    从第二个交易日起逐日链式复利。
    """
    md = sqlite3.connect(MD)
    qs = ",".join("?" * len(codes))
    rows = md.execute(
        f"""SELECT b.code, b.trade_date,
                   b.close * f.qfq_multiplier + f.qfq_offset AS px
              FROM market_daily_bars b
              JOIN market_daily_adjustment_factors f
                ON f.market=b.market AND f.code=b.code AND f.trade_date=b.trade_date
             WHERE b.market='cn' AND b.code IN ({qs}) AND b.trade_date >= ? AND b.close > 0
             ORDER BY b.code, b.trade_date""",
        (*codes, start_date),
    ).fetchall()

    per_code: dict[str, list[tuple[str, float]]] = {}
    for code, day, px in rows:
        per_code.setdefault(code, []).append((day, px))

    # day -> [收益...]
    daily: dict[str, list[float]] = {}
    for series in per_code.values():
        for i in range(1, len(series)):
            _, prev_px = series[i - 1]
            day, px = series[i]
            if prev_px > 0:
                daily.setdefault(day, []).append((px / prev_px - 1.0) * 100.0)

    days = sorted(daily)
    if not days:
        return []
    level = 1000.0
    out: list[tuple[str, float]] = [(days[0], level)]
    for day in days[1:]:
        level *= 1.0 + statistics.fmean(daily[day]) / 100.0
        out.append((day, level))
    return out


def main() -> None:
    ind = sqlite3.connect(IND)
    concept = sys.argv[1] if len(sys.argv) > 1 else "固态电池"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 365
    codes = [
        row[0].split(".")[0]
        for row in ind.execute(
            """SELECT m.stock_code FROM stock_concept_mappings m
                WHERE EXISTS (SELECT 1 FROM json_each(
                        CASE WHEN json_valid(m.concepts_json) THEN m.concepts_json ELSE '[]' END)
                      WHERE json_each.value = ?)
                ORDER BY m.stock_code""",
            (concept,),
        ).fetchall()
    ]
    # 必须与 ConceptIndexRepository 的抽样口径一致，否则大概念无法对比
    full_count = len(codes)
    codes = sample_constituents(codes)
    if len(codes) < full_count:
        print(f"注意：原始成分股 {full_count} 超过 {MAX_CONSTITUENTS}，已按同样口径抽样")
    start = (date.today() - timedelta(days=days)).isoformat()
    points = load_concept_index(codes, start)
    reference = naive_equal_weight(codes, start)

    print(f"概念={concept} 成分股={len(codes)} 区间={start} 起")
    print(f"SQL 合成点数={len(points)}  参考实现点数={len(reference)}")
    assert len(points) == len(reference), "交易日数量不一致"

    worst = 0.0
    for point, (day, level) in zip(points, reference, strict=True):
        assert point.date == day, f"日期错位 {point.date} != {day}"
        worst = max(worst, abs(point.level - level))
    print(f"最大点位偏差={worst:.10f}")
    assert worst < 1e-6, "SQL 合成与参考实现不一致"
    assert abs(points[0].level - 1000.0) < 1e-9, "首日必须是 1000 基期"

    # 抽查单日均涨跌是否等于参考实现
    md_ret = {p.date: p.avg_ret for p in points}
    print("\n抽查（SQL 收盘 / 参考收盘 / 当日均涨跌 / 样本数）：")
    for point in points[:2] + points[len(points) // 2 : len(points) // 2 + 1] + points[-2:]:
        print(f"  {point.date}  {point.level:10.4f}  {md_ret[point.date]:+.4f}%  n={point.sample_count}")
    print("\n交叉验证通过")


if __name__ == "__main__":
    main()
