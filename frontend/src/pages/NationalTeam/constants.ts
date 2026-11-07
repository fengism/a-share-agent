export const HISTORY_WINDOWS = [30, 60, 120, 240, 365] as const;

export const INDEX_ORDER = [
  "沪深300",
  "上证50",
  "中证A500",
  "中证500",
  "中证1000",
  "中证2000",
  "科创50",
  "科创100",
  "创业板",
  "红利低波",
];

export const INDEX_TAG_COLORS: Record<string, string> = {
  "沪深300": "blue",
  "上证50": "purple",
  "中证A500": "gold",
  "中证500": "cyan",
  "中证1000": "orange",
  "中证2000": "geekblue",
  "科创50": "volcano",
  "科创100": "magenta",
  "创业板": "cyan",
  "红利低波": "gold",
};

export const CATEGORY_TAG_LABELS: Record<string, { label: string; color: string }> = {
  core_broad: { label: "核心大盘", color: "blue" },
  a500: { label: "新质A500", color: "gold" },
  growth: { label: "中小成长", color: "cyan" },
  dividend: { label: "红利防御", color: "purple" },
};

export const CATEGORY_OPTIONS = [
  { label: "全部板块", value: "all" },
  { label: "核心大盘", value: "core_broad" },
  { label: "新质A500", value: "a500" },
  { label: "中小成长", value: "growth" },
  { label: "红利防御", value: "dividend" },
];

export const QUALITY_LABELS: Record<string, string> = {
  complete: "数据完整",
  partial: "部分覆盖",
  insufficient: "数据不足",
};

export function indexOrder(name: string) {
  const order = INDEX_ORDER.indexOf(name);
  // 后端新增指数不在前端名单时排到最后，而不是被 indexOf 的 -1 顶到最前。
  return order === -1 ? INDEX_ORDER.length : order;
}
