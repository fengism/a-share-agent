export type LlmApiMode = "auto" | "openai" | "litellm";

/**
 * 公共出站代理类型；none 表示已声明作用域内的接口仍强制直连。
 * 各数据源在代码中自行声明生效范围，未声明的接口始终直连。
 */
export type OutboundProxyType = "none" | "http" | "socks5";

export interface ProviderDefault {
  label: string;
  description: string;
  api_mode: Exclude<LlmApiMode, "auto">;
  api_key_required: boolean;
  api_version?: string;
  base_url: string;
  model: string;
}

export interface ConfigData {
  llm_provider: string;
  llm_api_mode: LlmApiMode;
  llm_api_version: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_model: string;
  llm_sub_model: string;
  llm_simple_tasks: string;
  llm_temperature: number;
  llm_context_length_tokens: number;
  feishu_enabled: boolean;
  feishu_app_id: string;
  feishu_app_secret: string;
  feishu_folder_token: string;
  feishu_wiki_space_id: string;
  feishu_wiki_daily_review_parent: string;
  feishu_wiki_analysis_parent: string;
  feishu_daily_review_folder: string;
  feishu_analysis_folder: string;
  feishu_default_receiver: string;
  push_auto_enabled?: boolean;
  push_daily_review_auto?: boolean;
  push_potential_auto?: boolean;
  push_feishu_enabled?: boolean;
  push_dingtalk_enabled?: boolean;
  push_wecom_enabled?: boolean;
  push_wxpusher_enabled?: boolean;
  feishu_webhook_url?: string;
  feishu_webhook_secret?: string;
  dingtalk_webhook_url?: string;
  dingtalk_webhook_secret?: string;
  wecom_webhook_url?: string;
  wxpusher_app_token?: string;
  wxpusher_uids?: string;
  notion_enabled: boolean;
  notion_api_token: string;
  notion_parent_page_id: string;
  notion_database_id: string;
  iwencai_enabled: boolean;
  iwencai_base_url: string;
  iwencai_api_key: string;
  disabled_chat_skills: string[];
  disabled_chat_agents: string[];
  provider_defaults: Record<string, ProviderDefault>;
  twitter_feeds: string[];
  fred_api_key: string;
  anysearch_api_key: string;
  ths_cookie: string;
  fuyao_api_key: string;
  http_trust_env: boolean;
  eastmoney_min_interval_seconds: number;
  eastmoney_datacenter_min_interval_seconds: number;
  eastmoney_datacenter_cooldown_seconds: number;
  eastmoney_jitter_min_seconds: number;
  eastmoney_jitter_max_seconds: number;
  eastmoney_cooldown_seconds: number;
  eastmoney_transient_failure_threshold: number;
  /** 公共出站代理类型；none 表示已声明作用域内的接口仍强制直连。 */
  outbound_proxy_type: OutboundProxyType;
  /** 公共出站代理地址，内含凭证，接口下发时按敏感字段脱敏。 */
  outbound_proxy_url: string;
  outbound_proxy_timeout_seconds: number;
  outbound_proxy_retries: number;
  market_daily_bar_refresh_enabled: boolean;
  market_daily_bar_refresh_poll_seconds: number;
  market_daily_bar_refresh_retry_base_seconds: number;
  market_daily_observation_retention_days: number;
  market_daily_attempt_retention_days: number;
  database_backup_retention_count: number;
  database_backup_include_market_daily: boolean;
  market_daily_backup_interval_days: number;
  market_daily_backup_compression_level: number;
  bot_enabled: boolean;
  bot_command_prefix: string;
  bot_service_user_id: number;
  bot_feishu_app_id: string;
  bot_feishu_app_secret: string;
  feishu_verification_token: string;
  feishu_encrypt_key: string;
  bot_rate_limit_requests: number;
  bot_rate_limit_window: number;
  bot_webhook_max_skew_seconds: number;
  bot_event_dedup_ttl_seconds: number;
  bot_job_poll_seconds: number;
  bot_job_lease_seconds: number;
  bot_job_max_attempts: number;
  bot_job_retry_base_seconds: number;
  bot_job_worker_concurrency: number;
  bot_batch_concurrency: number;
  bot_batch_max_stocks: number;
  bot_admin_users: string[];
  analysis_llm_timeout_seconds: number;
  agent_research_timeout_seconds: number;
  industry_chain_research_timeout_seconds: number;
  industry_chain_repair_research_timeout_seconds: number;
  industry_chain_repair_synthesis_timeout_seconds: number;
  industry_chain_max_rounds: number;
  industry_chain_repair_max_rounds: number;
  industry_chain_tool_calls_total: number;
  industry_chain_repair_tool_calls_total: number;
  chat_max_tool_calls_total: number;
  /** Whether the current user may edit instance-global fields. */
  is_admin: boolean;
}

