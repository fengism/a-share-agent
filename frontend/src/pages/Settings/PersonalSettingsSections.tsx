import { Col, Row } from "antd";
import type { ProviderDefault } from "../../types/settings";
import {
  FeishuConfigCard,
  IwencaiConfigCard,
  LlmConfigCard,
  NotionConfigCard,
  ProviderDefaultsCard,
} from "./ConfigCards";
import type { ConfigSectionProps } from "./sectionTypes";

interface AiSettingsSectionProps extends ConfigSectionProps {
  providerDefaults: Record<string, ProviderDefault>;
  onSave: () => void;
  onProviderChange: (provider: string) => void;
}

export function AiSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  providerDefaults,
  onSave,
  onProviderChange,
}: AiSettingsSectionProps) {
  return (
    <section aria-labelledby="ai-settings-title">
      <h3 id="ai-settings-title" style={sectionTitleStyle}>AI 配置</h3>
      <LlmConfigCard
        form={form}
        onChange={onChange}
        isSaving={isSaving}
        providerDefaults={providerDefaults}
        onSave={onSave}
        onProviderChange={onProviderChange}
      />
      <ProviderDefaultsCard providerDefaults={providerDefaults} />
    </section>
  );
}

interface IntegrationsSettingsSectionProps extends ConfigSectionProps {
  onSaveFeishu: () => void;
  onSaveNotion: () => void;
  onSaveIwencai: () => void;
}

export function IntegrationsSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveFeishu,
  onSaveNotion,
  onSaveIwencai,
}: IntegrationsSettingsSectionProps) {
  const cardProps = { form, onChange, isSaving };
  return (
    <section aria-labelledby="integration-settings-title">
      <h3 id="integration-settings-title" style={sectionTitleStyle}>内容集成</h3>
      <FeishuConfigCard {...cardProps} onSave={onSaveFeishu} />
      <Row gutter={[16, 0]}>
        <Col xs={24} lg={12} style={{ display: "flex" }}>
          <NotionConfigCard stretch {...cardProps} onSave={onSaveNotion} />
        </Col>
        <Col xs={24} lg={12} style={{ display: "flex" }}>
          <IwencaiConfigCard stretch {...cardProps} onSave={onSaveIwencai} />
        </Col>
      </Row>
    </section>
  );
}
