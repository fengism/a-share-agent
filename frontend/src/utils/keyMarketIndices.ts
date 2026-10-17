/**
 * 核心宽基指数。
 *
 * 这份名单此前在两个地方各写一遍，且写法不一致：
 * - `pages/Market/AIndexTab.tsx`：`["000001", "399001", ...]`（指数页可切换的指数）
 * - `components/HeaderMarketTicker.tsx`：混入 `sh000001` / `sz399001` 前缀形式做容错匹配
 *
 * 后端 `app/constants/market.py::INDEX_FALLBACKS` 维护着同一批指数（且
 * `normalize_indices()` 会按它的顺序过滤并归一 `/market/indices` 的返回），因此这份
 * 名单必须与后端保持一致——`backend/tests/test_key_market_index_contract.py` 会在 CI 中校验。
 */

export interface KeyMarketIndex {
  /** 6 位裸代码，与后端 `/market/indices` 归一后的 code 口径一致 */
  code: string;
  /** 中文简称，用于按名称兜底匹配（部分数据源不返回可用的代码） */
  name: string;
  /** 其它可能出现过的代码写法（带交易所前缀），仅用于容错匹配 */
  codeAliases?: readonly string[];
  /** 是否出现在顶部行情条 */
  inHeaderTicker: boolean;
}

export const KEY_MARKET_INDICES = [
  { code: "000001", name: "上证指数", codeAliases: ["sh000001"], inHeaderTicker: true },
  { code: "399001", name: "深证成指", codeAliases: ["sz399001"], inHeaderTicker: true },
  { code: "399006", name: "创业板指", codeAliases: ["sz399006"], inHeaderTicker: true },
  { code: "000688", name: "科创50", inHeaderTicker: false },
  { code: "000300", name: "沪深300", inHeaderTicker: false },
  { code: "000905", name: "中证500", inHeaderTicker: false },
] as const satisfies readonly KeyMarketIndex[];

export type KeyMarketIndexCode = (typeof KEY_MARKET_INDICES)[number]["code"];

/** 指数页可切换/展示的指数代码，顺序即展示顺序（与后端归一顺序一致）。 */
export const KEY_MARKET_INDEX_CODES: readonly KeyMarketIndexCode[] = KEY_MARKET_INDICES.map(
  (item) => item.code,
);

const HEADER_TICKER_INDICES = KEY_MARKET_INDICES.filter((item) => item.inHeaderTicker);

/** 顶部行情条展示的指数数量（列表里标记了 `inHeaderTicker` 的个数）。 */
export const HEADER_TICKER_INDEX_COUNT = HEADER_TICKER_INDICES.length;

/**
 * 判断某条指数数据是否属于顶部行情条展示集合。
 *
 * 兼容三种情况：裸代码（`000001`）、带交易所前缀的代码（`sh000001`）、中文简称。
 * 后端已按 `INDEX_FALLBACKS` 归一，这里的前缀与名称匹配是应对数据源口径变化的历史容错。
 */
export function isHeaderTickerIndex(index: {
  code?: string | null;
  name?: string | null;
}): boolean {
  const code = index.code ?? "";
  const name = index.name ?? "";
  return HEADER_TICKER_INDICES.some((item) => {
    const candidates: readonly string[] = [item.code, ...(item.codeAliases ?? [])];
    const matchesCode = code !== "" && candidates.some((candidate) => code.includes(candidate));
    const matchesName = name !== "" && name.includes(item.name);
    return matchesCode || matchesName;
  });
}
