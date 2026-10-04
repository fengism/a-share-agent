import { DatabaseOutlined, RobotOutlined, UserOutlined } from "@ant-design/icons";
import { Col, Row } from "antd";
import AdminResetCard from "../../components/AdminResetCard";
import {
  AnySearchConfigCard,
  BotConfigCard,
  DataSourceCredentialsCard,
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

interface DataSourcesSettingsSectionProps extends ConfigSectionProps {
  onSaveIwencai: () => void;
  onSaveTwitter: () => void;
  onSaveFred: () => void;
  anySearchConfigured: boolean;
  onSaveAnySearch: () => void;
  fuyaoConfigured: boolean;
  onSaveDataSourceCredentials: () => void;
  isAdmin?: boolean;
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
  isAdmin = true,
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
        <IwencaiConfigCard {...cardProps} onSave={onSaveIwencai} />
      </div>

      {/* 全局公共数据源（宏观、舆情、搜索与备用源） */}
      {isAdmin && (
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <FredConfigCard stretch {...cardProps} onSave={onSaveFred} />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <TwitterConfigCard stretch {...cardProps} onSave={onSaveTwitter} />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <AnySearchConfigCard stretch {...cardProps} configured={anySearchConfigured} onSave={onSaveAnySearch} />
          </Col>
          <Col xs={24} lg={12} style={{ display: "flex" }}>
            <DataSourceCredentialsCard
              stretch
              {...cardProps}
              fuyaoConfigured={fuyaoConfigured}
              onSave={onSaveDataSourceCredentials}
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
}: AdminSettingsSectionProps) {
  const subSectionTitleStyle: React.CSSProperties = {
    margin: "24px 0 8px",
    color: "var(--c-text-primary)",
    fontSize: "var(--c-font-base)",
    fontWeight: "var(--c-weight-semibold)",
    display: "flex",
    alignItems: "center",
  };

  return (
    <section aria-labelledby="admin-settings-title">
      <h3 id="admin-settings-title" style={sectionTitleStyle}>管理员工具</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 20 }}>
        面向系统管理员的高级功能：涵盖系统运维策略、自动化机器人调度与全局用户权限治理。
      </p>

      {/* 模块一：系统运维与数据维护 */}
      <div style={{ marginBottom: 32 }}>
        <h4 style={subSectionTitleStyle}>
          <DatabaseOutlined style={{ marginRight: 8, color: "var(--c-primary)" }} />
          系统运维与数据维护
        </h4>
        <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
          数据库在线备份策略（基础库与大库独立周期/极速压缩）、10 年日线数据维护与 AI 思考耗时预算。
        </p>
        <BackupRetentionCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveBackupRetention} />
        <MarketDailyBarManagerCard
          form={form}
          onChange={onChange}
          isSaving={isSaving}
          sectionTitleStyle={sectionTitleStyle}
          onSave={onSaveMarketDailyBars}
        />
        <ResearchBudgetCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveResearchBudget} />
      </div>

      {/* 模块二：自动化与推送机器人 */}
      <div style={{ marginBottom: 32 }}>
        <h4 style={subSectionTitleStyle}>
          <RobotOutlined style={{ marginRight: 8, color: "var(--c-primary)" }} />
          自动化与推送机器人
        </h4>
        <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
          飞书群聊交互机器人接入、盘后复盘自动推送规则与后台任务处理队列监控。
        </p>
        <BotConfigCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveBot} />
        <BotJobManagerCard />
      </div>

      {/* 模块三：用户权限与安全审计 */}
      <div style={{ marginBottom: 32 }}>
        <h4 style={subSectionTitleStyle}>
          <UserOutlined style={{ marginRight: 8, color: "var(--c-primary)" }} />
          用户与权限安全
        </h4>
        <p style={{ color: "var(--c-text-muted)", marginTop: 0, marginBottom: 16 }}>
          系统注册账号管理、邀请码发放、安全操作审计与敏感凭证一键重置。
        </p>
        <UserManagerCard />
        <InviteManagerCard />
        <SecurityAuditCard />
        <AdminResetCard />
      </div>
    </section>
  );
}
