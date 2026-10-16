import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { RobotOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, message, Popconfirm, Tag } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { useConfig, useTestOutboundProxy } from "../../api/queries";
import { queryKeys } from "../../api/queryKeys";
import ChangePasswordCard from "../../components/ChangePasswordCard";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { ConfigUpdate, ProviderDefault, ProxyTestResponse } from "../../types/settings";
import { EASTMONEY_RATE_LIMIT_KEYS, normalizeProxyUrl, validateProxyUrl } from "./ConfigCards";
import SystemUpdateCard from "./SystemUpdateCard";
import { useConfigSectionSave } from "./useConfigSectionSave";

const AiSettingsSection = lazy(() => import("./PersonalSettingsSections").then((module) => ({
  default: module.AiSettingsSection,
})));
const IntegrationsSettingsSection = lazy(() => import("./PersonalSettingsSections").then((module) => ({
  default: module.IntegrationsSettingsSection,
})));
const DataSourcesSettingsSection = lazy(() => import("./AdminSettingsSections").then((module) => ({
  default: module.DataSourcesSettingsSection,
})));
const AdminSettingsSection = lazy(() => import("./AdminSettingsSections").then((module) => ({
  default: module.AdminSettingsSection,
})));

function SettingsSectionFallback() {
  return <div role="status" aria-live="polite" style={{ minHeight: 240, padding: 24 }}>正在加载配置模块...</div>;
}

