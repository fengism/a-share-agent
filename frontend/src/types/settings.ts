import type { components } from "../api/generated/schema";

type GeneratedConfigResponse = components["schemas"]["ConfigResponse"];

/** 生效配置的字段类型直接来自 OpenAPI 生成产物，避免手写字段与后端漂移。 */
export type LlmApiMode = GeneratedConfigResponse["llm_api_mode"];

/**
 * 公共出站代理类型；none 表示已声明作用域内的接口仍强制直连。
 * 各数据源在代码中自行声明生效范围，未声明的接口始终直连。
 */
export type OutboundProxyType = GeneratedConfigResponse["outbound_proxy_type"];

export interface ProviderDefault {
  label: string;
  description: string;
  api_mode: Exclude<LlmApiMode, "auto">;
  api_key_required: boolean;
  api_version?: string;
  base_url: string;
  model: string;
}

/**
 * 当前用户的生效配置：字段与后端 `ConfigResponse` 契约一一对应，
 * 由 OpenAPI 生成类型派生，仅把 `provider_defaults` 收敛为强类型字典。
 */
export type ConfigData = Omit<GeneratedConfigResponse, "provider_defaults"> & {
  provider_defaults: Record<string, ProviderDefault>;
};

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
