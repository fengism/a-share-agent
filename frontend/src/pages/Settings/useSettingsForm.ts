/**
 * 设置页表单状态与卡片动作。
 *
 * 把 `index.tsx` 里的状态、脏检查、保存/撤销编排收敛到一处：
 * - 表单初始化直接从 `ConfigData` 派生，新增字段无需改动；
 * - 卡片脏标记与保存/撤销由 `cardSpecs` 声明驱动；
 * - 对外暴露统一的 `cards.save(key)` / `cards.reset(key)` / `cards.dirty`，
 *   避免 section 组件层层透传十几个回调。
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { message } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useAuthStore } from "../../store/authStore";
import type { ConfigData, ConfigUpdate, ProviderDefault } from "../../types/settings";
import { normalizeProxyUrl, validateProxyUrl } from "./ConfigCards";
import {
  CARD_KEYS,
  CARD_SPECS,
  buildCardPatch,
  buildCardReset,
  isCardDirty,
  isMaskedValue,
  type CardKey,
} from "./cardSpecs";
import { PROVIDER_MODEL_PAIRS } from "./llmModelPairs";

export type ConfigSave = (
  patch: ConfigUpdate,
  successMessage: string,
  afterSuccess?: (data?: ConfigData) => void,
) => void;

export interface SettingsCards {
  /**
   * 保存单张卡片（内部按卡片分派校验/归一化逻辑）。
   *
   * `overrides` 用于卡片自身的"一键切换"动作：需要发送 `buildCardPatch` 不会生成的字段
   * （例如清空密钥字段的空串），与卡片补丁合并后提交。
   */
  save: (key: CardKey, overrides?: ConfigUpdate) => void;
  /** 撤销单张卡片的未保存修改。 */
  reset: (key: CardKey) => void;
  /** 各卡片是否有未保存修改。 */
  dirty: Record<CardKey, boolean>;
  isSaving: boolean;
}

export interface DirtyFlags {
  ai: boolean;
  feishu: boolean;
  notion: boolean;
  notificationChannels: boolean;
  integrations: boolean;
  iwencai: boolean;
  fred: boolean;
  twitter: boolean;
  anySearch: boolean;
  fuyao: boolean;
  outboundProxy: boolean;
  eastmoneyRateLimit: boolean;
  dataSources: boolean;
  backup: boolean;
  marketDaily: boolean;
  researchBudget: boolean;
  scheduledTasks: boolean;
  bot: boolean;
  adminOps: boolean;
  adminBot: boolean;
  admin: boolean;
  hasUnsavedChanges: boolean;
}

function normalizeFeeds(feeds: string[] | undefined): string[] {
  return (feeds ?? []).map((feed) => feed.trim()).filter(Boolean);
}

function feedsDirty(form: ConfigUpdate, config: ConfigData): boolean {
  return (
    JSON.stringify(normalizeFeeds(form.twitter_feeds)) !==
    JSON.stringify(normalizeFeeds(config.twitter_feeds))
  );
}

function normalizeAdminUsers(users: string[] | undefined): string[] {
  return (users ?? []).map((userId) => userId.trim()).filter(Boolean);
}

function adminUsersDirty(form: ConfigUpdate, config: ConfigData): boolean {
  return (
    JSON.stringify(normalizeAdminUsers(form.bot_admin_users)) !==
    JSON.stringify(normalizeAdminUsers(config.bot_admin_users))
  );
}