export default function SettingsPage() {
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const colors = useColors();
  const { data: config, isLoading, error, refetch } = useConfig();
  const { save: saveConfig, isSaving } = useConfigSectionSave();
  const {
    mutate: testOutboundProxyMutate,
    isPending: isTestingOutboundProxy,
  } = useTestOutboundProxy();
  const [outboundProxyTestResult, setOutboundProxyTestResult] = useState<ProxyTestResponse | null>(null);
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const isAdmin = Boolean(config?.is_admin);

  const [form, setForm] = useState<ConfigUpdate>({});
  const [initializedUserId, setInitializedUserId] = useState<number | null>(null);
  const [previousProvider, setPreviousProvider] = useState("");
  const [activeSection, setActiveSection] = useState("account");

  const buildInitialForm = useCallback((cfg: typeof config): ConfigUpdate => {
    if (!cfg) return {};
    return {
      llm_provider: cfg.llm_provider,
      llm_api_mode: cfg.llm_api_mode,
      llm_api_version: cfg.llm_api_version,
      llm_api_key: cfg.llm_api_key,
      llm_base_url: cfg.llm_base_url,
      llm_model: cfg.llm_model,
      llm_sub_model: cfg.llm_sub_model,
      llm_simple_tasks: cfg.llm_simple_tasks,
      llm_temperature: cfg.llm_temperature,
      llm_context_length_tokens: cfg.llm_context_length_tokens,
      feishu_enabled: cfg.feishu_enabled,
      feishu_app_id: cfg.feishu_app_id,
      feishu_app_secret: cfg.feishu_app_secret,
      feishu_folder_token: cfg.feishu_folder_token,
      feishu_wiki_space_id: cfg.feishu_wiki_space_id,
      feishu_wiki_daily_review_parent: cfg.feishu_wiki_daily_review_parent,
      feishu_wiki_analysis_parent: cfg.feishu_wiki_analysis_parent,
      feishu_daily_review_folder: cfg.feishu_daily_review_folder,
      feishu_analysis_folder: cfg.feishu_analysis_folder,
      feishu_default_receiver: cfg.feishu_default_receiver,
      notion_enabled: cfg.notion_enabled,
      notion_api_token: cfg.notion_api_token,
      notion_parent_page_id: cfg.notion_parent_page_id,
      notion_database_id: cfg.notion_database_id,
      iwencai_enabled: cfg.iwencai_enabled,
      iwencai_base_url: cfg.iwencai_base_url,
      iwencai_api_key: cfg.iwencai_api_key,
      twitter_feeds: cfg.twitter_feeds,
      fred_api_key: cfg.fred_api_key,
      market_daily_bar_refresh_enabled: cfg.market_daily_bar_refresh_enabled,
      market_daily_bar_refresh_poll_seconds: cfg.market_daily_bar_refresh_poll_seconds,
      market_daily_bar_refresh_retry_base_seconds: cfg.market_daily_bar_refresh_retry_base_seconds,
      market_daily_observation_retention_days: cfg.market_daily_observation_retention_days,
      market_daily_attempt_retention_days: cfg.market_daily_attempt_retention_days,
      database_backup_retention_count: cfg.database_backup_retention_count,
      database_backup_include_market_daily: cfg.database_backup_include_market_daily,
      market_daily_backup_interval_days: cfg.market_daily_backup_interval_days,
      market_daily_backup_compression_level: cfg.market_daily_backup_compression_level,
      fuyao_api_key: cfg.fuyao_api_key,
      outbound_proxy_type: cfg.outbound_proxy_type,
      outbound_proxy_url: cfg.outbound_proxy_url,
      outbound_proxy_timeout_seconds: cfg.outbound_proxy_timeout_seconds,
      outbound_proxy_retries: cfg.outbound_proxy_retries,
      eastmoney_min_interval_seconds: cfg.eastmoney_min_interval_seconds,
      eastmoney_datacenter_min_interval_seconds: cfg.eastmoney_datacenter_min_interval_seconds,
      eastmoney_datacenter_cooldown_seconds: cfg.eastmoney_datacenter_cooldown_seconds,
      eastmoney_jitter_min_seconds: cfg.eastmoney_jitter_min_seconds,
      eastmoney_jitter_max_seconds: cfg.eastmoney_jitter_max_seconds,
      eastmoney_cooldown_seconds: cfg.eastmoney_cooldown_seconds,
      eastmoney_transient_failure_threshold: cfg.eastmoney_transient_failure_threshold,
      anysearch_api_key: "",
      bot_enabled: cfg.bot_enabled,
      bot_command_prefix: cfg.bot_command_prefix,
      bot_service_user_id: cfg.bot_service_user_id,
      bot_feishu_app_id: cfg.bot_feishu_app_id,
      bot_feishu_app_secret: cfg.bot_feishu_app_secret,
      feishu_verification_token: cfg.feishu_verification_token,
      feishu_encrypt_key: cfg.feishu_encrypt_key,
      bot_rate_limit_requests: cfg.bot_rate_limit_requests,
      bot_rate_limit_window: cfg.bot_rate_limit_window,
      bot_webhook_max_skew_seconds: cfg.bot_webhook_max_skew_seconds,
      bot_event_dedup_ttl_seconds: cfg.bot_event_dedup_ttl_seconds,
      bot_job_poll_seconds: cfg.bot_job_poll_seconds,
      bot_job_lease_seconds: cfg.bot_job_lease_seconds,
      bot_job_max_attempts: cfg.bot_job_max_attempts,
      bot_job_retry_base_seconds: cfg.bot_job_retry_base_seconds,
      bot_job_worker_concurrency: cfg.bot_job_worker_concurrency,
      bot_batch_concurrency: cfg.bot_batch_concurrency,
      bot_batch_max_stocks: cfg.bot_batch_max_stocks,
      bot_admin_users: cfg.bot_admin_users,
      analysis_llm_timeout_seconds: cfg.analysis_llm_timeout_seconds,
      agent_research_timeout_seconds: cfg.agent_research_timeout_seconds,
      industry_chain_research_timeout_seconds: cfg.industry_chain_research_timeout_seconds,
      industry_chain_repair_research_timeout_seconds: cfg.industry_chain_repair_research_timeout_seconds,
      industry_chain_repair_synthesis_timeout_seconds: cfg.industry_chain_repair_synthesis_timeout_seconds,
      industry_chain_max_rounds: cfg.industry_chain_max_rounds,
      industry_chain_repair_max_rounds: cfg.industry_chain_repair_max_rounds,
      industry_chain_tool_calls_total: cfg.industry_chain_tool_calls_total,
      industry_chain_repair_tool_calls_total: cfg.industry_chain_repair_tool_calls_total,
      chat_max_tool_calls_total: cfg.chat_max_tool_calls_total,
    };
  }, []);

  useEffect(() => {
    if (!config || !user || initializedUserId === user.id) return;
    setForm(buildInitialForm(config));
    setPreviousProvider(config.llm_provider);
    setInitializedUserId(user.id);
  }, [buildInitialForm, config, initializedUserId, user]);

  const handleResetAllUnsaved = useCallback(() => {
    if (!config) return;
    setForm(buildInitialForm(config));
    setPreviousProvider(config.llm_provider);
    message.success("已撤销所有未保存的修改");
  }, [buildInitialForm, config]);

  const updateForm = useCallback((patch: ConfigUpdate) => {
    setForm((previous) => ({ ...previous, ...patch }));
  }, []);

  const handleProviderChange = useCallback((newProvider: string) => {
    const defaults = config?.provider_defaults?.[newProvider] as ProviderDefault | undefined;
    const oldDefaults = config?.provider_defaults?.[previousProvider] as ProviderDefault | undefined;
    const patch: ConfigUpdate = { llm_provider: newProvider };

    if (defaults) {
      patch.llm_api_mode = defaults.api_mode;
      patch.llm_api_version = defaults.api_version || "";
      if (!form.llm_base_url || form.llm_base_url === oldDefaults?.base_url) {
        patch.llm_base_url = defaults.base_url;
      }
      if (!form.llm_model || form.llm_model === oldDefaults?.model) {
        patch.llm_model = defaults.model;
      }
    }

    updateForm(patch);
    setPreviousProvider(newProvider);
  }, [config, form.llm_base_url, form.llm_model, previousProvider, updateForm]);

  const dirtyFlags = useMemo(() => {
    if (!config) {
      return {
        ai: false,
        feishu: false,
        notion: false,
        notificationChannels: false,
        integrations: false,
        iwencai: false,
        fred: false,
        twitter: false,
        anySearch: false,
        fuyao: false,
        outboundProxy: false,
        eastmoneyRateLimit: false,
        dataSources: false,
        backup: false,
        marketDaily: false,
        researchBudget: false,
        bot: false,
        adminOps: false,
        adminBot: false,
        admin: false,
      };
    }

    const ai = Boolean(
      (form.llm_provider !== undefined && form.llm_provider !== config.llm_provider) ||
      (form.llm_api_mode !== undefined && form.llm_api_mode !== config.llm_api_mode) ||
      (form.llm_api_version !== undefined && form.llm_api_version !== config.llm_api_version) ||
      (form.llm_base_url !== undefined && form.llm_base_url !== config.llm_base_url) ||
      (form.llm_model !== undefined && form.llm_model !== config.llm_model) ||
      (form.llm_sub_model !== undefined && form.llm_sub_model !== config.llm_sub_model) ||
      (form.llm_simple_tasks !== undefined && form.llm_simple_tasks !== config.llm_simple_tasks) ||
      (form.llm_temperature !== undefined && form.llm_temperature !== config.llm_temperature) ||
      (form.llm_context_length_tokens !== undefined && form.llm_context_length_tokens !== config.llm_context_length_tokens) ||
      (form.llm_api_key && !form.llm_api_key.includes("***") && form.llm_api_key !== config.llm_api_key)
    );

    const feishu = Boolean(
      (form.feishu_enabled !== undefined && form.feishu_enabled !== config.feishu_enabled) ||
      (form.feishu_app_id !== undefined && form.feishu_app_id !== config.feishu_app_id) ||
      (form.feishu_folder_token !== undefined && form.feishu_folder_token !== config.feishu_folder_token) ||
      (form.feishu_wiki_space_id !== undefined && form.feishu_wiki_space_id !== config.feishu_wiki_space_id) ||
      (form.feishu_wiki_daily_review_parent !== undefined && form.feishu_wiki_daily_review_parent !== config.feishu_wiki_daily_review_parent) ||
      (form.feishu_wiki_analysis_parent !== undefined && form.feishu_wiki_analysis_parent !== config.feishu_wiki_analysis_parent) ||
      (form.feishu_daily_review_folder !== undefined && form.feishu_daily_review_folder !== config.feishu_daily_review_folder) ||
      (form.feishu_analysis_folder !== undefined && form.feishu_analysis_folder !== config.feishu_analysis_folder) ||
      (form.feishu_default_receiver !== undefined && form.feishu_default_receiver !== config.feishu_default_receiver) ||
      (form.feishu_app_secret && !form.feishu_app_secret.includes("***") && form.feishu_app_secret !== config.feishu_app_secret)
    );

    const notion = Boolean(
      (form.notion_enabled !== undefined && form.notion_enabled !== config.notion_enabled) ||
      (form.notion_parent_page_id !== undefined && form.notion_parent_page_id !== config.notion_parent_page_id) ||
      (form.notion_database_id !== undefined && form.notion_database_id !== config.notion_database_id) ||
      (form.notion_api_token && !form.notion_api_token.includes("***") && form.notion_api_token !== config.notion_api_token)
    );

    const notificationChannels = Boolean(
      (form.push_auto_enabled !== undefined && form.push_auto_enabled !== config.push_auto_enabled) ||
      (form.push_daily_review_auto !== undefined && form.push_daily_review_auto !== config.push_daily_review_auto) ||
      (form.push_potential_auto !== undefined && form.push_potential_auto !== config.push_potential_auto) ||
      (form.feishu_webhook_url !== undefined && form.feishu_webhook_url !== config.feishu_webhook_url) ||
      (form.wecom_webhook_url !== undefined && form.wecom_webhook_url !== config.wecom_webhook_url) ||
      (form.wxpusher_uids !== undefined && form.wxpusher_uids !== config.wxpusher_uids) ||
      (form.feishu_webhook_secret && !form.feishu_webhook_secret.includes("***") && form.feishu_webhook_secret !== config.feishu_webhook_secret) ||
      (form.wxpusher_app_token && !form.wxpusher_app_token.includes("***") && form.wxpusher_app_token !== config.wxpusher_app_token)
    );

    const iwencai = Boolean(
      (form.iwencai_enabled !== undefined && form.iwencai_enabled !== config.iwencai_enabled) ||
      (form.iwencai_base_url !== undefined && form.iwencai_base_url !== config.iwencai_base_url) ||
      (form.iwencai_api_key && !form.iwencai_api_key.includes("***") && form.iwencai_api_key !== config.iwencai_api_key)
    );

    const fred = Boolean(
      form.fred_api_key && !form.fred_api_key.includes("***") && form.fred_api_key !== config.fred_api_key
    );

    const twitter = Boolean(
      form.twitter_feeds &&
      JSON.stringify(form.twitter_feeds.map((f) => f.trim()).filter(Boolean)) !==
      JSON.stringify((config.twitter_feeds ?? []).map((f) => f.trim()).filter(Boolean))
    );

    const anySearch = Boolean(
      form.anysearch_api_key && !form.anysearch_api_key.includes("***") && form.anysearch_api_key !== config.anysearch_api_key
    );

    const fuyao = Boolean(
      form.fuyao_api_key && !form.fuyao_api_key.includes("***") && form.fuyao_api_key !== config.fuyao_api_key
    );

    const outboundProxy = Boolean(
      (form.outbound_proxy_type !== undefined &&
        form.outbound_proxy_type !== config.outbound_proxy_type) ||
      (form.outbound_proxy_url !== undefined &&
        !form.outbound_proxy_url.includes("***") &&
        form.outbound_proxy_url !== config.outbound_proxy_url) ||
      (form.outbound_proxy_timeout_seconds !== undefined &&
        form.outbound_proxy_timeout_seconds !== config.outbound_proxy_timeout_seconds) ||
      (form.outbound_proxy_retries !== undefined &&
        form.outbound_proxy_retries !== config.outbound_proxy_retries)
    );

    const eastmoneyRateLimit = EASTMONEY_RATE_LIMIT_KEYS.some((key) => {
      const nextValue = form[key];
      const currentValue = config[key];
      return nextValue !== undefined && nextValue !== currentValue;
    });

    const backup = Boolean(
      (form.database_backup_retention_count !== undefined && form.database_backup_retention_count !== config.database_backup_retention_count) ||
      (form.database_backup_include_market_daily !== undefined && form.database_backup_include_market_daily !== config.database_backup_include_market_daily) ||
      (form.market_daily_backup_interval_days !== undefined && form.market_daily_backup_interval_days !== config.market_daily_backup_interval_days) ||
      (form.market_daily_backup_compression_level !== undefined && form.market_daily_backup_compression_level !== config.market_daily_backup_compression_level)
    );

    const marketDaily = Boolean(
      (form.market_daily_bar_refresh_enabled !== undefined && form.market_daily_bar_refresh_enabled !== config.market_daily_bar_refresh_enabled) ||
      (form.market_daily_bar_refresh_poll_seconds !== undefined && form.market_daily_bar_refresh_poll_seconds !== config.market_daily_bar_refresh_poll_seconds) ||
      (form.market_daily_bar_refresh_retry_base_seconds !== undefined && form.market_daily_bar_refresh_retry_base_seconds !== config.market_daily_bar_refresh_retry_base_seconds) ||
      (form.market_daily_observation_retention_days !== undefined && form.market_daily_observation_retention_days !== config.market_daily_observation_retention_days) ||
      (form.market_daily_attempt_retention_days !== undefined && form.market_daily_attempt_retention_days !== config.market_daily_attempt_retention_days)
    );

    const researchBudget = Boolean(
      (form.analysis_llm_timeout_seconds !== undefined && form.analysis_llm_timeout_seconds !== config.analysis_llm_timeout_seconds) ||
      (form.agent_research_timeout_seconds !== undefined && form.agent_research_timeout_seconds !== config.agent_research_timeout_seconds) ||
      (form.industry_chain_research_timeout_seconds !== undefined && form.industry_chain_research_timeout_seconds !== config.industry_chain_research_timeout_seconds) ||
      (form.industry_chain_repair_research_timeout_seconds !== undefined && form.industry_chain_repair_research_timeout_seconds !== config.industry_chain_repair_research_timeout_seconds) ||
      (form.industry_chain_repair_synthesis_timeout_seconds !== undefined && form.industry_chain_repair_synthesis_timeout_seconds !== config.industry_chain_repair_synthesis_timeout_seconds) ||
      (form.industry_chain_max_rounds !== undefined && form.industry_chain_max_rounds !== config.industry_chain_max_rounds) ||
      (form.industry_chain_repair_max_rounds !== undefined && form.industry_chain_repair_max_rounds !== config.industry_chain_repair_max_rounds) ||
      (form.industry_chain_tool_calls_total !== undefined && form.industry_chain_tool_calls_total !== config.industry_chain_tool_calls_total) ||
      (form.industry_chain_repair_tool_calls_total !== undefined && form.industry_chain_repair_tool_calls_total !== config.industry_chain_repair_tool_calls_total) ||
      (form.chat_max_tool_calls_total !== undefined && form.chat_max_tool_calls_total !== config.chat_max_tool_calls_total)
    );

    const bot = Boolean(
      (form.bot_enabled !== undefined && form.bot_enabled !== config.bot_enabled) ||
      (form.bot_command_prefix !== undefined && form.bot_command_prefix !== config.bot_command_prefix) ||
      (form.bot_service_user_id !== undefined && form.bot_service_user_id !== config.bot_service_user_id) ||
      (form.bot_feishu_app_id !== undefined && form.bot_feishu_app_id !== config.bot_feishu_app_id) ||
      (form.bot_rate_limit_requests !== undefined && form.bot_rate_limit_requests !== config.bot_rate_limit_requests) ||
      (form.bot_rate_limit_window !== undefined && form.bot_rate_limit_window !== config.bot_rate_limit_window) ||
      (form.bot_webhook_max_skew_seconds !== undefined && form.bot_webhook_max_skew_seconds !== config.bot_webhook_max_skew_seconds) ||
      (form.bot_event_dedup_ttl_seconds !== undefined && form.bot_event_dedup_ttl_seconds !== config.bot_event_dedup_ttl_seconds) ||
      (form.bot_job_poll_seconds !== undefined && form.bot_job_poll_seconds !== config.bot_job_poll_seconds) ||
      (form.bot_job_lease_seconds !== undefined && form.bot_job_lease_seconds !== config.bot_job_lease_seconds) ||
      (form.bot_job_max_attempts !== undefined && form.bot_job_max_attempts !== config.bot_job_max_attempts) ||
      (form.bot_job_retry_base_seconds !== undefined && form.bot_job_retry_base_seconds !== config.bot_job_retry_base_seconds) ||
      (form.bot_job_worker_concurrency !== undefined && form.bot_job_worker_concurrency !== config.bot_job_worker_concurrency) ||
      (form.bot_batch_concurrency !== undefined && form.bot_batch_concurrency !== config.bot_batch_concurrency) ||
      (form.bot_batch_max_stocks !== undefined && form.bot_batch_max_stocks !== config.bot_batch_max_stocks) ||
      (form.bot_feishu_app_secret && !form.bot_feishu_app_secret.includes("***") && form.bot_feishu_app_secret !== config.bot_feishu_app_secret) ||
      (form.feishu_verification_token && !form.feishu_verification_token.includes("***") && form.feishu_verification_token !== config.feishu_verification_token) ||
      (form.feishu_encrypt_key && !form.feishu_encrypt_key.includes("***") && form.feishu_encrypt_key !== config.feishu_encrypt_key) ||
      (form.bot_admin_users &&
        JSON.stringify(form.bot_admin_users.map((u) => u.trim()).filter(Boolean)) !==
        JSON.stringify((config.bot_admin_users ?? []).map((u) => u.trim()).filter(Boolean)))
    );

    const integrations = feishu || notion || notificationChannels;
    const dataSources = iwencai || fred || twitter || anySearch || fuyao || outboundProxy || eastmoneyRateLimit;
    const adminOps = backup || marketDaily || researchBudget;
    const admin = adminOps || bot;
    const hasUnsavedChanges = Boolean(ai || integrations || dataSources || admin);

    return {
      ai,
      feishu,
      notion,
      notificationChannels,
      integrations,
      iwencai,
      fred,
      twitter,
      anySearch,
      fuyao,
      outboundProxy,
      eastmoneyRateLimit,
      dataSources,
      backup,
      marketDaily,
      researchBudget,
      bot,
      adminOps,
      adminBot: bot,
      admin,
      hasUnsavedChanges,
    };
  }, [config, form]);

  useEffect(() => {
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!dirtyFlags.hasUnsavedChanges) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, [dirtyFlags.hasUnsavedChanges]);

  const handleSaveLlm = useCallback(() => {
    const providerName = form.llm_provider || "openai";
    const selectedDefaults = config?.provider_defaults?.[providerName] as ProviderDefault | undefined;
    if (selectedDefaults?.api_key_required && !form.llm_api_key?.trim()) {
      message.error(`${selectedDefaults.label || providerName} 需要填写 API Key`);
      return;
    }
    const patch: ConfigUpdate = {
      llm_provider: form.llm_provider,
      llm_api_mode: form.llm_api_mode,
      llm_api_version: form.llm_api_version,
      llm_base_url: form.llm_base_url,
      llm_model: form.llm_model,
      llm_sub_model: form.llm_sub_model,
      llm_simple_tasks: form.llm_simple_tasks,
      llm_temperature: form.llm_temperature,
      llm_context_length_tokens: form.llm_context_length_tokens,
    };
    if (form.llm_api_key && !form.llm_api_key.endsWith("***")) {
      patch.llm_api_key = form.llm_api_key;
    }
    saveConfig(patch, "大模型配置已保存");
  }, [config?.provider_defaults, form, saveConfig]);

  const handleSaveFeishu = useCallback(() => {
    const patch: ConfigUpdate = {
      feishu_enabled: form.feishu_enabled,
      feishu_app_id: form.feishu_app_id,
      feishu_folder_token: form.feishu_folder_token,
      feishu_wiki_space_id: form.feishu_wiki_space_id,
      feishu_wiki_daily_review_parent: form.feishu_wiki_daily_review_parent,
      feishu_wiki_analysis_parent: form.feishu_wiki_analysis_parent,
      feishu_daily_review_folder: form.feishu_daily_review_folder,
      feishu_analysis_folder: form.feishu_analysis_folder,
      feishu_default_receiver: form.feishu_default_receiver,
    };
    if (form.feishu_app_secret && !form.feishu_app_secret.endsWith("***")) {
      patch.feishu_app_secret = form.feishu_app_secret;
    }
    saveConfig(patch, "飞书配置已保存");
  }, [form, saveConfig]);

  const handleSaveNotion = useCallback(() => {
    const patch: ConfigUpdate = {
      notion_enabled: form.notion_enabled,
      notion_parent_page_id: form.notion_parent_page_id,
      notion_database_id: form.notion_database_id,
    };
    if (form.notion_api_token && !form.notion_api_token.includes("***")) {
      patch.notion_api_token = form.notion_api_token;
    }
    saveConfig(patch, "Notion 配置已保存");
  }, [form, saveConfig]);

  const handleSaveNotificationChannels = useCallback(() => {
    const patch: ConfigUpdate = {
      push_auto_enabled: form.push_auto_enabled,
      push_daily_review_auto: form.push_daily_review_auto,
      push_potential_auto: form.push_potential_auto,
      feishu_webhook_url: form.feishu_webhook_url,
      wecom_webhook_url: form.wecom_webhook_url,
      wxpusher_uids: form.wxpusher_uids,
    };
    if (form.feishu_webhook_secret && !form.feishu_webhook_secret.includes("***")) {
      patch.feishu_webhook_secret = form.feishu_webhook_secret;
    }
    if (form.wxpusher_app_token && !form.wxpusher_app_token.includes("***")) {
      patch.wxpusher_app_token = form.wxpusher_app_token;
    }
    saveConfig(patch, "通知推送通道配置已保存");
  }, [form, saveConfig]);

  const handleSaveIwencai = useCallback(() => {
    const patch: ConfigUpdate = {
      iwencai_enabled: form.iwencai_enabled,
      iwencai_base_url: form.iwencai_base_url,
    };
    if (form.iwencai_api_key && !form.iwencai_api_key.endsWith("***")) {
      patch.iwencai_api_key = form.iwencai_api_key;
    }
    saveConfig(patch, "问财数据源配置已保存");
  }, [form, saveConfig]);

  const handleSaveTwitter = useCallback(() => {
    const cleanedFeeds = (form.twitter_feeds ?? []).map((feed) => feed.trim()).filter(Boolean);
    saveConfig(
      { twitter_feeds: cleanedFeeds },
      "Twitter 账号配置已保存",
      () => {
        void queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterFeed });
      },
    );
  }, [form.twitter_feeds, queryClient, saveConfig]);

  const handleSaveFred = useCallback(() => {
    const value = (form.fred_api_key ?? "").trim();
    if (value.includes("***") || value === (config?.fred_api_key ?? "")) {
      message.info("没有需要保存的变更");
      return;
    }
    saveConfig({ fred_api_key: value }, "FRED API Key 已保存");
  }, [config?.fred_api_key, form.fred_api_key, saveConfig]);

  const handleSaveAnySearch = useCallback(() => {
    const value = (form.anysearch_api_key ?? "").trim();
    if (!value || value.includes("***")) {
      message.info("没有需要保存的变更");
      return;
    }
    saveConfig(
      { anysearch_api_key: value },
      "AnySearch API Key 已保存",
      () => updateForm({ anysearch_api_key: "" }),
    );
  }, [form.anysearch_api_key, saveConfig, updateForm]);

  const handleSaveDataSourceCredentials = useCallback(() => {
    const value = (form.fuyao_api_key ?? "").trim();
    if (!value || value.includes("***") || value === (config?.fuyao_api_key ?? "")) {
      message.info("没有需要保存的变更");
      return;
    }
    saveConfig({ fuyao_api_key: value }, "fuyao API Key 已保存", () =>
      updateForm({ fuyao_api_key: "" }),
    );
  }, [config?.fuyao_api_key, form.fuyao_api_key, saveConfig, updateForm]);

  const handleSaveOutboundProxy = useCallback(() => {
    const proxyType = form.outbound_proxy_type ?? "none";
    const rawUrl = (form.outbound_proxy_url ?? "").trim();
    // 代理地址按凭证下发，已保存的值会带 ***，此时不覆盖后端原值
    const maskedUrl = rawUrl.includes("***");
    let url = maskedUrl ? (config?.outbound_proxy_url ?? "") : rawUrl;

    if (proxyType === "none") {
      url = "";
    } else {
      if (!maskedUrl && !url) {
        message.error("启用代理后必须填写代理地址");
        return;
      }
      if (maskedUrl && config?.outbound_proxy_type !== proxyType) {
        message.error("切换代理类型后请重新填写代理地址");
        return;
      }
      if (!maskedUrl) {
        const error = validateProxyUrl(url, proxyType);
        if (error) {
          message.error(error);
          return;
        }
        url = normalizeProxyUrl(url, proxyType);
      }
    }

    saveConfig(
      {
        outbound_proxy_type: proxyType,
        outbound_proxy_url: url,
        outbound_proxy_timeout_seconds:
          form.outbound_proxy_timeout_seconds ?? 20,
        outbound_proxy_retries: form.outbound_proxy_retries ?? 2,
      },
      proxyType === "none" ? "出站代理已关闭" : "出站代理配置已保存",
      (updatedConfig) => {
        if (updatedConfig) {
          updateForm({
            outbound_proxy_type: updatedConfig.outbound_proxy_type,
            outbound_proxy_url: updatedConfig.outbound_proxy_url ?? "",
            outbound_proxy_timeout_seconds: updatedConfig.outbound_proxy_timeout_seconds,
            outbound_proxy_retries: updatedConfig.outbound_proxy_retries,
          });
        }
      },
    );
  }, [
    config?.outbound_proxy_type,
    config?.outbound_proxy_url,
    form.outbound_proxy_retries,
    form.outbound_proxy_timeout_seconds,
    form.outbound_proxy_type,
    form.outbound_proxy_url,
    saveConfig,
    updateForm,
  ]);

  const handleSaveEastmoneyRateLimit = useCallback(() => {
    const patch: ConfigUpdate = {};
    EASTMONEY_RATE_LIMIT_KEYS.forEach((key) => {
      const value = form[key];
      if (value !== undefined) {
        patch[key] = value;
      }
    });
    saveConfig(patch, "东财限流与风控配置已保存");
  }, [form, saveConfig]);

  const handleSaveBackupRetention = useCallback(() => {
    saveConfig(
      {
        database_backup_retention_count: form.database_backup_retention_count,
        database_backup_include_market_daily: form.database_backup_include_market_daily,
        market_daily_backup_interval_days: form.market_daily_backup_interval_days,
        market_daily_backup_compression_level: form.market_daily_backup_compression_level,
      },
      "数据库备份设置已保存",
    );
  }, [
    form.database_backup_retention_count,
    form.database_backup_include_market_daily,
    form.market_daily_backup_interval_days,
    form.market_daily_backup_compression_level,
    saveConfig,
  ]);

  const handleSaveResearchBudget = useCallback(() => {
    const patch: ConfigUpdate = {
      analysis_llm_timeout_seconds: form.analysis_llm_timeout_seconds,
      agent_research_timeout_seconds: form.agent_research_timeout_seconds,
      industry_chain_research_timeout_seconds: form.industry_chain_research_timeout_seconds,
      industry_chain_repair_research_timeout_seconds: form.industry_chain_repair_research_timeout_seconds,
      industry_chain_repair_synthesis_timeout_seconds: form.industry_chain_repair_synthesis_timeout_seconds,
      industry_chain_max_rounds: form.industry_chain_max_rounds,
      industry_chain_repair_max_rounds: form.industry_chain_repair_max_rounds,
      industry_chain_tool_calls_total: form.industry_chain_tool_calls_total,
      industry_chain_repair_tool_calls_total: form.industry_chain_repair_tool_calls_total,
      chat_max_tool_calls_total: form.chat_max_tool_calls_total,
    };
    saveConfig(patch, "研究预算与超时已保存");
  }, [form, saveConfig]);

  const handleSaveMarketDailyBars = useCallback(() => {
    saveConfig(
      {
        market_daily_bar_refresh_enabled: form.market_daily_bar_refresh_enabled,
        market_daily_bar_refresh_poll_seconds: form.market_daily_bar_refresh_poll_seconds,
        market_daily_bar_refresh_retry_base_seconds: form.market_daily_bar_refresh_retry_base_seconds,
        market_daily_observation_retention_days: form.market_daily_observation_retention_days,
        market_daily_attempt_retention_days: form.market_daily_attempt_retention_days,
      },
      "市场日行情刷新配置已保存",
    );
  }, [form, saveConfig]);

  const handleSaveBot = useCallback(() => {
    const patch: ConfigUpdate = {
      bot_enabled: form.bot_enabled,
      bot_command_prefix: form.bot_command_prefix,
      bot_service_user_id: form.bot_service_user_id,
      bot_feishu_app_id: form.bot_feishu_app_id,
      bot_rate_limit_requests: form.bot_rate_limit_requests,
      bot_rate_limit_window: form.bot_rate_limit_window,
      bot_webhook_max_skew_seconds: form.bot_webhook_max_skew_seconds,
      bot_event_dedup_ttl_seconds: form.bot_event_dedup_ttl_seconds,
      bot_job_poll_seconds: form.bot_job_poll_seconds,
      bot_job_lease_seconds: form.bot_job_lease_seconds,
      bot_job_max_attempts: form.bot_job_max_attempts,
      bot_job_retry_base_seconds: form.bot_job_retry_base_seconds,
      bot_job_worker_concurrency: form.bot_job_worker_concurrency,
      bot_batch_concurrency: form.bot_batch_concurrency,
      bot_batch_max_stocks: form.bot_batch_max_stocks,
      bot_admin_users: (form.bot_admin_users ?? []).map((userId) => userId.trim()).filter(Boolean),
    };
    if (form.bot_feishu_app_secret && !form.bot_feishu_app_secret.includes("***")) {
      patch.bot_feishu_app_secret = form.bot_feishu_app_secret;
    }
    if (form.feishu_verification_token && !form.feishu_verification_token.includes("***")) {
      patch.feishu_verification_token = form.feishu_verification_token;
    }
    if (form.feishu_encrypt_key && !form.feishu_encrypt_key.includes("***")) {
      patch.feishu_encrypt_key = form.feishu_encrypt_key;
    }
    saveConfig(patch, "Bot 配置已保存");
  }, [form, saveConfig]);

  const handleResetLlm = useCallback(() => {
    if (!config) return;
    updateForm({
      llm_provider: config.llm_provider,
      llm_api_mode: config.llm_api_mode,
      llm_api_version: config.llm_api_version,
      llm_api_key: config.llm_api_key,
      llm_base_url: config.llm_base_url,
      llm_model: config.llm_model,
      llm_sub_model: config.llm_sub_model,
      llm_simple_tasks: config.llm_simple_tasks,
      llm_temperature: config.llm_temperature,
      llm_context_length_tokens: config.llm_context_length_tokens,
    });
    setPreviousProvider(config.llm_provider ?? "");
    message.success("已撤销大模型配置修改");
  }, [config, updateForm]);

  const handleResetFeishu = useCallback(() => {
    if (!config) return;
    updateForm({
      feishu_enabled: config.feishu_enabled,
      feishu_app_id: config.feishu_app_id,
      feishu_app_secret: config.feishu_app_secret,
      feishu_folder_token: config.feishu_folder_token,
      feishu_wiki_space_id: config.feishu_wiki_space_id,
      feishu_wiki_daily_review_parent: config.feishu_wiki_daily_review_parent,
      feishu_wiki_analysis_parent: config.feishu_wiki_analysis_parent,
      feishu_daily_review_folder: config.feishu_daily_review_folder,
      feishu_analysis_folder: config.feishu_analysis_folder,
      feishu_default_receiver: config.feishu_default_receiver,
    });
    message.success("已撤销飞书推送配置修改");
  }, [config, updateForm]);

  const handleResetNotion = useCallback(() => {
    if (!config) return;
    updateForm({
      notion_enabled: config.notion_enabled,
      notion_api_token: config.notion_api_token,
      notion_parent_page_id: config.notion_parent_page_id,
      notion_database_id: config.notion_database_id,
    });
    message.success("已撤销 Notion 配置修改");
  }, [config, updateForm]);

  const handleResetNotificationChannels = useCallback(() => {
    if (!config) return;
    updateForm({
      push_auto_enabled: config.push_auto_enabled,
      push_daily_review_auto: config.push_daily_review_auto,
      push_potential_auto: config.push_potential_auto,
      feishu_webhook_url: config.feishu_webhook_url,
      feishu_webhook_secret: config.feishu_webhook_secret,
      wecom_webhook_url: config.wecom_webhook_url,
      wxpusher_app_token: config.wxpusher_app_token,
      wxpusher_uids: config.wxpusher_uids,
    });
    message.success("已撤销通知推送通道配置修改");
  }, [config, updateForm]);

  const handleResetIwencai = useCallback(() => {
    if (!config) return;
    updateForm({
      iwencai_enabled: config.iwencai_enabled,
      iwencai_base_url: config.iwencai_base_url,
      iwencai_api_key: config.iwencai_api_key,
    });
    message.success("已撤销问财配置修改");
  }, [config, updateForm]);

  const handleResetTwitter = useCallback(() => {
    if (!config) return;
    updateForm({
      twitter_feeds: config.twitter_feeds,
    });
    message.success("已撤销 Twitter 账号修改");
  }, [config, updateForm]);

  const handleResetFred = useCallback(() => {
    if (!config) return;
    updateForm({
      fred_api_key: config.fred_api_key,
    });
    message.success("已撤销 FRED 配置修改");
  }, [config, updateForm]);

  const handleResetAnySearch = useCallback(() => {
    updateForm({
      anysearch_api_key: "",
    });
    message.success("已撤销 AnySearch 修改");
  }, [updateForm]);

  const handleResetFuyao = useCallback(() => {
    if (!config) return;
    updateForm({
      fuyao_api_key: config.fuyao_api_key,
    });
    message.success("已撤销 fuyao 凭证修改");
  }, [config, updateForm]);

  const handleTestOutboundProxy = useCallback(() => {
    testOutboundProxyMutate(undefined, {
      onSuccess: (result) => {
        setOutboundProxyTestResult(result);
        if (result.ok) {
          message.success(`代理可用（${result.latency_ms}ms）`);
        } else {
          message.warning(`代理不可用：${result.message}`);
        }
      },
      onError: (error: Error) => message.error(`连通性测试失败: ${error.message}`),
    });
  }, [testOutboundProxyMutate]);

  const handleResetOutboundProxy = useCallback(() => {
    if (!config) return;
    updateForm({
      outbound_proxy_type: config.outbound_proxy_type,
      outbound_proxy_url: config.outbound_proxy_url,
      outbound_proxy_timeout_seconds: config.outbound_proxy_timeout_seconds,
      outbound_proxy_retries: config.outbound_proxy_retries,
    });
    message.success("已撤销出站代理修改");
  }, [config, updateForm]);

  const handleResetEastmoneyRateLimit = useCallback(() => {
    if (!config) return;
    const patch: ConfigUpdate = {};
    EASTMONEY_RATE_LIMIT_KEYS.forEach((key) => {
      patch[key] = config[key] as number;
    });
    updateForm(patch);
    message.success("已撤销东财限流配置修改");
  }, [config, updateForm]);

  const handleResetBackupRetention = useCallback(() => {
    if (!config) return;
    updateForm({
      database_backup_retention_count: config.database_backup_retention_count,
      database_backup_include_market_daily: config.database_backup_include_market_daily,
      market_daily_backup_interval_days: config.market_daily_backup_interval_days,
      market_daily_backup_compression_level: config.market_daily_backup_compression_level,
    });
    message.success("已撤销备份配置修改");
  }, [config, updateForm]);

  const handleResetMarketDailyBars = useCallback(() => {
    if (!config) return;
    updateForm({
      market_daily_bar_refresh_enabled: config.market_daily_bar_refresh_enabled,
      market_daily_bar_refresh_poll_seconds: config.market_daily_bar_refresh_poll_seconds,
      market_daily_bar_refresh_retry_base_seconds: config.market_daily_bar_refresh_retry_base_seconds,
      market_daily_observation_retention_days: config.market_daily_observation_retention_days,
      market_daily_attempt_retention_days: config.market_daily_attempt_retention_days,
    });
    message.success("已撤销日行情刷新配置修改");
  }, [config, updateForm]);

  const handleResetResearchBudget = useCallback(() => {
    if (!config) return;
    updateForm({
      analysis_llm_timeout_seconds: config.analysis_llm_timeout_seconds,
      agent_research_timeout_seconds: config.agent_research_timeout_seconds,
      industry_chain_research_timeout_seconds: config.industry_chain_research_timeout_seconds,
      industry_chain_repair_research_timeout_seconds: config.industry_chain_repair_research_timeout_seconds,
      industry_chain_repair_synthesis_timeout_seconds: config.industry_chain_repair_synthesis_timeout_seconds,
      industry_chain_max_rounds: config.industry_chain_max_rounds,
      industry_chain_repair_max_rounds: config.industry_chain_repair_max_rounds,
      industry_chain_tool_calls_total: config.industry_chain_tool_calls_total,
      industry_chain_repair_tool_calls_total: config.industry_chain_repair_tool_calls_total,
      chat_max_tool_calls_total: config.chat_max_tool_calls_total,
    });
    message.success("已撤销研究预算修改");
  }, [config, updateForm]);

  const handleResetBot = useCallback(() => {
    if (!config) return;
    updateForm({
      bot_enabled: config.bot_enabled,
      bot_command_prefix: config.bot_command_prefix,
      bot_service_user_id: config.bot_service_user_id,
      bot_feishu_app_id: config.bot_feishu_app_id,
      bot_feishu_app_secret: config.bot_feishu_app_secret,
      feishu_verification_token: config.feishu_verification_token,
      feishu_encrypt_key: config.feishu_encrypt_key,
      bot_rate_limit_requests: config.bot_rate_limit_requests,
      bot_rate_limit_window: config.bot_rate_limit_window,
      bot_webhook_max_skew_seconds: config.bot_webhook_max_skew_seconds,
      bot_event_dedup_ttl_seconds: config.bot_event_dedup_ttl_seconds,
      bot_job_poll_seconds: config.bot_job_poll_seconds,
      bot_job_lease_seconds: config.bot_job_lease_seconds,
      bot_job_max_attempts: config.bot_job_max_attempts,
      bot_job_retry_base_seconds: config.bot_job_retry_base_seconds,
      bot_job_worker_concurrency: config.bot_job_worker_concurrency,
      bot_batch_concurrency: config.bot_batch_concurrency,
      bot_batch_max_stocks: config.bot_batch_max_stocks,
      bot_admin_users: config.bot_admin_users,
    });
    message.success("已撤销 Bot 配置修改");
  }, [config, updateForm]);

  if (!config) {
    return (
      <div style={pageContainerStyle}>
        <SectionDataState
          isLoading={isLoading}
          error={error}
          onRetry={() => refetch()}
          isEmpty={!isLoading && !error && !config}
          emptyText="暂无配置数据"
          errorTitle="系统配置加载失败"
          minHeight={320}
          skeletonRows={8}
        >
          {null}
        </SectionDataState>
      </div>
    );
  }

  const sectionTitleStyle = {
    margin: "24px 0 12px",
    color: colors.textPrimary,
    fontSize: "var(--c-font-lg)",
    fontWeight: "var(--c-weight-semibold)",
  };

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h2 style={pageTitleStyle}>
              <RobotOutlined style={{ marginRight: 8 }} />
              系统配置
            </h2>
            <p style={pageDescriptionStyle}>
              配置 AI 模型思考引擎、行情与资讯数据输入源，以及研报外部协同导出渠道。
              个人配置（大模型、问财 Key、飞书私有空间）独立生效；系统公共数据源与运维策略由管理员统一维护。
              {user && (
                <span style={{ marginLeft: 8, color: colors.textMuted }}>
                  当前账号：<strong style={{ color: colors.textSecondary }}>{user.username}</strong>
                  {user.is_admin && <Tag style={{ ...semanticTagStyle("warning"), marginLeft: 6 }}>管理员</Tag>}
                </span>
              )}
            </p>
          </div>

          {dirtyFlags.hasUnsavedChanges && (
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 4 }}>
              <Tag color="warning" style={{ padding: "4px 10px", fontSize: "var(--c-font-sm)", display: "inline-flex", alignItems: "center", gap: 6, margin: 0 }}>
                <span
                  style={{
                    display: "inline-block",
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    backgroundColor: "currentColor",
                  }}
                />
                检测到未保存配置变更
              </Tag>
              <Popconfirm
                title="撤销未保存的全部修改？"
                description="将还原至上次保存的配置值，当前未保存的输入将被清空。"
                onConfirm={handleResetAllUnsaved}
                okText="确认撤销"
                cancelText="继续编辑"
              >
                <Button size="small" icon={<UndoOutlined />}>
                  还原所有修改
                </Button>
              </Popconfirm>
            </div>
          )}
        </div>
      </div>

      <ResponsiveSectionNav
        items={[
          {
            key: "account",
            label: "账号与安全",
            group: "个人配置",
            children: (
              <section aria-labelledby="account-settings-title">
                <h3 id="account-settings-title" style={sectionTitleStyle}>账号与安全</h3>
                <ChangePasswordCard />
                <SystemUpdateCard />
              </section>
            ),
          },
          {
            key: "ai",
            label: (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                AI 模型配置
                {dirtyFlags.ai && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: "var(--c-warning, #faad14)",
                    }}
                    title="存在未保存的修改"
                  />
                )}
              </span>
            ),
            group: "个人配置",
            children: (
              <Suspense fallback={<SettingsSectionFallback />}>
                <AiSettingsSection
                  form={form}
                  onChange={updateForm}
                  isSaving={isSaving}
                  sectionTitleStyle={sectionTitleStyle}
                  providerDefaults={config.provider_defaults || {}}
                  onSave={handleSaveLlm}
                  onProviderChange={handleProviderChange}
                  isDirty={dirtyFlags.ai}
                  onReset={handleResetLlm}
                />
              </Suspense>
            ),
          },
          {
            key: "data-sources",
            label: (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                数据源管理
                {dirtyFlags.dataSources && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: "var(--c-warning, #faad14)",
                    }}
                    title="存在未保存的修改"
                  />
                )}
              </span>
            ),
            group: "个人配置",
            children: (
              <Suspense fallback={<SettingsSectionFallback />}>
                <DataSourcesSettingsSection
                  form={form}
                  onChange={updateForm}
                  isSaving={isSaving}
                  isAdmin={isAdmin}
                  sectionTitleStyle={sectionTitleStyle}
                  onSaveIwencai={handleSaveIwencai}
                  onSaveTwitter={handleSaveTwitter}
                  onSaveFred={handleSaveFred}
                  anySearchConfigured={Boolean(config.anysearch_api_key)}
                  onSaveAnySearch={handleSaveAnySearch}
                  fuyaoConfigured={Boolean(config.fuyao_api_key)}
                  onSaveDataSourceCredentials={handleSaveDataSourceCredentials}
                  onSaveOutboundProxy={handleSaveOutboundProxy}
                  onSaveEastmoneyRateLimit={handleSaveEastmoneyRateLimit}
                  onTestOutboundProxy={handleTestOutboundProxy}
                  isTestingOutboundProxy={isTestingOutboundProxy}
                  outboundProxyTestResult={outboundProxyTestResult}
                  onResetIwencai={handleResetIwencai}
                  onResetTwitter={handleResetTwitter}
                  onResetFred={handleResetFred}
                  onResetAnySearch={handleResetAnySearch}
                  onResetFuyao={handleResetFuyao}
                  onResetOutboundProxy={handleResetOutboundProxy}
                  onResetEastmoneyRateLimit={handleResetEastmoneyRateLimit}
                  dirtyCards={{
                    iwencai: dirtyFlags.iwencai,
                    fred: dirtyFlags.fred,
                    twitter: dirtyFlags.twitter,
                    anySearch: dirtyFlags.anySearch,
                    fuyao: dirtyFlags.fuyao,
                    outboundProxy: dirtyFlags.outboundProxy,
                    eastmoneyRateLimit: dirtyFlags.eastmoneyRateLimit,
                  }}
                />
              </Suspense>
            ),
          },
          {
            key: "integrations",
            label: (
              <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                协同与自动推送
                {dirtyFlags.integrations && (
                  <span
                    style={{
                      display: "inline-block",
                      width: 6,
                      height: 6,
                      borderRadius: "50%",
                      backgroundColor: "var(--c-warning, #faad14)",
                    }}
                    title="存在未保存的修改"
                  />
                )}
              </span>
            ),
            group: "个人配置",
            children: (
              <Suspense fallback={<SettingsSectionFallback />}>
                <IntegrationsSettingsSection
                  form={form}
                  onChange={updateForm}
                  isSaving={isSaving}
                  sectionTitleStyle={sectionTitleStyle}
                  onSaveFeishu={handleSaveFeishu}
                  onSaveNotion={handleSaveNotion}
                  onSaveNotificationChannels={handleSaveNotificationChannels}
                  onResetFeishu={handleResetFeishu}
                  onResetNotion={handleResetNotion}
                  onResetNotificationChannels={handleResetNotificationChannels}
                  dirtyCards={{
                    feishu: dirtyFlags.feishu,
                    notion: dirtyFlags.notion,
                    notificationChannels: dirtyFlags.notificationChannels,
                  }}
                />
              </Suspense>
            ),
          },
          ...(isAdmin ? [
            {
              key: "admin",
              label: (
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  管理员工具
                  {dirtyFlags.admin && (
                    <span
                      style={{
                        display: "inline-block",
                        width: 6,
                        height: 6,
                        borderRadius: "50%",
                        backgroundColor: "var(--c-warning, #faad14)",
                      }}
                      title="存在未保存的修改"
                    />
                  )}
                </span>
              ),
              group: "系统管理",
              children: (
                <Suspense fallback={<SettingsSectionFallback />}>
                  <AdminSettingsSection
                    form={form}
                    onChange={updateForm}
                    isSaving={isSaving}
                    sectionTitleStyle={sectionTitleStyle}
                    onSaveBot={handleSaveBot}
                    onSaveResearchBudget={handleSaveResearchBudget}
                    onSaveMarketDailyBars={handleSaveMarketDailyBars}
                    onSaveBackupRetention={handleSaveBackupRetention}
                    onResetBot={handleResetBot}
                    onResetResearchBudget={handleResetResearchBudget}
                    onResetMarketDailyBars={handleResetMarketDailyBars}
                    onResetBackupRetention={handleResetBackupRetention}
                    dirtyCards={{
                      backup: dirtyFlags.backup,
                      marketDaily: dirtyFlags.marketDaily,
                      researchBudget: dirtyFlags.researchBudget,
                      bot: dirtyFlags.bot,
                    }}
                  />
                </Suspense>
              ),
            },
          ] : []),
        ]}
        activeKey={activeSection}
        onChange={setActiveSection}
        ariaLabel="系统配置分类"
        desktopMode="rail"
      />
    </div>
  );
}
