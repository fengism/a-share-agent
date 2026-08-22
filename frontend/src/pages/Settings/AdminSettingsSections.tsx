import { Col, Row } from "antd";
import AdminResetCard from "../../components/AdminResetCard";
import { BotConfigCard, DataSourceCookiesCard, TwitterConfigCard } from "./ConfigCards";
import BotJobManagerCard from "./BotJobManagerCard";
import InviteManagerCard from "./InviteManagerCard";
import type { ConfigSectionProps } from "./sectionTypes";

interface DataSourcesSettingsSectionProps extends ConfigSectionProps {
  onSaveTwitter: () => void;
  onSaveDataSourceCookies: () => void;
}

export function DataSourcesSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveTwitter,
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
          <DataSourceCookiesCard {...cardProps} onSave={onSaveDataSourceCookies} />
        </Col>
      </Row>
    </section>
  );
}

interface AdminSettingsSectionProps extends ConfigSectionProps {
  onSaveBot: () => void;
}

export function AdminSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveBot,
}: AdminSettingsSectionProps) {
  return (
    <section aria-labelledby="admin-settings-title">
      <h3 id="admin-settings-title" style={sectionTitleStyle}>管理员工具</h3>
      <BotConfigCard form={form} onChange={onChange} isSaving={isSaving} onSave={onSaveBot} />
      <BotJobManagerCard />
      <InviteManagerCard />
      <AdminResetCard />
    </section>
  );
}
