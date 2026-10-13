import { useState } from "react";
import { DatabaseOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Col, Row, Segmented } from "antd";
import AdminResetCard from "../../components/AdminResetCard";
import {
  AnySearchConfigCard,
  BotConfigCard,
  DataSourceCredentialsCard,
  EastmoneyProxyConfigCard,
  EastmoneyRateLimitConfigCard,
  FredConfigCard,
  IwencaiConfigCard,
  ResearchBudgetCard,
  TwitterConfigCard,
} from "./ConfigCards";
import BackupRetentionCard from "./BackupRetentionCard";
import BotJobManagerCard from "./BotJobManagerCard";
import InviteManagerCard from "./InviteManagerCard";
import MarketDailyBarManagerCard from "./MarketDailyBarManagerCard";
import SecurityAuditCard from "./SecurityAuditCard";
import UserManagerCard from "./UserManagerCard";
import type { ConfigSectionProps } from "./sectionTypes";
import type { ProxyTestResponse } from "../../types/settings";

interface DataSourcesSettingsSectionProps extends ConfigSectionProps {
  onSaveIwencai: () => void;
  onSaveTwitter: () => void;
  onSaveFred: () => void;
  anySearchConfigured: boolean;
  onSaveAnySearch: () => void;
  fuyaoConfigured: boolean;
  onSaveDataSourceCredentials: () => void;
  onSaveOutboundProxy: () => void;
  onSaveEastmoneyRateLimit: () => void;
  onTestOutboundProxy?: () => void;
  isTestingOutboundProxy?: boolean;
  outboundProxyTestResult?: ProxyTestResponse | null;
  onResetIwencai?: () => void;
  onResetTwitter?: () => void;
  onResetFred?: () => void;
  onResetAnySearch?: () => void;
  onResetFuyao?: () => void;
  onResetOutboundProxy?: () => void;
  onResetEastmoneyRateLimit?: () => void;
  isAdmin?: boolean;
  dirtyCards?: {
    iwencai?: boolean;
    fred?: boolean;
    twitter?: boolean;
    anySearch?: boolean;
    fuyao?: boolean;
    outboundProxy?: boolean;
    eastmoneyRateLimit?: boolean;
  };
}

export function DataSourcesSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveIwencai,
  onSaveTwitter,
  onSaveFred,
  anySearchConfigured,
  onSaveAnySearch,
  fuyaoConfigured,
  onSaveDataSourceCredentials,
  onSaveOutboundProxy,
  onSaveEastmoneyRateLimit,
  onTestOutboundProxy,
  isTestingOutboundProxy = false,
  outboundProxyTestResult = null,
  onResetIwencai,
  onResetTwitter,
  onResetFred,
  onResetAnySearch,
  onResetFuyao,
  onResetOutboundProxy,
  onResetEastmoneyRateLimit,
  isAdmin = true,
  dirtyCards = {},
}: DataSourcesSettingsSectionProps) {
  const cardProps = { form, onChange, isSaving };
  return (
    <section aria-labelledby="data-source-settings-title">
      <h3 id="data-source-settings-title" style={sectionTitleStyle}>数据源管理</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 16 }}>
        配置系统获取市场行情、财务指标、宏观经济与新闻资讯的数据输入源。问财为个人专属配置，其余为全局系统共享数据源。
      </p>

      {/* 智能选股与自然语言数据源（个人独立配置） */}
      <div style={{ marginBottom: 20 }}>
        <IwencaiConfigCard
          {...cardProps}
          onSave={onSaveIwencai}
          isDirty={dirtyCards.iwencai}
          onReset={onResetIwencai}
        />
      </div>

      {/* 全局公共数据源（宏观、舆情、搜索与备用源） */}
      {isAdmin && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <FredConfigCard
              stretch
              {...cardProps}
              onSave={onSaveFred}
              isDirty={dirtyCards.fred}
              onReset={onResetFred}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <TwitterConfigCard
              stretch
              {...cardProps}
              onSave={onSaveTwitter}
              isDirty={dirtyCards.twitter}
              onReset={onResetTwitter}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <AnySearchConfigCard
              stretch
              {...cardProps}
              configured={anySearchConfigured}
              onSave={onSaveAnySearch}
              isDirty={dirtyCards.anySearch}
              onReset={onResetAnySearch}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <DataSourceCredentialsCard
              stretch
              {...cardProps}
              fuyaoConfigured={fuyaoConfigured}
              onSave={onSaveDataSourceCredentials}
              isDirty={dirtyCards.fuyao}
              onReset={onResetFuyao}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <EastmoneyProxyConfigCard
              stretch
              {...cardProps}
              onSave={onSaveOutboundProxy}
              isDirty={dirtyCards.outboundProxy}
              onReset={onResetOutboundProxy}
              onTest={onTestOutboundProxy}
              isTesting={isTestingOutboundProxy}
              testResult={outboundProxyTestResult}
            />
          </Col>
          <Col xs={24} style={{ display: "flex" }}>
            <EastmoneyRateLimitConfigCard
              stretch
              {...cardProps}
              onSave={onSaveEastmoneyRateLimit}
              isDirty={dirtyCards.eastmoneyRateLimit}
              onReset={onResetEastmoneyRateLimit}
            />
          </Col>
        </Row>
      )}
    </section>
  );
}

