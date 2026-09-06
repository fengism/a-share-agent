import type { ChatDisplayMessage } from "../../types/chat";
import type { ScreenerFilter } from "../../types/stock";
import {
  DEFAULT_SCREENER_FILTERS,
  type ScreenerUrlState,
} from "../../features/screener/screenerUrlState";

export interface ChatResultContext {
  stockCodes: string[];
  screenerState?: ScreenerUrlState;
}

export type ChatResultAction = "watchlist" | "alert" | "screener" | "quant";
export type ChatResultActionHandler = (action: ChatResultAction, context: ChatResultContext) => void;

const CODE_KEYS = new Set(["code", "codes", "stock_code", "stock_codes", "股票代码", "证券代码"]);
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
] as const;
const SORT_FIELDS = new Set(["market_cap", "pe", "pb", "price", "change_pct", "turnover_pct", "volume"]);

function isStockCode(value: string): boolean {
  return /^[03468]\d{5}$/.test(value);
}

function collectCodesFromText(text: string, target: Set<string>) {
  const pattern = /(?:^|\D)([03468]\d{5})(?!\d)/g;
  for (const match of text.matchAll(pattern)) {
    if (match[1]) target.add(match[1]);
  }
}

function collectCodeValue(value: unknown, target: Set<string>) {
  if (typeof value === "string") {
    for (const candidate of value.split(/[，,\s]+/)) {
      if (isStockCode(candidate)) target.add(candidate);
    }
    return;
  }
  if (Array.isArray(value)) value.forEach((item) => collectCodeValue(item, target));
}

function collectStructuredCodes(value: unknown, target: Set<string>) {
  if (Array.isArray(value)) {
    value.forEach((item) => collectStructuredCodes(item, target));
    return;
  }
  if (typeof value !== "object" || value === null) return;
  for (const [key, item] of Object.entries(value)) {
    if (CODE_KEYS.has(key)) collectCodeValue(item, target);
    else collectStructuredCodes(item, target);
  }
}

function parseJson(value?: string): unknown {
  if (!value) return undefined;
  try {
    return JSON.parse(value);
  } catch {
    return undefined;
  }
}

function buildScreenerState(argumentsValue: unknown): ScreenerUrlState | undefined {
  if (typeof argumentsValue !== "object" || argumentsValue === null || Array.isArray(argumentsValue)) return undefined;
  const values = argumentsValue as Record<string, unknown>;
  const filters: ScreenerFilter = { ...DEFAULT_SCREENER_FILTERS };
  let hasFilter = false;
  for (const key of NUMBER_FILTER_KEYS) {
    if (typeof values[key] === "number" && Number.isFinite(values[key])) {
      filters[key] = values[key];
      hasFilter = true;
    }
  }
  if (Array.isArray(values.industries)) {
    const industries = values.industries.filter((item): item is string => typeof item === "string" && !!item.trim());
    if (industries.length) {
      filters.industries = Array.from(new Set(industries));
      hasFilter = true;
    }
  }
  if (Array.isArray(values.concepts)) {
    const concepts = values.concepts.filter((item): item is string => typeof item === "string" && !!item.trim());
    if (concepts.length) {
      filters.concepts = Array.from(new Set(concepts));
      hasFilter = true;
    }
  }
  if (typeof values.sort_by === "string" && SORT_FIELDS.has(values.sort_by)) {
    filters.sort_by = values.sort_by;
    hasFilter = true;
  }
  if (values.sort_order === "asc" || values.sort_order === "desc") {
    filters.sort_order = values.sort_order;
    hasFilter = true;
  }
  if (!hasFilter) return undefined;
  return {
    filters: { ...filters, page: 1 },
    showPercentile: false,
    pePercentileMax: 50,
    pbPercentileMax: 50,
  };
}

export function extractChatResultContext(message: ChatDisplayMessage): ChatResultContext {
  const codes = new Set<string>();
  collectCodesFromText(message.content, codes);
  let screenerState: ScreenerUrlState | undefined;

  for (const toolCall of message.toolCalls ?? []) {
    const argumentsValue = parseJson(toolCall.arguments);
    collectStructuredCodes(argumentsValue, codes);
    const resultValue = parseJson(toolCall.result);
    if (resultValue === undefined && toolCall.result) collectCodesFromText(toolCall.result, codes);
    else collectStructuredCodes(resultValue, codes);
    if (!screenerState && toolCall.name === "screen_stocks") {
      screenerState = buildScreenerState(argumentsValue);
    }
  }

  return { stockCodes: [...codes].slice(0, 10), screenerState };
}