export function useSettingsForm(
  config: ConfigData | undefined,
  saveConfig: ConfigSave,
  isSaving: boolean,
) {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);

  const [form, setForm] = useState<ConfigUpdate>({});
  const [initializedUserId, setInitializedUserId] = useState<number | null>(null);
  const [previousProvider, setPreviousProvider] = useState("");

  const buildInitialForm = useCallback((cfg: ConfigData | undefined): ConfigUpdate => {
    if (!cfg) return {};
    // 表单字段与生效配置一一对应（由 ConfigData 派生），无需逐字段手写。
    const values = Object.fromEntries(
      Object.entries(cfg).filter(
        ([key]) => !["provider_defaults", "is_admin", "inherited_keys"].includes(key),
      ),
    ) as ConfigUpdate;
    // AnySearch 采用“粘贴新 Key 即替换”的交互，初始化不回填掩码值。
    // 继承管理员 Key 的私密字段（如 llm_api_key）不回填掩码值，
    // 保持输入框留空以展示「留空即沿用管理员配置」placeholder 并符合「留空=继承」交互。
    const inheritedApiKey = cfg.inherited_keys?.includes("llm_api_key");
    return {
      ...values,
      anysearch_api_key: "",
      ...(inheritedApiKey ? { llm_api_key: "" } : {}),
    };
  }, []);

  useEffect(() => {
    if (!config || !user || initializedUserId === user.id) return;
    setForm(buildInitialForm(config));
    setPreviousProvider(config.llm_provider);
    setInitializedUserId(user.id);
  }, [buildInitialForm, config, initializedUserId, user]);

  const updateForm = useCallback((patch: ConfigUpdate) => {
    setForm((previous) => ({ ...previous, ...patch }));
  }, []);

  const handleResetAllUnsaved = useCallback(() => {
    if (!config) return;
    setForm(buildInitialForm(config));
    setPreviousProvider(config.llm_provider);
    message.success("已撤销所有未保存的修改");
  }, [buildInitialForm, config]);

  const handleProviderChange = useCallback(
    (newProvider: string) => {
      const defaults = config?.provider_defaults?.[newProvider] as ProviderDefault | undefined;
      const oldDefaults = config?.provider_defaults?.[previousProvider] as ProviderDefault | undefined;
      const pair = PROVIDER_MODEL_PAIRS[newProvider];
      const oldPair = PROVIDER_MODEL_PAIRS[previousProvider];
      const patch: ConfigUpdate = { llm_provider: newProvider };

      if (defaults) {
        patch.llm_api_mode = defaults.api_mode;
        patch.llm_api_version = defaults.api_version || "";
        if (!form.llm_base_url || form.llm_base_url === oldDefaults?.base_url) {
          patch.llm_base_url = defaults.base_url;
        }
        if (!form.llm_model || form.llm_model === oldDefaults?.model || form.llm_model === oldPair?.main) {
          patch.llm_model = pair?.main || defaults.model;
        }
        if (!form.llm_sub_model || form.llm_sub_model === oldPair?.sub) {
          patch.llm_sub_model = pair?.sub || "";
        }
      }

      updateForm(patch);
      setPreviousProvider(newProvider);
    },
    [config, form.llm_base_url, form.llm_model, form.llm_sub_model, previousProvider, updateForm],
  );

  // 卡片级脏标记：由声明式 spec 派生，仅数组字段需要归一化后比较。
  const cardDirty = useMemo(() => {
    const dirty = {} as Record<CardKey, boolean>;
    for (const key of CARD_KEYS) {
      dirty[key] = config ? isCardDirty(form, config, CARD_SPECS[key]) : false;
    }
    if (config) {
      dirty.twitter = feedsDirty(form, config);
      dirty.bot = dirty.bot || adminUsersDirty(form, config);
    }
    return dirty;
  }, [config, form]);

  const dirtyFlags = useMemo<DirtyFlags>(() => {
    const ai = cardDirty.llm;
    const integrations = cardDirty.feishu || cardDirty.notion || cardDirty.notificationChannels;
    const dataSources =
      cardDirty.iwencai ||
      cardDirty.fred ||
      cardDirty.twitter ||
      cardDirty.anysearch ||
      cardDirty.fuyao ||
      cardDirty.outboundProxy ||
      cardDirty.eastmoneyRateLimit;
    const adminOps =
      cardDirty.backup ||
      cardDirty.marketDaily ||
      cardDirty.researchBudget ||
      cardDirty.scheduledTasks;
    const admin = adminOps || cardDirty.bot;

    return {
      ai,
      feishu: cardDirty.feishu,
      notion: cardDirty.notion,
      notificationChannels: cardDirty.notificationChannels,
      integrations,
      iwencai: cardDirty.iwencai,
      fred: cardDirty.fred,
      twitter: cardDirty.twitter,
      anySearch: cardDirty.anysearch,
      fuyao: cardDirty.fuyao,
      outboundProxy: cardDirty.outboundProxy,
      eastmoneyRateLimit: cardDirty.eastmoneyRateLimit,
      dataSources,
      backup: cardDirty.backup,
      marketDaily: cardDirty.marketDaily,
      researchBudget: cardDirty.researchBudget,
      scheduledTasks: cardDirty.scheduledTasks,
      bot: cardDirty.bot,
      adminOps,
      adminBot: cardDirty.bot,
      admin,
      hasUnsavedChanges: Boolean(ai || integrations || dataSources || admin),
    };
  }, [cardDirty]);

  const cards = useMemo<SettingsCards>(() => {
    const save = (key: CardKey, overrides?: ConfigUpdate) => {
      switch (key) {
        case "llm": {
          // 传 config：继承字段（端点/凭据）未改动则不提交，避免静默钉住管理员配置
          const patch = { ...buildCardPatch(form, CARD_SPECS.llm, config), ...overrides };
          // 一键回退到管理员配置时端点为继承值，Key 由管理员提供，不该被本地校验拦住
          const revertingToAdminConfig =
            overrides?.llm_provider === "" && overrides?.llm_base_url === "";
          const providerName = (patch.llm_provider || form.llm_provider || "openai") as string;
          const selectedDefaults = config?.provider_defaults?.[providerName] as
            | ProviderDefault
            | undefined;

          // 是否正在沿用管理员端点
          const isInheritingEndpoint =
            revertingToAdminConfig
            || (!patch.llm_provider
              && !patch.llm_base_url
              && Boolean(config?.inherited_keys?.includes("llm_provider"))
              && Boolean(config?.inherited_keys?.includes("llm_base_url")));

          // 是否沿用管理员的 Key
          const isInheritingKey =
            isInheritingEndpoint && Boolean(config?.inherited_keys?.includes("llm_api_key"));

          // 用户在本次保存中是否有提供新 Key、新 URL
          const hasNewKey = Boolean(typeof patch.llm_api_key === "string" && patch.llm_api_key.trim());
          const hasNewUrl = Boolean(typeof patch.llm_base_url === "string" && patch.llm_base_url.trim());
          const requiresKey = selectedDefaults?.api_key_required !== false;

          // 简化规则（普通用户）：
          // 1. 如果用户要修改 URL 或 Key，必须同时都改（不能只设置 Key 不改 URL；也不能只改 URL 不设 Key）
          // 2. 不改 URL 和 Key 的情况下，可以自由修改温度系数（llm_temperature）和模型（llm_model）
          if (!revertingToAdminConfig && !config?.is_admin) {
            // 不能只设置 Key 而不修改 Base URL
            if (hasNewKey && !hasNewUrl) {
              const currentHasPersonalUrl =
                !config?.inherited_keys?.includes("llm_base_url") && Boolean(form.llm_base_url);
              if (!currentHasPersonalUrl) {
                message.error("不能只设置 API Key，自定义端点需同时配置 Base URL 与 API Key");
                return;
              }
            }

            // 不能只修改 Base URL 而不设置 API Key（针对需要 Key 的服务）
            if (hasNewUrl && !hasNewKey && requiresKey) {
              const currentHasPersonalKey =
                !config?.inherited_keys?.includes("llm_api_key") && Boolean(form.llm_api_key);
              if (!currentHasPersonalKey) {
                message.error("不能只修改 Base URL，自定义端点需同时配置 Base URL 与 API Key");
                return;
              }
            }

            // 切换了需 Key 的服务商但未填 Key
            if (patch.llm_provider && !hasNewKey && requiresKey && !isInheritingKey) {
              message.error(`${selectedDefaults?.label || providerName} 需要同时配置 Base URL 与 API Key`);
              return;
            }

            // 用户若既无新 Key 也无新 URL，但此前未继承 Key 且无已保存 Key
            const hasExistingKey = Boolean(
              !config?.inherited_keys?.includes("llm_api_key")
                && typeof form.llm_api_key === "string"
                && form.llm_api_key.trim(),
            );
            if (requiresKey && !hasNewKey && !isInheritingKey && !hasExistingKey) {
              message.error(`${selectedDefaults?.label || providerName} 需要填写 API Key`);
              return;
            }
          }
          saveConfig(patch, CARD_SPECS.llm.saveMessage);
          return;
        }
        case "twitter": {
          saveConfig(
            { twitter_feeds: normalizeFeeds(form.twitter_feeds) },
            CARD_SPECS.twitter.saveMessage,
            () => {
              void queryClient.invalidateQueries({ queryKey: queryKeys.market.twitterFeed });
            },
          );
          return;
        }
        case "fred": {
          const value = (form.fred_api_key ?? "").trim();
          if (value.includes("***") || value === (config?.fred_api_key ?? "")) {
            message.info("没有需要保存的变更");
            return;
          }
          saveConfig({ fred_api_key: value }, CARD_SPECS.fred.saveMessage);
          return;
        }
        case "anysearch": {
          const value = (form.anysearch_api_key ?? "").trim();
          if (!value || value.includes("***")) {
            message.info("没有需要保存的变更");
            return;
          }
          saveConfig({ anysearch_api_key: value }, CARD_SPECS.anysearch.saveMessage, () =>
            updateForm({ anysearch_api_key: "" }),
          );
          return;
        }
        case "fuyao": {
          const value = (form.fuyao_api_key ?? "").trim();
          if (!value || value.includes("***") || value === (config?.fuyao_api_key ?? "")) {
            message.info("没有需要保存的变更");
            return;
          }
          saveConfig({ fuyao_api_key: value }, CARD_SPECS.fuyao.saveMessage, () =>
            updateForm({ fuyao_api_key: "" }),
          );
          return;
        }
        case "outboundProxy": {
          const proxyType = form.outbound_proxy_type ?? "none";
          const rawUrl = (form.outbound_proxy_url ?? "").trim();
          // 代理地址按凭证下发，已保存的值会带 ***，此时不覆盖后端原值
          const maskedUrl = isMaskedValue(rawUrl);
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
              outbound_proxy_timeout_seconds: form.outbound_proxy_timeout_seconds ?? 20,
              outbound_proxy_retries: form.outbound_proxy_retries ?? 2,
            },
            proxyType === "none" ? "出站代理已关闭" : CARD_SPECS.outboundProxy.saveMessage,
            (updatedConfig) => {
              if (updatedConfig) {
                updateForm({
                  outbound_proxy_type: updatedConfig.outbound_proxy_type,
                  outbound_proxy_url: updatedConfig.outbound_proxy_url ?? "",
                  outbound_proxy_timeout_seconds: updatedConfig.outbound_proxy_timeout_seconds,
                  outbound_proxy_retries: updatedConfig.outbound_proxy_retries,
                  outbound_proxy_scopes: updatedConfig.outbound_proxy_scopes,
                });
              }
            },
          );
          return;
        }
        case "bot": {
          saveConfig(
            {
              ...buildCardPatch(form, CARD_SPECS.bot),
              bot_admin_users: normalizeAdminUsers(form.bot_admin_users),
            },
            CARD_SPECS.bot.saveMessage,
          );
          return;
        }
        default:
          saveConfig(buildCardPatch(form, CARD_SPECS[key]), CARD_SPECS[key].saveMessage);
      }
    };

    const reset = (key: CardKey) => {
      if (!config) return;
      if (key === "anysearch") {
        updateForm({ anysearch_api_key: "" });
        message.success(CARD_SPECS.anysearch.resetMessage);
        return;
      }
      if (key === "llm") {
        updateForm(buildCardReset(config, CARD_SPECS.llm));
        setPreviousProvider(config.llm_provider ?? "");
        message.success(CARD_SPECS.llm.resetMessage);
        return;
      }
      updateForm(buildCardReset(config, CARD_SPECS[key]));
      message.success(CARD_SPECS[key].resetMessage);
    };

    return { save, reset, dirty: cardDirty, isSaving };
  }, [config, form, cardDirty, isSaving, queryClient, saveConfig, updateForm]);

  return {
    form,
    updateForm,
    dirtyFlags,
    cards,
    handleResetAllUnsaved,
    handleProviderChange,
  };
}
