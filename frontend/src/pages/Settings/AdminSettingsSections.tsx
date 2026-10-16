import { useState } from "react";
import { DatabaseOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Col, Row, Segmented } from "antd";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import AdminResetCard from "../../components/AdminResetCard";
import {
  AnySearchConfigCard,
  BackupRetentionCard,
  BotConfigCard,
  DataSourceCookiesCard,
  DataSourceCredentialsCard,
  EastmoneyProxyConfigCard,
  EastmoneyRateLimitConfigCard,
  FredConfigCard,
  IwencaiConfigCard,
  MarketDailyBarManagerCard,
  ResearchBudgetCard,
  ScheduledTasksConfigCard,
  TwitterConfigCard,
} from "./ConfigCards";
import BotJobManagerCard from "./BotJobManagerCard";
import InviteManagerCard from "./InviteManagerCard";
import SecurityAuditCard from "./SecurityAuditCard";
import UserManagerCard from "./UserManagerCard";
import type { ConfigSectionProps } from "./sectionTypes";
import type { ProxyTestResponse } from "../../types/settings";
import type { SettingsCards } from "./useSettingsForm";

interface DataSourcesSettingsSectionProps extends ConfigSectionProps {
  anySearchConfigured: boolean;
  fuyaoConfigured: boolean;
  onTestOutboundProxy?: () => void;
  isTestingOutboundProxy?: boolean;
  outboundProxyTestResult?: ProxyTestResponse | null;
  isAdmin?: boolean;
  cards: SettingsCards;
}

export function DataSourcesSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  anySearchConfigured,
  fuyaoConfigured,
  onTestOutboundProxy,
  isTestingOutboundProxy = false,
  outboundProxyTestResult = null,
  isAdmin = true,
  cards,
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
          onSave={() => cards.save("iwencai")}
          isDirty={cards.dirty.iwencai}
          onReset={() => cards.reset("iwencai")}
        />
      </div>

      {/* 全局公共数据源（宏观、舆情、搜索与备用源） */}
      {isAdmin && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <FredConfigCard
              stretch
              {...cardProps}
              onSave={() => cards.save("fred")}
              isDirty={cards.dirty.fred}
              onReset={() => cards.reset("fred")}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <TwitterConfigCard
              stretch
              {...cardProps}
              onSave={() => cards.save("twitter")}
              isDirty={cards.dirty.twitter}
              onReset={() => cards.reset("twitter")}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <AnySearchConfigCard
              stretch
              {...cardProps}
              configured={anySearchConfigured}
              onSave={() => cards.save("anysearch")}
              isDirty={cards.dirty.anysearch}
              onReset={() => cards.reset("anysearch")}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <DataSourceCredentialsCard
              stretch
              {...cardProps}
              fuyaoConfigured={fuyaoConfigured}
              onSave={() => cards.save("fuyao")}
              isDirty={cards.dirty.fuyao}
              onReset={() => cards.reset("fuyao")}
            />
          </Col>
          <Col xs={24} style={{ display: "flex" }}>
            <DataSourceCookiesCard
              stretch
              {...cardProps}
              onSave={() => cards.save("dataSourceCookies")}
              isDirty={cards.dirty.dataSourceCookies}
              onReset={() => cards.reset("dataSourceCookies")}
            />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <EastmoneyProxyConfigCard
              stretch
              {...cardProps}
              onSave={() => cards.save("outboundProxy")}
              isDirty={cards.dirty.outboundProxy}
              onReset={() => cards.reset("outboundProxy")}
              onTest={onTestOutboundProxy}
              isTesting={isTestingOutboundProxy}
              testResult={outboundProxyTestResult}
            />
          </Col>
          <Col xs={24} style={{ display: "flex" }}>
            <EastmoneyRateLimitConfigCard
              stretch
              {...cardProps}
              onSave={() => cards.save("eastmoneyRateLimit")}
              isDirty={cards.dirty.eastmoneyRateLimit}
              onReset={() => cards.reset("eastmoneyRateLimit")}
            />
          </Col>
        </Row>
      )}
    </section>
  );
}

interface AdminSettingsSectionProps extends ConfigSectionProps {
  cards: SettingsCards;
}

export function AdminSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  cards,
}: AdminSettingsSectionProps) {
  const [activeTab, setActiveTab] = useState<"ops" | "bot" | "user">("ops");
  const isNarrow = useMediaQuery("(max-width: 640px)");
  const isMobile = useMediaQuery("(max-width: 480px)");
  const opsDirty =
    cards.dirty.backup ||
    cards.dirty.marketDaily ||
    cards.dirty.researchBudget ||
    cards.dirty.scheduledTasks;

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
          block={isNarrow}
          size={isNarrow ? "middle" : "large"}
          options={[
            {
              value: "ops",
              label: (
                <span style={{ padding: isNarrow ? "0 2px" : "0 8px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                  <DatabaseOutlined /> {isNarrow ? (isMobile ? "运维" : "系统运维") : "系统运维与数据维护"}
                  {opsDirty && (
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
                <span style={{ padding: isNarrow ? "0 2px" : "0 8px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                  <RobotOutlined /> {isNarrow ? (isMobile ? "推送" : "自动化推送") : "自动化与推送机器人"}
                  {cards.dirty.bot && (
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
                <span style={{ padding: isNarrow ? "0 2px" : "0 8px", display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6 }}>
                  <UserOutlined /> {isNarrow ? (isMobile ? "用户" : "用户安全") : "用户与权限安全"}
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
            常驻后台定时任务开关、数据库在线备份策略（基础库与大库独立周期/极速压缩）、10 年日线数据维护与 AI 思考耗时预算。
          </p>
          <ScheduledTasksConfigCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={() => cards.save("scheduledTasks")}
            isDirty={cards.dirty.scheduledTasks}
            onReset={() => cards.reset("scheduledTasks")}
          />
          <BackupRetentionCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={() => cards.save("backup")}
            isDirty={cards.dirty.backup}
            onReset={() => cards.reset("backup")}
          />
          <MarketDailyBarManagerCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            sectionTitleStyle={sectionTitleStyle}
            onSave={() => cards.save("marketDaily")}
            isDirty={cards.dirty.marketDaily}
            onReset={() => cards.reset("marketDaily")}
          />
          <ResearchBudgetCard
            form={form}
            onChange={onChange}
            isSaving={isSaving}
            onSave={() => cards.save("researchBudget")}
            isDirty={cards.dirty.researchBudget}
            onReset={() => cards.reset("researchBudget")}
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
            onSave={() => cards.save("bot")}
            isDirty={cards.dirty.bot}
            onReset={() => cards.reset("bot")}
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
