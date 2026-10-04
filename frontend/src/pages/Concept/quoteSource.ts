/**
 * 识别后端的本地收盘兜底来源（`market_daily_close:YYYY-MM-DD`）。
 *
 * 命中说明该行展示的是**收盘价**而非实时价，需要在 UI 上明确区分，
 * 否则用户会把盘后收盘价误读成盘中最新价。
 *
 * 只接受严格格式，其他取值（包括 null 和无法识别的来源）一律视为"非收盘兜底"，
 * 以免把来源不明的价格说成收盘价。
 */
export function closeSourceDate(source: string | null | undefined): string | null {
  if (!source) return null;
  const matched = /^market_daily_close:(\d{4}-\d{2}-\d{2})$/.exec(source);
  return matched ? matched[1] : null;
}