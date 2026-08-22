import { RobotOutlined } from "@ant-design/icons";
import { Col, Input, Row, Select, Slider } from "antd";
import { useStyles } from "../../../styles/ui";
import type { LlmApiMode, ProviderDefault } from "../../../types/settings";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

const API_MODE_OPTIONS: Array<{ value: LlmApiMode; label: string }> = [
  { value: "auto", label: "自动（跟随 Provider）" },
  { value: "openai", label: "OpenAI Compatible" },
  { value: "litellm", label: "LiteLLM" },
];

interface LlmConfigCardProps extends ConfigCardProps {
  onProviderChange: (provider: string) => void;
  providerDefaults: Record<string, ProviderDefault>;
}

export default function LlmConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  onProviderChange,
  providerDefaults,
}: LlmConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const selectedDefaults = form.llm_provider ? providerDefaults[form.llm_provider] : undefined;
  const providerOptions = Object.entries(providerDefaults).map(([value, defaults]) => ({
    value,
    label: defaults.label || value,
  }));

  return (
    <SettingsCard
      title="大模型配置"
      icon={<RobotOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存大模型配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Provider</div>
          <Select
            value={form.llm_provider}
            onChange={onProviderChange}
            options={providerOptions}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API 模式</div>
          <Select<LlmApiMode>
            value={form.llm_api_mode || "auto"}
            onChange={(value) => onChange({ llm_api_mode: value })}
            options={API_MODE_OPTIONS}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>
            API Key{selectedDefaults && !selectedDefaults.api_key_required ? "（可选）" : ""}
          </div>
          <Input.Password
            value={form.llm_api_key || ""}
            onChange={(event) => onChange({ llm_api_key: event.target.value })}
            placeholder={
              selectedDefaults?.api_key_required === false
                ? "本地服务可留空"
                : "输入新的 API Key 以覆盖"
            }
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API Version（可选）</div>
          <Input
            value={form.llm_api_version || ""}
            onChange={(event) => onChange({ llm_api_version: event.target.value })}
            placeholder={selectedDefaults?.api_version || "Azure 等接口需要"}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Base URL</div>
          <Input
            value={form.llm_base_url || ""}
            onChange={(event) => onChange({ llm_base_url: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Model</div>
          <Input
            value={form.llm_model || ""}
            onChange={(event) => onChange({ llm_model: event.target.value })}
          />
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>Temperature: {form.llm_temperature ?? 0.1}</div>
          <Slider
            min={0}
            max={1}
            step={0.05}
            value={form.llm_temperature ?? 0.1}
            onChange={(value) => onChange({ llm_temperature: value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
