import { Col, Row } from "antd";
import type { ProviderDefault } from "../../types/settings";
import {
  FeishuConfigCard,
  LlmConfigCard,
  NotificationChannelsConfigCard,
  NotionConfigCard,
  ProviderDefaultsCard,
} from "./ConfigCards";
import type { ConfigSectionProps } from "./sectionTypes";
import type { SettingsCards } from "./useSettingsForm";

interface AiSettingsSectionProps extends ConfigSectionProps {
  providerDefaults: Record<string, ProviderDefault>;
  onProviderChange: (provider: string) => void;
  cards: SettingsCards;
}

export function AiSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  providerDefaults,
  onProviderChange,
  cards,
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
        onSave={() => cards.save("llm")}
        onProviderChange={onProviderChange}
        isDirty={cards.dirty.llm}
        onReset={() => cards.reset("llm")}
      />
      <ProviderDefaultsCard providerDefaults={providerDefaults} />
    </section>
  );
}

interface IntegrationsSettingsSectionProps extends ConfigSectionProps {
  cards: SettingsCards;
}

export function IntegrationsSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  cards,
}: IntegrationsSettingsSectionProps) {
  const cardProps = { form, onChange, isSaving };
  return (
    <section aria-labelledby="integration-settings-title">
      <h3 id="integration-settings-title" style={sectionTitleStyle}>协同与自动推送</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 16 }}>
        支持将每日收盘复盘与题材雷达自动推送到飞书群、企业微信群或个人微信，并可将研报同步归档至飞书文档与 Notion 知识库。
      </p>
      <Row gutter={[16, 16]}>
        <Col span={24}>
          <NotificationChannelsConfigCard
            stretch
            {...cardProps}
            onSave={() => cards.save("notificationChannels")}
            isDirty={cards.dirty.notificationChannels}
            onReset={() => cards.reset("notificationChannels")}
          />
        </Col>
        <Col xs={24} xl={14} style={{ display: "flex" }}>
          <FeishuConfigCard
            stretch
            {...cardProps}
            onSave={() => cards.save("feishu")}
            isDirty={cards.dirty.feishu}
            onReset={() => cards.reset("feishu")}
          />
        </Col>
        <Col xs={24} xl={10} style={{ display: "flex" }}>
          <NotionConfigCard
            stretch
            {...cardProps}
            onSave={() => cards.save("notion")}
            isDirty={cards.dirty.notion}
            onReset={() => cards.reset("notion")}
          />
        </Col>
      </Row>
    </section>
  );
}
