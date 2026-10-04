import type { ProviderDefault } from "../../types/settings";
import {
  FeishuConfigCard,
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
      <h3 id="ai-settings-title" style={sectionTitleStyle}>AI 模型配置</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 16 }}>
        配置驱动股票分析、每日大盘复盘、产业链梳理与量化策略的大语言模型推理引擎。
      </p>
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
}

export function IntegrationsSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  onSaveFeishu,
  onSaveNotion,
}: IntegrationsSettingsSectionProps) {
  const cardProps = { form, onChange, isSaving };
  return (
    <section aria-labelledby="integration-settings-title">
      <h3 id="integration-settings-title" style={sectionTitleStyle}>协同与研报导出</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 16 }}>
        将系统生成的每日大盘复盘、个股深度研报和产业链图谱，自动同步推送到飞书文档或 Notion 企业知识库。
      </p>
      <FeishuConfigCard {...cardProps} onSave={onSaveFeishu} />
      <div style={{ marginTop: 16 }}>
        <NotionConfigCard {...cardProps} onSave={onSaveNotion} />
      </div>
    </section>
  );
}
