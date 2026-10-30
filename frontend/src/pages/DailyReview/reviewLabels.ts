/** 复盘事件影响卡片的枚举文案（页面与导出共用） */

export const eventTypeLabels = {
  policy: "政策",
  macro: "宏观",
  global: "海外",
  industry: "产业",
  market: "市场",
} as const;

export const eventDirectionLabels = {
  positive: "偏利好",
  negative: "偏利空",
  mixed: "影响分化",
  neutral: "方向待确认",
} as const;

export const eventHorizonLabels = {
  intraday: "日内",
  short_term: "短期",
  medium_term: "中期",
} as const;

export const eventTimingLabels = {
  before: "盘前/事前",
  on_date: "复盘日",
  after: "事后验证",
} as const;
