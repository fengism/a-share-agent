import { Col, Row } from "antd";
import AdminResetCard from "../../components/AdminResetCard";
import {
  AnySearchConfigCard,
  BotConfigCard,
  DataSourceCookiesCard,
  FredConfigCard,
  ResearchBudgetCard,
  TwitterConfigCard,
} from "./ConfigCards";
import BotJobManagerCard from "./BotJobManagerCard";
import InviteManagerCard from "./InviteManagerCard";
import MarketDailyBarManagerCard from "./MarketDailyBarManagerCard";
import SecurityAuditCard from "./SecurityAuditCard";
import UserManagerCard from "./UserManagerCard";
import type { ConfigSectionProps } from "./sectionTypes";

interface DataSourcesSettingsSectionProps extends ConfigSectionProps {
  onSaveTwitter: () => void;
  onSaveFred: () => void;
  anySearchConfigured: boolean;
  onSaveAnySearch: () => void;
  onSaveDataSourceCookies: () => void;
}

export function DataSourcesSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveTwitter,
  onSaveFred,
  anySearchConfigured,
  onSaveAnySearch,
  onSaveDataSourceCookies,
}: DataSourcesSettingsSectionProps) {
  const cardProps = { form, onChange, isSaving };
  return (
    <section aria-labelledby="data-source-settings-title">
      <h3 id="data-source-settings-title" style={sectionTitleStyle}>数据源管理</h3>
      <Row gutter={[16, 0]}>
        <Col xs={24} lg={12}>
          <TwitterConfigCard {...cardProps} onSave={onSaveTwitter} />
        </Col>
        <Col xs={24} lg={12}>
          <FredConfigCard {...cardProps} onSave={onSaveFred} />
        </Col>
        <Col xs={24} lg={12}>
          <AnySearchConfigCard {...cardProps} configured={anySearchConfigured} onSave={onSaveAnySearch} />
        </Col>
        <Col xs={24} lg={12}>
          <DataSourceCookiesCard {...cardProps} onSave={onSaveDataSourceCookies} />
        </Col>
      </Row>
    </section>
  );
}

interface AdminSettingsSectionProps extends ConfigSectionProps {
  onSaveBot: () => void;
  onSaveResearchBudget: () => void;
  onSaveMarketDailyBars: () => void;
}

export function AdminSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveBot,
  onSaveResearchBudget,
  onSaveMarketDailyBars,
}: AdminSettingsSectionProps) {
  return (
    <section aria-labelledby="admin-settings-title">
      <h3 id="admin-settings-title" style={sectionTitleStyle}>管理员工具</h3>
      <UserManagerCard />
      <InviteManagerCard />
      <SecurityAuditCard />
      <AdminResetCard />
      <BotConfigCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveBot} />
      <ResearchBudgetCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveResearchBudget} />
      <MarketDailyBarManagerCard
        form={form}
        onChange={onChange}
        isSaving={isSaving}
        sectionTitleStyle={sectionTitleStyle}
        onSave={onSaveMarketDailyBars}
      />
      <BotJobManagerCard />
    </section>
  );
}
