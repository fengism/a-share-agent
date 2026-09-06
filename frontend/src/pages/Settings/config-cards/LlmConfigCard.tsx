import { RobotOutlined } from "@ant-design/icons";
import { Col, Input, Row, Select, Slider, Tag } from "antd";
import { useStyles } from "../../../styles/ui";
import type { LlmApiMode, ProviderDefault } from "../../../types/settings";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

const API_MODE_OPTIONS: Array<{ value: LlmApiMode; label: string }> = [
  { value: "auto", label: "自动（跟随 Provider）" },
  { value: "openai", label: "OpenAI Compatible" },
  { value: "litellm", label: "LiteLLM" },
];

const PROVIDER_RECOMMENDED_MODELS: Record<string, string[]> = {
  deepseek: ["deepseek-chat", "deepseek-reasoner"],
  openai: ["gpt-4o", "gpt-4o-mini", "o3-mini"],
  anthropic: ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
  qwen: ["qwen-plus", "qwen-max", "qwen-turbo"],
  siliconflow: ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "Qwen/Qwen2.5-72B-Instruct"],
  ollama: ["deepseek-r1:8b", "qwen2.5:7b", "llama3.1:8b"],
  zhipu: ["glm-4-plus", "glm-4-air", "glm-4-flash"],
  baichuan: ["Baichuan4", "Baichuan3-Turbo"],
  moonshot: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
};

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
            placeholder={selectedDefaults?.model || "模型标识符"}
          />
          {form.llm_provider && PROVIDER_RECOMMENDED_MODELS[form.llm_provider] ? (
            <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
              <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)", alignSelf: "center" }}>常用模型:</span>
              {PROVIDER_RECOMMENDED_MODELS[form.llm_provider].map((m) => (
                <Tag
                  key={m}
                  style={{
                    cursor: "pointer",
                    fontSize: "var(--c-font-xs)",
                    marginInlineEnd: 0,
                    borderRadius: "4px",
                    background: form.llm_model === m ? "var(--c-primary-soft)" : undefined,
                    borderColor: form.llm_model === m ? "var(--c-primary)" : undefined,
                    color: form.llm_model === m ? "var(--c-primary)" : undefined,
                  }}
                  onClick={() => onChange({ llm_model: m })}
                >
                  {m}
                </Tag>
              ))}
            </div>
          ) : null}
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
