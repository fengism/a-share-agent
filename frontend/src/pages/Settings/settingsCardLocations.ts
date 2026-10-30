/**
 * 卡片 → 所属分区 / 锚点 / 展示名 的索引。
 *
 * 脏改动汇总面板、目录跳转都需要"某张卡在哪个分区"，这里集中声明一次，
 * 避免在多个组件里重复维护映射。
 */

import type { CardKey } from "./cardSpecs";
import { SETTINGS_ANCHORS, type SettingsSectionKey } from "./settingsSections";

export interface SettingsCardLocation {
  label: string;
  section: SettingsSectionKey;
  /** 卡片所属分组锚点；管理员分区的卡片在页签内，无独立锚点 */
  anchorId?: string;
  /** 所属分区内的二级页签（仅管理员分区使用） */
  tab?: "ops" | "bot" | "user";
}

export const SETTINGS_CARD_LOCATIONS: Record<CardKey, SettingsCardLocation> = {
  llm: { label: "大模型配置", section: "ai", anchorId: SETTINGS_ANCHORS.llm },
  feishu: { label: "飞书协同", section: "integrations", anchorId: SETTINGS_ANCHORS.archive },
  notion: { label: "Notion 归档", section: "integrations", anchorId: SETTINGS_ANCHORS.archive },
  notificationChannels: {
    label: "通知推送渠道",
    section: "integrations",
    anchorId: SETTINGS_ANCHORS.pushChannels,
  },
  iwencai: { label: "问财数据源", section: "data-sources", anchorId: SETTINGS_ANCHORS.iwencai },
  twitter: { label: "推特舆情源", section: "data-sources", anchorId: SETTINGS_ANCHORS.marketSources },
  fred: { label: "FRED 宏观源", section: "data-sources", anchorId: SETTINGS_ANCHORS.marketSources },
  anysearch: { label: "AnySearch 搜索", section: "data-sources", anchorId: SETTINGS_ANCHORS.marketSources },
  fuyao: { label: "复耀行情凭据", section: "data-sources", anchorId: SETTINGS_ANCHORS.marketSources },
  dataSourceCookies: { label: "数据源 Cookie", section: "data-sources", anchorId: SETTINGS_ANCHORS.marketSources },
  outboundProxy: { label: "出站代理", section: "data-sources", anchorId: SETTINGS_ANCHORS.network },
  eastmoneyRateLimit: { label: "东财限流", section: "data-sources", anchorId: SETTINGS_ANCHORS.network },
  backup: { label: "备份保留策略", section: "admin", tab: "ops" },
  scheduledTasks: { label: "定时任务开关", section: "admin", tab: "ops" },
  researchBudget: { label: "AI 思考预算", section: "admin", tab: "ops" },
  marketDaily: { label: "日线数据维护", section: "admin", tab: "ops" },
  bot: { label: "自动化推送机器人", section: "admin", tab: "bot" },
};

export const SETTINGS_SECTION_LABELS: Record<SettingsSectionKey, string> = {
  account: "账号与安全",
  ai: "AI 模型配置",
  "data-sources": "数据源管理",
  integrations: "协同与自动推送",
  admin: "管理员工具",
};
