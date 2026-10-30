import { Col, Row } from "antd";
import type { ProviderDefault } from "../../types/settings";
import {
  FeishuConfigCard,
  LlmConfigCard,
  NotificationChannelsConfigCard,
  NotionConfigCard,
  ProviderDefaultsCard,
} from "./ConfigCards";
import { PERSONAL_LLM_CLEAR_PATCH } from "./llmInheritance";
import type { ConfigSectionProps } from "./sectionTypes";
import SettingsSectionDirectory from "./SettingsSectionDirectory";
import { SETTINGS_ANCHORS, type SettingsDirectoryItem } from "./settingsSections";
import type { SettingsCards } from "./useSettingsForm";

const AI_DIRECTORY: SettingsDirectoryItem[] = [
  { id: SETTINGS_ANCHORS.llm, label: "模型引擎" },
  { id: SETTINGS_ANCHORS.providerDefaults, label: "模型默认值" },
];

const INTEGRATION_DIRECTORY: SettingsDirectoryItem[] = [
  { id: SETTINGS_ANCHORS.pushChannels, label: "推送渠道" },
  { id: SETTINGS_ANCHORS.archive, label: "知识库归档" },
];

interface AiSettingsSectionProps extends ConfigSectionProps {
  providerDefaults: Record<string, ProviderDefault>;
  onProviderChange: (provider: string) => void;
  inheritedKeys?: string[];
  isAdmin?: boolean;
  cards: SettingsCards;
}

export function AiSettingsSection({
  form,
  onChange,
  isSaving,
  sectionTitleStyle,
  providerDefaults,
  onProviderChange,
  inheritedKeys,
  isAdmin,
  cards,
}: AiSettingsSectionProps) {
  return (
    <section aria-labelledby="ai-settings-title">
      <h3 id="ai-settings-title" style={sectionTitleStyle}>AI 模型配置</h3>
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 12 }}>
        配置驱动股票分析、每日大盘复盘、产业链梳理与量化策略的大语言模型推理引擎。
      </p>
      <SettingsSectionDirectory items={AI_DIRECTORY} ariaLabel="AI 模型配置目录" />

      <div className="settings-group" id={SETTINGS_ANCHORS.llm}>
        <h4 className="settings-group__title">模型引擎</h4>
        <p className="settings-group__hint">推理端点、模型选择与生成参数；留空则继承管理员全局配置。</p>
        <LlmConfigCard
          form={form}
          onChange={onChange}
          isSaving={isSaving}
          providerDefaults={providerDefaults}
          inheritedKeys={inheritedKeys}
          isAdmin={isAdmin}
          onUseAdminConfig={() => cards.save("llm", PERSONAL_LLM_CLEAR_PATCH)}
          onSave={() => cards.save("llm")}
          onProviderChange={onProviderChange}
          isDirty={cards.dirty.llm}
          onReset={() => cards.reset("llm")}
        />
      </div>

      <div className="settings-group" id={SETTINGS_ANCHORS.providerDefaults}>
        <h4 className="settings-group__title">模型默认值</h4>
        <p className="settings-group__hint">各服务商推荐端点与默认模型，供快速填充参考。</p>
        <ProviderDefaultsCard providerDefaults={providerDefaults} />
      </div>
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
      <p style={{ color: "var(--c-text-muted)", marginTop: -4, marginBottom: 12 }}>
        支持将每日收盘复盘与题材雷达自动推送到飞书群、企业微信群或个人微信，并可将研报同步归档至飞书文档与 Notion 知识库。
      </p>
      <SettingsSectionDirectory items={INTEGRATION_DIRECTORY} ariaLabel="协同与自动推送目录" />

      <div className="settings-group" id={SETTINGS_ANCHORS.pushChannels}>
        <h4 className="settings-group__title">推送渠道</h4>
        <p className="settings-group__hint">选择复盘与题材雷达的自动推送目标渠道及触发规则。</p>
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
        </Row>
      </div>

      <div className="settings-group" id={SETTINGS_ANCHORS.archive}>
        <h4 className="settings-group__title">知识库归档</h4>
        <p className="settings-group__hint">把研报同步写入飞书文档 / 知识空间或 Notion 数据库，便于长期检索。</p>
        <Row gutter={[16, 16]}>
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
      </div>
    </section>
  );
}
