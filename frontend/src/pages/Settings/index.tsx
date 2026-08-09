import { useCallback, useEffect, useState } from "react";
import { RobotOutlined } from "@ant-design/icons";
import { Col, message, Row, Tag } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import {
  useChatCapabilities,
  useChatCapabilityAvailability,
  useConfig,
} from "../../api/queries";
import { queryKeys } from "../../api/queryKeys";
import AdminResetCard from "../../components/AdminResetCard";
import ChangePasswordCard from "../../components/ChangePasswordCard";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useColors, useStyles } from "../../styles/ui";
import type { ConfigUpdate, ProviderDefault } from "../../types/settings";
import {
  BotConfigCard,
  DataSourceCookiesCard,
  FeishuConfigCard,
  IwencaiConfigCard,
  LlmConfigCard,
  NotionConfigCard,
  ProviderDefaultsCard,
  TwitterConfigCard,
} from "./ConfigCards";
import BotJobManagerCard from "./BotJobManagerCard";
import InviteManagerCard from "./InviteManagerCard";
import SkillAgentConfigCard from "./SkillAgentConfigCard";
import { useConfigSectionSave } from "./useConfigSectionSave";

export default function SettingsPage() {
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const colors = useColors();
  const { data: config, isLoading, error, refetch } = useConfig();
  const {
    data: chatCapabilities,
    isLoading: isLoadingChatCapabilities,
    error: chatCapabilitiesError,
    refetch: refetchChatCapabilities,
  } = useChatCapabilities();
  const {
    data: chatCapabilityAvailability,
    isFetching: isCheckingChatCapabilities,
    refetch: refetchChatCapabilityAvailability,
  } = useChatCapabilityAvailability();
  const { save: saveConfig, isSaving } = useConfigSectionSave();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const isAdmin = Boolean(config?.is_admin);

  const [form, setForm] = useState<ConfigUpdate>({});
  const [initializedUserId, setInitializedUserId] = useState<number | null>(null);
  const [previousProvider, setPreviousProvider] = useState("");

  useEffect(() => {
    if (!config || !user || initializedUserId === user.id) return;
    setForm({
      llm_provider: config.llm_provider,
      llm_api_mode: config.llm_api_mode,
      llm_api_version: config.llm_api_version,
      llm_api_key: config.llm_api_key,
      llm_base_url: config.llm_base_url,
      llm_model: config.llm_model,
      llm_temperature: config.llm_temperature,
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
      notion_enabled: config.notion_enabled,
      notion_parent_page_id: config.notion_parent_page_id,
      notion_database_id: config.notion_database_id,
      iwencai_enabled: config.iwencai_enabled,
      iwencai_base_url: config.iwencai_base_url,
      iwencai_api_key: config.iwencai_api_key,
      disabled_chat_skills: config.disabled_chat_skills,
      disabled_chat_agents: config.disabled_chat_agents,
      twitter_feeds: config.twitter_feeds,
      eastmoney_cookie: config.eastmoney_cookie,
      baidu_cookie: config.baidu_cookie,
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
    setPreviousProvider(config.llm_provider);
    setInitializedUserId(user.id);
  }, [config, initializedUserId, user]);

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

  const handleSaveLlm = useCallback(() => {
    const patch: ConfigUpdate = {
      llm_provider: form.llm_provider,
      llm_api_mode: form.llm_api_mode,
      llm_api_version: form.llm_api_version,
      llm_base_url: form.llm_base_url,
      llm_model: form.llm_model,
      llm_temperature: form.llm_temperature,
    };
    if (form.llm_api_key && !form.llm_api_key.endsWith("***")) {
      patch.llm_api_key = form.llm_api_key;
    }
    saveConfig(patch, "大模型配置已保存");
  }, [form, saveConfig]);

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
    saveConfig(
      {
        notion_enabled: form.notion_enabled,
        notion_parent_page_id: form.notion_parent_page_id,
        notion_database_id: form.notion_database_id,
      },
      "Notion 配置已保存",
    );
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

  const handleSaveChatCapabilities = useCallback(() => {
    saveConfig(
      {
        disabled_chat_skills: form.disabled_chat_skills ?? [],
        disabled_chat_agents: form.disabled_chat_agents ?? [],
      },
      "Skill 与 Agent 配置已保存",
      () => {
        void refetchChatCapabilityAvailability();
      },
    );
  }, [
    form.disabled_chat_agents,
    form.disabled_chat_skills,
    refetchChatCapabilityAvailability,
    saveConfig,
  ]);

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

  const handleSaveDataSourceCookies = useCallback(() => {
    const patch: ConfigUpdate = {};
    if (form.eastmoney_cookie && !form.eastmoney_cookie.endsWith("***")) {
      patch.eastmoney_cookie = form.eastmoney_cookie;
    }
    if (form.baidu_cookie && !form.baidu_cookie.endsWith("***")) {
      patch.baidu_cookie = form.baidu_cookie;
    }
    if (Object.keys(patch).length === 0) {
      message.info("没有需要保存的变更");
      return;
    }
    saveConfig(patch, "数据源 Cookie 配置已保存");
  }, [form.baidu_cookie, form.eastmoney_cookie, saveConfig]);

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

  const cardProps = {
    form,
    onChange: updateForm,
    isSaving,
  };
  const sectionTitleStyle = {
    margin: "24px 0 12px",
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: 600,
  };

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <h2 style={pageTitleStyle}>
          <RobotOutlined style={{ marginRight: 8 }} />
          系统配置
        </h2>
        <p style={pageDescriptionStyle}>
          大模型、飞书、Notion、问财等为<strong>每账号独立的私密配置</strong>，仅对当前登录用户生效；
          修改后即时生效无需重启。
          {user && (
            <span style={{ marginLeft: 8, color: colors.textMuted }}>
              当前账号：<strong style={{ color: colors.textSecondary }}>{user.username}</strong>
              {user.is_admin && <Tag color="gold" style={{ marginLeft: 6 }}>管理员</Tag>}
            </span>
          )}
        </p>
      </div>

      <section aria-labelledby="account-settings-title">
        <h3 id="account-settings-title" style={sectionTitleStyle}>账号与安全</h3>
        <ChangePasswordCard />
      </section>

      <section aria-labelledby="ai-settings-title">
        <h3 id="ai-settings-title" style={sectionTitleStyle}>AI 配置</h3>
        <LlmConfigCard
          {...cardProps}
          providerDefaults={config.provider_defaults || {}}
          onSave={handleSaveLlm}
          onProviderChange={handleProviderChange}
        />
        <SkillAgentConfigCard
          capabilities={chatCapabilities}
          availability={chatCapabilityAvailability}
          disabledSkillNames={form.disabled_chat_skills ?? []}
          disabledAgentNames={form.disabled_chat_agents ?? []}
          onChange={updateForm}
          onSave={handleSaveChatCapabilities}
          isSaving={isSaving}
          isLoading={isLoadingChatCapabilities}
          error={chatCapabilitiesError}
          onRetry={() => refetchChatCapabilities()}
          isCheckingAvailability={isCheckingChatCapabilities}
          onCheckAvailability={() => refetchChatCapabilityAvailability()}
        />
        <ProviderDefaultsCard providerDefaults={config.provider_defaults || {}} />
      </section>

      <section aria-labelledby="integration-settings-title">
        <h3 id="integration-settings-title" style={sectionTitleStyle}>内容集成</h3>
        <FeishuConfigCard {...cardProps} onSave={handleSaveFeishu} />
        <Row gutter={[16, 0]}>
          <Col xs={24} lg={12}>
            <NotionConfigCard {...cardProps} onSave={handleSaveNotion} />
          </Col>
          <Col xs={24} lg={12}>
            <IwencaiConfigCard {...cardProps} onSave={handleSaveIwencai} />
          </Col>
        </Row>
      </section>

      {isAdmin && (
        <section aria-labelledby="data-source-settings-title">
          <h3 id="data-source-settings-title" style={sectionTitleStyle}>数据源管理</h3>
          <Row gutter={[16, 0]}>
            <Col xs={24} lg={12}>
              <TwitterConfigCard {...cardProps} onSave={handleSaveTwitter} />
            </Col>
            <Col xs={24} lg={12}>
              <DataSourceCookiesCard {...cardProps} onSave={handleSaveDataSourceCookies} />
            </Col>
          </Row>
        </section>
      )}

      {isAdmin && (
        <section aria-labelledby="admin-settings-title">
          <h3 id="admin-settings-title" style={sectionTitleStyle}>管理员工具</h3>
          <BotConfigCard {...cardProps} onSave={handleSaveBot} />
          <BotJobManagerCard />
          <InviteManagerCard />
          <AdminResetCard />
        </section>
      )}
    </div>
  );
}
