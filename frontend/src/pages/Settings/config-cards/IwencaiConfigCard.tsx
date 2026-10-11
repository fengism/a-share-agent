import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row, Switch, Tag } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function IwencaiConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  stretch,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="问财数据源配置"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存问财配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-sm)", marginTop: -4, marginBottom: 16 }}>
        自定义问财地址需要填写个人 API Key，用于自然语言条件选股与财务指标检索。
      </div>
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用问财数据源</div>
          <Switch
            checked={form.iwencai_enabled ?? false}
            onChange={(value) => onChange({ iwencai_enabled: value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Base URL</div>
          <Input
            value={form.iwencai_base_url || ""}
            onChange={(event) => onChange({ iwencai_base_url: event.target.value })}
            placeholder="https://openapi.iwencai.com"
          />
          <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px", alignItems: "center" }}>
            <span style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>常用预设:</span>
            <Tag
              style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0, borderRadius: "4px" }}
              onClick={() => onChange({ iwencai_base_url: "https://openapi.iwencai.com" })}
            >
              官方 OpenAPI
            </Tag>
            <Tag
              style={{ cursor: "pointer", fontSize: "var(--c-font-xs)", marginInlineEnd: 0, borderRadius: "4px" }}
              onClick={() => onChange({ iwencai_base_url: "http://127.0.0.1:8000" })}
            >
              本地转发代理
            </Tag>
          </div>
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API Key</div>
          <Input.Password
            value={form.iwencai_api_key || ""}
            onChange={(event) => onChange({ iwencai_api_key: event.target.value })}
            placeholder="输入新的 API Key 以覆盖"
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
            用于自然语言选股和个股画像指标接口鉴权，留空则保持现有或免密转发
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
