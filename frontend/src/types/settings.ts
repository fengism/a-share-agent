export type LlmApiMode = "auto" | "openai" | "litellm";

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
  eastmoney_cookie: string;
  fred_api_key: string;
  baidu_cookie: string;
  ths_cookie: string;
  http_trust_env: boolean;
  eastmoney_min_interval_seconds: number;
  eastmoney_datacenter_min_interval_seconds: number;
  eastmoney_datacenter_cooldown_seconds: number;
  eastmoney_jitter_min_seconds: number;
  eastmoney_jitter_max_seconds: number;
  eastmoney_cooldown_seconds: number;
  eastmoney_transient_failure_threshold: number;
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
  industry_chain_repair_timeout_seconds: number;
  industry_chain_tool_calls_total: number;
  industry_chain_repair_tool_calls_total: number;
  chat_max_tool_calls_total: number;
  /** Whether the current user may edit instance-global fields. */
  is_admin: boolean;
}

export type ConfigUpdate = Partial<Omit<ConfigData, "provider_defaults" | "is_admin">>;

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
