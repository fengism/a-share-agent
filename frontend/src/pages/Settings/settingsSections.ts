/**
 * 设置页分区与卡片分组的唯一声明来源。
 *
 * - `SETTINGS_SECTIONS` 用于 URL `?section=` 校验与导航项 key
 * - `SettingsDirectoryItem` 描述分区内部的卡片分组锚点，供目录条跳转
 */

export const SETTINGS_SECTIONS = ["account", "ai", "data-sources", "integrations", "admin"] as const;

export type SettingsSectionKey = (typeof SETTINGS_SECTIONS)[number];

export const DEFAULT_SETTINGS_SECTION: SettingsSectionKey = "account";

export function isSettingsSectionKey(value: string | null): value is SettingsSectionKey {
  return value !== null && (SETTINGS_SECTIONS as readonly string[]).includes(value);
}

export interface SettingsDirectoryItem {
  /** 分组容器的 DOM id，目录条点击后滚动到此锚点 */
  id: string;
  label: string;
}

/** 分区内卡片分组锚点（顺序即页面展示顺序） */
export const SETTINGS_ANCHORS = {
  llm: "settings-anchor-llm",
  providerDefaults: "settings-anchor-provider-defaults",
  pushChannels: "settings-anchor-push-channels",
  archive: "settings-anchor-archive",
  iwencai: "settings-anchor-iwencai",
  marketSources: "settings-anchor-market-sources",
  network: "settings-anchor-network",
} as const;

/** 目录条滚动时的吸顶偏移（页面头部高度） */
export const SETTINGS_SCROLL_OFFSET = 96;