export type ConfigUpdate = Partial<Omit<ConfigData, "provider_defaults" | "is_admin">>;

/** 出站代理连通性探测请求（留空则使用默认探测目标）。 */
export interface ProxyTestRequest {
  target_url?: string;
}

/** 出站代理连通性探测结果。 */
export interface ProxyTestResponse {
  ok: boolean;
  target_url: string;
  proxy_enabled: boolean;
  proxy_type: string;
  exit_ip: string | null;
  latency_ms: number;
  message: string;
}

export type BotJobStatus = "pending" | "running" | "succeeded" | "failed";

export interface BotAdminJob {
  id: string;
  event_id: string;
  platform: string;
  request_user_id: string;
  command_name: string;
  status: BotJobStatus;
  attempts: number;
  max_attempts: number;
  last_error: string | null;
  created_at: number;
  updated_at: number;
  completed_at: number | null;
}

export interface BotAdminJobsResponse {
  counts: Record<BotJobStatus, number>;
  jobs: BotAdminJob[];
}

export interface LlmModelsRequest {
  base_url?: string;
  api_key?: string;
  api_mode?: string;
  api_version?: string;
}

export interface LlmModelsResponse {
  models: string[];
}


export type MarketDailySegment = "cn_stock" | "cn_index" | "hk_stock" | "hk_index";
export type MarketDailyRefreshCheckpoint = "initial" | "recheck";
export type MarketDailyRefreshStatus = "pending" | "running" | "success" | "skipped" | "failed";

export interface MarketDailyBarRefreshStatusItem {
  trade_date: string;
  checkpoint: MarketDailyRefreshCheckpoint;
  segment: MarketDailySegment;
  status: MarketDailyRefreshStatus;
  attempts: number;
  next_retry_at: string | null;
  expected_count: number | null;
  stored_count: number | null;
  last_error: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface MarketDailyBarRefreshHistory {
  items: MarketDailyBarRefreshStatusItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface MarketDailyBarRefreshRequest {
  trade_date: string;
  checkpoint: MarketDailyRefreshCheckpoint;
  segments: MarketDailySegment[];
  retry_failed_only?: boolean;
  force?: boolean;
}

export type MarketDailyBackfillStatus = "pending" | "running" | "succeeded" | "failed" | "cancelled";

export interface MarketDailyBackfillRequest {
  start_date: string;
  end_date: string;
  market?: "cn";
  instrument_type?: "stock";
  overwrite_existing?: boolean;
  max_provider_sources?: number;
}

export interface MarketDailyBackfillJob {
  job_id: string;
  market: "cn";
  instrument_type: "stock";
  start_date: string;
  end_date: string;
  overwrite_existing: boolean;
  max_provider_sources: number;
  status: MarketDailyBackfillStatus;
  total_instruments: number;
  completed_instruments: number;
  succeeded_instruments: number;
  failed_instruments: number;
  retryable_failed_instruments: number;
  average_quality_score: number | null;
  stored_bars: number;
  current_code: string | null;
  last_error: string | null;
  failure_details: Array<{ code: string; kind?: string; retryable?: boolean; error: string }>;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
}

export interface MarketDailyBackfillJobList {
  items: MarketDailyBackfillJob[];
  total: number;
}

export interface MarketDailyBarRefreshResult {
  trade_date: string;
  checkpoint: MarketDailyRefreshCheckpoint;
  requested_segments: MarketDailySegment[];
  statuses: MarketDailyBarRefreshStatusItem[];
}

export interface MarketDailyBarDeleteRequest {
  trade_date: string;
  segments: MarketDailySegment[];
  rebuild?: boolean;
  checkpoint?: MarketDailyRefreshCheckpoint;
}

export interface MarketDailyBarDeleteResult {
  trade_date: string;
  deleted_bars: number;
  deleted_observations: number;
  deleted_jobs: number;
  rebuild_result: MarketDailyBarRefreshResult | null;
}


export type MarketAdjustmentFactorHealth = "missing" | "healthy" | "stale" | "degraded" | "incomplete";

export interface MarketAdjustmentFactorStatus {
  code: string;
  status: MarketAdjustmentFactorHealth;
  bar_count: number;
  factor_count: number;
  action_count: number;
  first_bar_date: string | null;
  last_bar_date: string | null;
  first_factor_date: string | null;
  last_factor_date: string | null;
  action_hash: string | null;
  algorithm_version: string | null;
  source: string | null;
  calculated_at: string | null;
  last_checked_at: string | null;
  last_error: string | null;
  using_last_good: boolean;
  coverage_complete: boolean;
}
