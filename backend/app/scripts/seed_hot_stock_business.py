"""为热门股票抓取经营信息并写入个股资料库，作为起始种子数据。

热门股与"每日潜力股"候选池同一口径：剔除 ST/退市/次新/低成交后按成交额
降序取头部。对每只股票执行资料补充（THS 主营 + 东财公司概况；库中已有
主营则跳过，--force 强制重取），可选 --export 将结果固化为种子。

用法:
  uv run python -m app.scripts.seed_hot_stock_business [--top 50]
      [--codes 600519,000001] [--force] [--export] [--delay 1.0]
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from dataclasses import dataclass, field

from app.modules.potential.service import _select_candidates


async def collect_hot_codes(top: int, extra_codes: list[str] | None = None) -> list[str]:
    """热门股列表：潜力股候选池口径按成交额取头部，显式指定的代码追加去重。"""
    from app.financial_data.stock.public import get_exchange_stock_master, get_spot_snapshot

    snapshot_df, master = await asyncio.gather(
        get_spot_snapshot(),
        get_exchange_stock_master(),
    )
    candidates = _select_candidates(
        snapshot_df,
        master.records if master is not None else [],
    )
    codes = [str(candidate["code"]) for candidate in candidates[: max(0, top)]]
    for code in extra_codes or []:
        if code not in codes:
            codes.append(code)
    return codes


@dataclass
class EnrichOutcome:
    fetched: int = 0  # 本次联网抓取并更新
    skipped: int = 0  # 库中已有主营资料，跳过联网
    failed: int = 0
    failures: list[str] = field(default_factory=list)


def enrich_hot_stocks(
    codes: list[str],
    *,
    force: bool = False,
    delay: float = 1.0,
    enrich=None,
) -> EnrichOutcome:
    """逐只补充经营信息；单只失败不影响其余，股票间留出间隔避免触发上游风控。"""
    if enrich is None:
        from app.modules.stock_profile.service import enrich_stock_profile as enrich

    outcome = EnrichOutcome()
    for index, code in enumerate(codes):
        try:
            result = enrich(code, force=force)
        except Exception as exc:
            outcome.failed += 1
            outcome.failures.append(f"{code}: {exc}")
            continue
        if not result.success:
            outcome.failed += 1
            outcome.failures.append(f"{code}: {result.message}")
        elif result.updated_fields:
            outcome.fetched += 1
        else:
            outcome.skipped += 1
        if index < len(codes) - 1 and delay > 0:
            time.sleep(delay)
    return outcome


async def run(args: argparse.Namespace) -> int:
    extra_codes = [code.strip() for code in args.codes.split(",") if code.strip()] if args.codes else []
    codes = await collect_hot_codes(args.top, extra_codes=extra_codes)
    if not codes:
        print("错误: 未能获取热门股票列表（行情快照不可用？）", file=sys.stderr)
        return 1
    preview = ", ".join(codes[:10])
    print(f"热门股票 {len(codes)} 只: {preview}{' ...' if len(codes) > 10 else ''}")

    outcome = enrich_hot_stocks(codes, force=args.force, delay=args.delay)
    print(f"完成: 抓取更新 {outcome.fetched}，库中已有跳过 {outcome.skipped}，失败 {outcome.failed}")
    for failure in outcome.failures[:10]:
        print(f"  失败: {failure}")

    if args.export:
        from app.configuration.paths import SEEDS_DIR
        from app.infrastructure.persistence.connection import get_connection
        from app.infrastructure.persistence.seeds import export_seed_tables

        written = export_seed_tables(get_connection("industry"), SEEDS_DIR)
        print(f"种子已固化: {len(written)} 个文件 -> {SEEDS_DIR}")
        print("下一步: make backend-seeds-drift 核对差异后提交")

    return 0 if outcome.failed == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="为热门股票抓取经营信息（起始种子数据）")
    parser.add_argument("--top", type=int, default=50, help="按成交额取前 N 只热门股（默认 50）")
    parser.add_argument("--codes", default="", help="显式指定股票代码（逗号分隔），追加到热门列表")
    parser.add_argument("--force", action="store_true", help="库中已有主营资料也强制重新抓取")
    parser.add_argument("--export", action="store_true", help="完成后将库状态固化为种子")
    parser.add_argument("--delay", type=float, default=1.0, help="股票间抓取间隔秒数（默认 1.0）")
    args = parser.parse_args()

    exit_code = asyncio.run(run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
