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

export type ConfigSave = (
  patch: ConfigUpdate,
  successMessage: string,
  afterSuccess?: (data?: ConfigData) => void,
) => void;

export interface SettingsCards {
  /** 保存单张卡片（内部按卡片分派校验/归一化逻辑）。 */
  save: (key: CardKey) => void;
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
      Object.entries(cfg).filter(([key]) => key !== "provider_defaults" && key !== "is_admin"),
    ) as ConfigUpdate;
    // AnySearch 采用“粘贴新 Key 即替换”的交互，初始化不回填掩码值。
    return { ...values, anysearch_api_key: "" };
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
    },
    [config, form.llm_base_url, form.llm_model, previousProvider, updateForm],
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
    const save = (key: CardKey) => {
      switch (key) {
        case "llm": {
          const providerName = form.llm_provider || "openai";
          const selectedDefaults = config?.provider_defaults?.[providerName] as
            | ProviderDefault
            | undefined;
          if (selectedDefaults?.api_key_required && !form.llm_api_key?.trim()) {
            message.error(`${selectedDefaults.label || providerName} 需要填写 API Key`);
            return;
          }
          saveConfig(buildCardPatch(form, CARD_SPECS.llm), CARD_SPECS.llm.saveMessage);
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
