/**
 * 设置卡片声明式描述。
 *
 * 每张卡片只声明一次字段集合，save / reset / dirty 三处行为全部由它派生，
 * 避免同一组字段在多处手写而漂移（新增字段只需改这里）。
 *
 * - `fields`：普通字段，原样提交/还原/比较
 * - `secrets`：敏感字段，仅在用户输入了非掩码的新值时才提交
 */

import type { ConfigData, ConfigUpdate } from "../../types/settings";
import { EASTMONEY_RATE_LIMIT_KEYS } from "./config-cards/EastmoneyRateLimitConfigCard";

export type ConfigFieldKey = keyof ConfigUpdate;

export interface CardSpec {
  fields: readonly ConfigFieldKey[];
  secrets?: readonly ConfigFieldKey[];
  /** 保存成功提示 */
  saveMessage: string;
  /** 撤销成功提示 */
  resetMessage: string;
}

export const CARD_SPECS = {
  llm: {
    saveMessage: "大模型配置已保存",
    resetMessage: "已撤销大模型配置修改",
    fields: [
      "llm_provider",
      "llm_api_mode",
      "llm_api_version",
      "llm_base_url",
      "llm_model",
      "llm_sub_model",
      "llm_simple_tasks",
      "llm_temperature",
      "llm_context_length_tokens",
    ],
    secrets: ["llm_api_key"],
  },
  feishu: {
    saveMessage: "飞书配置已保存",
    resetMessage: "已撤销飞书推送配置修改",
    fields: [
      "feishu_enabled",
      "feishu_app_id",
      "feishu_folder_token",
      "feishu_wiki_space_id",
      "feishu_wiki_daily_review_parent",
      "feishu_wiki_analysis_parent",
      "feishu_daily_review_folder",
      "feishu_analysis_folder",
      "feishu_default_receiver",
    ],
    secrets: ["feishu_app_secret"],
  },
  notion: {
    saveMessage: "Notion 配置已保存",
    resetMessage: "已撤销 Notion 配置修改",
    fields: ["notion_enabled", "notion_parent_page_id", "notion_database_id"],
    secrets: ["notion_api_token"],
  },
  notificationChannels: {
    saveMessage: "通知推送通道配置已保存",
    resetMessage: "已撤销通知推送通道配置修改",
    fields: [
      "push_auto_enabled",
      "push_daily_review_auto",
      "push_potential_auto",
      "push_feishu_enabled",
      "feishu_webhook_url",
      "push_dingtalk_enabled",
      "dingtalk_webhook_url",
      "push_wecom_enabled",
      "wecom_webhook_url",
      "push_wxpusher_enabled",
      "wxpusher_uids",
    ],
    secrets: ["feishu_webhook_secret", "dingtalk_webhook_secret", "wxpusher_app_token"],
  },
  iwencai: {
    saveMessage: "问财数据源配置已保存",
    resetMessage: "已撤销问财配置修改",
    fields: ["iwencai_enabled", "iwencai_base_url"],
    secrets: ["iwencai_api_key"],
  },
  twitter: {
    saveMessage: "Twitter 账号配置已保存",
    resetMessage: "已撤销 Twitter 账号修改",
    fields: ["twitter_feeds"],
  },
  fred: {
    saveMessage: "FRED API Key 已保存",
    resetMessage: "已撤销 FRED 配置修改",
    fields: [],
    secrets: ["fred_api_key"],
  },
  anysearch: {
    saveMessage: "AnySearch API Key 已保存",
    resetMessage: "已撤销 AnySearch 修改",
    fields: [],
    secrets: ["anysearch_api_key"],
  },
  fuyao: {
    saveMessage: "fuyao API Key 已保存",
    resetMessage: "已撤销 fuyao 凭证修改",
    fields: [],
    secrets: ["fuyao_api_key"],
  },
  dataSourceCookies: {
    saveMessage: "数据源登录凭证已保存",
    resetMessage: "已撤销数据源凭证修改",
    fields: [],
    secrets: ["eastmoney_cookie", "baidu_cookie", "ths_cookie", "legulegu_token"],
  },
  outboundProxy: {
    saveMessage: "出站代理配置已保存",
    resetMessage: "已撤销出站代理修改",
    fields: [
      "outbound_proxy_type",
      "outbound_proxy_url",
      "outbound_proxy_timeout_seconds",
      "outbound_proxy_retries",
    ],
  },
  eastmoneyRateLimit: {
    saveMessage: "东财限流与风控配置已保存",
    resetMessage: "已撤销东财限流配置修改",
    fields: [...EASTMONEY_RATE_LIMIT_KEYS],
  },
  backup: {
    saveMessage: "数据库备份设置已保存",
    resetMessage: "已撤销备份配置修改",
    fields: [
      "database_backup_retention_count",
      "database_backup_include_market_daily",
      "market_daily_backup_interval_days",
      "market_daily_backup_compression_level",
    ],
  },
  scheduledTasks: {
    saveMessage: "后台常驻任务设置已保存",
    resetMessage: "已撤销后台常驻任务设置修改",
    fields: [
      "macro_analysis_prewarm_enabled",
      "daily_review_prewarm_enabled",
      "potential_stock_daily_enabled",
      "stock_valuation_snapshot_refresh_enabled",
    ],
  },
  researchBudget: {
    saveMessage: "研究预算与超时已保存",
    resetMessage: "已撤销研究预算修改",
    fields: [
      "analysis_llm_timeout_seconds",
      "agent_research_timeout_seconds",
      "industry_chain_research_timeout_seconds",
      "industry_chain_repair_research_timeout_seconds",
      "industry_chain_repair_synthesis_timeout_seconds",
      "industry_chain_max_rounds",
      "industry_chain_repair_max_rounds",
      "industry_chain_tool_calls_total",
      "industry_chain_repair_tool_calls_total",
      "chat_max_tool_calls_total",
    ],
  },
  marketDaily: {
    saveMessage: "市场日行情刷新配置已保存",
    resetMessage: "已撤销日行情刷新配置修改",
    fields: [
      "market_daily_bar_refresh_enabled",
      "market_daily_bar_refresh_poll_seconds",
      "market_daily_bar_refresh_retry_base_seconds",
      "market_daily_observation_retention_days",
      "market_daily_attempt_retention_days",
    ],
  },
  bot: {
    saveMessage: "Bot 配置已保存",
    resetMessage: "已撤销 Bot 配置修改",
    fields: [
      "bot_enabled",
      "bot_command_prefix",
      "bot_service_user_id",
      "bot_rate_limit_requests",
      "bot_rate_limit_window",
      "bot_webhook_max_skew_seconds",
      "bot_event_dedup_ttl_seconds",
      "bot_job_poll_seconds",
      "bot_job_lease_seconds",
      "bot_job_max_attempts",
      "bot_job_retry_base_seconds",
      "bot_job_worker_concurrency",
      "bot_batch_concurrency",
      "bot_batch_max_stocks",
      "bot_admin_users",
    ],
    secrets: ["feishu_verification_token", "feishu_encrypt_key"],
  },
} as const satisfies Record<string, CardSpec>;