interface AdminSettingsSectionProps extends ConfigSectionProps {
  onSaveBot: () => void;
  onSaveResearchBudget: () => void;
  onSaveMarketDailyBars: () => void;
  onSaveBackupRetention: () => void;
  onResetBot?: () => void;
  onResetResearchBudget?: () => void;
  onResetMarketDailyBars?: () => void;
  onResetBackupRetention?: () => void;
  dirtyCards?: {
    backup?: boolean;
    marketDaily?: boolean;
    researchBudget?: boolean;
    bot?: boolean;
  };
}

export function AdminSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveBot,
  onSaveResearchBudget,
  onSaveMarketDailyBars,
  onSaveBackupRetention,
  onResetBot,
  onResetResearchBudget,
  onResetMarketDailyBars,
  onResetBackupRetention,
  dirtyCards = {},
}: AdminSettingsSectionProps) {
  const [activeTab, setActiveTab] = useState<"ops" | "bot" | "user">("ops");

  return (
    <section aria-labelledby="admin-settings-title">
      <h3 id="admin-settings-title" style={sectionTitleStyle}>管理员工具</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 16 }}>
        面向系统管理员的高级功能：涵盖系统运维策略、自动化机器人调度与全局用户权限治理。
      </p>

      <div style={{ marginBottom: 20 }}>
        <Segmented
          value={activeTab}
          onChange={(val) => setActiveTab(val as "ops" | "bot" | "user")}
          size="large"
          options={[
            {
              value: "ops",
              label: (
                <span style={{ padding: "0 8px", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <DatabaseOutlined /> 系统运维与数据维护
                  {(dirtyCards.backup || dirtyCards.marketDaily || dirtyCards.researchBudget) && (
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
            },
            {
              value: "bot",
              label: (
                <span style={{ padding: "0 8px", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <RobotOutlined /> 自动化与推送机器人
                  {dirtyCards.bot && (
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
            },
            {
              value: "user",
              label: (
                <span style={{ padding: "0 8px", display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <UserOutlined /> 用户与权限安全
                </span>
              ),
            },
          ]}
        />
      </div>

      {/* 模块一：系统运维与数据维护 */}
      {activeTab === "ops" && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
            数据库在线备份策略（基础库与大库独立周期/极速压缩）、10 年日线数据维护与 AI 思考耗时预算。
          </p>
          <BackupRetentionCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={onSaveBackupRetention}
            isDirty={dirtyCards.backup}
            onReset={onResetBackupRetention}
          />
          <MarketDailyBarManagerCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            sectionTitleStyle={sectionTitleStyle}
            onSave={onSaveMarketDailyBars}
            isDirty={dirtyCards.marketDaily}
            onReset={onResetMarketDailyBars}
          />
          <ResearchBudgetCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={onSaveResearchBudget}
            isDirty={dirtyCards.researchBudget}
            onReset={onResetResearchBudget}
          />
        </div>
      )}

      {/* 模块二：自动化与推送机器人 */}
      {activeTab === "bot" && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
            飞书群聊交互机器人接入、盘后复盘自动推送规则与后台任务处理队列监控。
          </p>
          <BotConfigCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={onSaveBot}
            isDirty={dirtyCards.bot}
            onReset={onResetBot}
          />
          <BotJobManagerCard />
        </div>
      )}

      {/* 模块三：用户权限与安全审计 */}
      {activeTab === "user" && (
        <div style={{ marginBottom: 24 }}>
          <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
            系统注册账号管理、邀请码发放、安全操作审计与敏感凭证一键重置。
          </p>
          <UserManagerCard />
          <InviteManagerCard />
          <SecurityAuditCard />
          <AdminResetCard />
        </div>
      )}
    </section>
  );
}
