import { lazy, Suspense, useCallback, useState } from "react";
import { RobotOutlined, UndoOutlined } from "@ant-design/icons";
import { Button, message, Popconfirm, Tag } from "antd";
import { useInRouterContext } from "react-router-dom";
import { useConfig, useTestOutboundProxy, useTestTdxProxy } from "../../api/queries";
import ChangePasswordCard from "../../components/ChangePasswordCard";
import SessionManagerCard from "./SessionManagerCard";
import LoginHistoryCard from "./LoginHistoryCard";
import ResponsiveSectionNav from "../../components/ResponsiveSectionNav";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useColors, useStyles, semanticTagStyle } from "../../styles/ui";
import type { ProxyTestResponse, TdxProxyTestResponse } from "../../types/settings";
import SystemUpdateCard from "./SystemUpdateCard";
import SettingsDirtySummary from "./SettingsDirtySummary";
import SettingsLeaveBlocker from "./SettingsLeaveBlocker";
import SettingsMobileSaveBar from "./SettingsMobileSaveBar";
import SettingsSectionUrlSync from "./SettingsSectionUrlSync";
import { CARD_KEYS } from "./cardSpecs";
import { DEFAULT_SETTINGS_SECTION, SETTINGS_SCROLL_OFFSET, type SettingsSectionKey } from "./settingsSections";
import "./settings.css";
import { useConfigSectionSave } from "./useConfigSectionSave";
import { useSettingsForm } from "./useSettingsForm";

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
  const {
    mutate: testTdxProxyMutate,
    isPending: isTestingTdxProxy,
  } = useTestTdxProxy();
  const [outboundProxyTestResult, setOutboundProxyTestResult] = useState<ProxyTestResponse | null>(null);
  const [tdxProxyTestResult, setTdxProxyTestResult] = useState<TdxProxyTestResponse | null>(null);
  const user = useAuthStore((state) => state.user);
  const isAdmin = Boolean(config?.is_admin);

  const {
    form,
    updateForm,
    dirtyFlags,
    cards,
    handleResetAllUnsaved,
    handleProviderChange,
  } = useSettingsForm(config, saveConfig, isSaving);

  const [activeSection, setActiveSection] = useState<SettingsSectionKey>(DEFAULT_SETTINGS_SECTION);
  const inRouter = useInRouterContext();
  const dirtyCardCount = CARD_KEYS.filter((key) => Boolean(cards.dirty[key])).length;

  const handleSectionChange = useCallback((key: string) => {
    setActiveSection(key as SettingsSectionKey);
    // 切换分区后回到顶部，避免停留在上一分区的长滚动位置
    try {
      window.scrollTo({ top: 0, behavior: "auto" });
    } catch {
      // 测试环境（jsdom）未实现 scrollTo，忽略即可
    }
  }, []);

  const handleJumpToCard = useCallback((section: SettingsSectionKey, anchorId?: string) => {
    setActiveSection(section);
    if (!anchorId) {
      try {
        window.scrollTo({ top: 0, behavior: "auto" });
      } catch {
        // jsdom 未实现 scrollTo
      }
      return;
    }
    // 等目标分区渲染出锚点后再滚动
    window.setTimeout(() => {
      const target = document.getElementById(anchorId);
      if (!target) return;
      const top = target.getBoundingClientRect().top + window.scrollY - SETTINGS_SCROLL_OFFSET;
      try {
        window.scrollTo({ top, behavior: "smooth" });
      } catch {
        // jsdom 未实现 scrollTo
      }
    }, 0);
  }, []);

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

  const handleTestTdxProxy = useCallback(() => {
    testTdxProxyMutate(undefined, {
      onSuccess: (result) => {
        setTdxProxyTestResult(result);
        if (result.ok) {
          message.success(`TDX 链路可用（${result.latency_ms}ms）`);
        } else {
          message.warning(`TDX 链路不可用：${result.message}`);
        }
      },
      onError: (error: Error) => message.error(`TDX 连通性测试失败: ${error.message}`),
    });
  }, [testTdxProxyMutate]);

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
            <div className="settings-header-actions">
              <SettingsDirtySummary cards={cards} onJumpToCard={handleJumpToCard} />
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
                <SessionManagerCard />
                <LoginHistoryCard />
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
                  inheritedKeys={config.inherited_keys}
                  isAdmin={isAdmin}
                  onProviderChange={handleProviderChange}
                  cards={cards}
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
                  anySearchConfigured={Boolean(config.anysearch_api_key)}
                  fuyaoConfigured={Boolean(config.fuyao_api_key)}
                  onTestOutboundProxy={handleTestOutboundProxy}
                  isTestingOutboundProxy={isTestingOutboundProxy}
                  outboundProxyTestResult={outboundProxyTestResult}
                  onTestTdxProxy={handleTestTdxProxy}
                  isTestingTdxProxy={isTestingTdxProxy}
                  tdxProxyTestResult={tdxProxyTestResult}
                  cards={cards}
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
                  cards={cards}
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
                    cards={cards}
                  />
                </Suspense>
              ),
            },
          ] : []),
        ]}
        activeKey={activeSection}
        onChange={handleSectionChange}
        ariaLabel="系统配置分类"
        desktopMode="rail"
        preserveVisited
        mobileMode="chips"
      />
      <SettingsMobileSaveBar cards={cards} onResetAll={handleResetAllUnsaved} />
      {inRouter && <SettingsSectionUrlSync section={activeSection} onChange={setActiveSection} />}
      {inRouter && (
        <SettingsLeaveBlocker
          hasUnsavedChanges={dirtyFlags.hasUnsavedChanges}
          dirtyCardCount={dirtyCardCount}
        />
      )}
    </div>
  );
}
