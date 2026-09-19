/** Shared application font stacks for UI, charts, and technical content. */
export const APP_FONT_FAMILY =
  '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", "微软雅黑", "Helvetica Neue", Arial, sans-serif';

export const APP_MONO_FONT_FAMILY =
  '"DIN Alternate", "DIN Pro", "SF Mono", "SFMono-Regular", "JetBrains Mono", "Cascadia Code", "Cascadia Mono", "Segoe UI Mono", Consolas, "Liberation Mono", Menlo, Monaco, "Courier New", monospace';

/** Numeric sizes for canvas/chart libraries that cannot consume CSS variables. */
export const APP_FONT_SIZE = {
  xs: 11,
  sm: 12,
  md: 13,
  base: 14,
  lg: 16,
  xl: 18,
  xxl: 20,
  title: 24,
  display: 32,
} as const;