export type CardKey = keyof typeof CARD_SPECS;

export const CARD_KEYS = Object.keys(CARD_SPECS) as CardKey[];

/** 密钥字段在下发时带 *** 掩码，掩码值不得回写覆盖已存值。 */
export function isMaskedValue(value: unknown): boolean {
  return typeof value === "string" && value.includes("***");
}

/** 生成保存补丁：普通字段原样，敏感字段仅在填入新值时提交。 */
export function buildCardPatch(form: ConfigUpdate, spec: CardSpec): ConfigUpdate {
  const patch: Record<string, unknown> = {};
  for (const key of spec.fields) {
    const value = form[key];
    if (value !== undefined) patch[key] = value;
  }
  for (const key of spec.secrets ?? []) {
    const value = form[key];
    if (typeof value === "string" && value !== "" && !isMaskedValue(value)) {
      patch[key] = value;
    }
  }
  return patch as ConfigUpdate;
}

/** 生成还原补丁：把上次保存的生效值写回表单（含掩码值，供用户看到已配置）。 */
export function buildCardReset(config: ConfigData, spec: CardSpec): ConfigUpdate {
  const patch: Record<string, unknown> = {};
  for (const key of [...spec.fields, ...(spec.secrets ?? [])]) {
    const value = config[key];
    if (value !== undefined) patch[key] = value;
  }
  return patch as ConfigUpdate;
}

/** 判断卡片是否有未保存修改（敏感字段忽略掩码值）。 */
export function isCardDirty(form: ConfigUpdate, config: ConfigData, spec: CardSpec): boolean {
  for (const key of spec.fields) {
    const next = form[key];
    if (next !== undefined && next !== config[key]) return true;
  }
  for (const key of spec.secrets ?? []) {
    const next = form[key];
    if (typeof next === "string" && next !== "" && !isMaskedValue(next) && next !== config[key]) {
      return true;
    }
  }
  return false;
}
