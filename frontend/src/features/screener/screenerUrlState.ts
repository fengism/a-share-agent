import type { ScreenerFilter } from "../../types/stock";

export const DEFAULT_SCREENER_FILTERS: ScreenerFilter = {
  sort_by: "market_cap",
  sort_order: "desc",
  page: 1,
  page_size: 50,
};

export interface ScreenerUrlState {
  filters: ScreenerFilter;
  showPercentile: boolean;
  pePercentileMax: number;
  pbPercentileMax: number;
}

const NUMBER_FILTER_KEYS = [
  "pe_min",
  "pe_max",
  "pb_min",
  "pb_max",
  "price_min",
  "price_max",
  "market_cap_min",
  "market_cap_max",
  "change_pct_min",
  "change_pct_max",
  "turnover_pct_min",
  "turnover_pct_max",
  "amplitude_min",
  "amplitude_max",
  "min_amount_yi",
  "min_listing_days",
] as const;

const SORT_FIELDS: ReadonlySet<string> = new Set([
  "market_cap",
  "pe",
  "pb",
  "price",
  "change_pct",
  "turnover_pct",
  "amplitude",
  "volume",
]);

function parseNumber(value: string | null): number | undefined {
  if (value === null || value === "") return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parsePositiveInteger(value: string | null, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function parsePercentile(value: string | null, fallback: number): number {
  if (value === null || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.min(100, Math.max(0, parsed)) : fallback;
}

export function parseScreenerUrlState(params: URLSearchParams): ScreenerUrlState {
  const filters: ScreenerFilter = { ...DEFAULT_SCREENER_FILTERS };
  for (const key of NUMBER_FILTER_KEYS) {
    const value = parseNumber(params.get(key));
    if (value !== undefined) filters[key] = value;
  }

  const industries = params.get("industries")
    ?.split(",")
    .map((industry) => industry.trim())
    .filter(Boolean);
  if (industries?.length) filters.industries = Array.from(new Set(industries));

  const concepts = params.get("concepts")
    ?.split(",")
    .map((concept) => concept.trim())
    .filter(Boolean);
  if (concepts?.length) filters.concepts = Array.from(new Set(concepts));

  const markets = params.get("markets")
    ?.split(",")
    .map((market) => market.trim())
    .filter(Boolean);
  if (markets?.length) filters.markets = Array.from(new Set(markets));

  const sortBy = params.get("sort");
  if (sortBy && SORT_FIELDS.has(sortBy)) filters.sort_by = sortBy;
  filters.sort_order = params.get("order") === "asc" ? "asc" : "desc";
  filters.page = parsePositiveInteger(params.get("page"), DEFAULT_SCREENER_FILTERS.page);
  filters.page_size = parsePositiveInteger(params.get("size"), DEFAULT_SCREENER_FILTERS.page_size);
  if (params.get("broken_net") === "1") filters.is_broken_net = true;
  if (params.get("exclude_st") === "1") filters.exclude_st = true;

  return {
    filters,
    showPercentile: params.get("percentile") === "1",
    pePercentileMax: parsePercentile(params.get("pe_pct"), 50),
    pbPercentileMax: parsePercentile(params.get("pb_pct"), 50),
  };
}

export function serializeScreenerUrlState(state: ScreenerUrlState): URLSearchParams {
  const params = new URLSearchParams();
  for (const key of NUMBER_FILTER_KEYS) {
    const value = state.filters[key];
    if (value !== null && value !== undefined) params.set(key, String(value));
  }

  if (state.filters.industries?.length) {
    params.set("industries", Array.from(new Set(state.filters.industries)).join(","));
  }
  if (state.filters.concepts?.length) {
    params.set("concepts", Array.from(new Set(state.filters.concepts)).join(","));
  }
  if (state.filters.markets?.length) {
    params.set("markets", Array.from(new Set(state.filters.markets)).join(","));
  }
  if (state.filters.is_broken_net) params.set("broken_net", "1");
  if (state.filters.exclude_st) params.set("exclude_st", "1");
  if (state.filters.sort_by !== DEFAULT_SCREENER_FILTERS.sort_by) params.set("sort", state.filters.sort_by);
  if (state.filters.sort_order !== DEFAULT_SCREENER_FILTERS.sort_order) params.set("order", state.filters.sort_order);
  if (state.filters.page !== DEFAULT_SCREENER_FILTERS.page) params.set("page", String(state.filters.page));
  if (state.filters.page_size !== DEFAULT_SCREENER_FILTERS.page_size) params.set("size", String(state.filters.page_size));
  if (state.showPercentile) params.set("percentile", "1");
  if (state.pePercentileMax !== 50) params.set("pe_pct", String(state.pePercentileMax));
  if (state.pbPercentileMax !== 50) params.set("pb_pct", String(state.pbPercentileMax));
  return params;
}
