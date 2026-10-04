import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row, Switch } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function IwencaiConfigCard({ form, onChange, onSave, isSaving, stretch }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="问财数据源配置"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存问财配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
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
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>API Key</div>
          <Input.Password
            value={form.iwencai_api_key || ""}
            onChange={(event) => onChange({ iwencai_api_key: event.target.value })}
            placeholder="输入新的 API Key 以覆盖"
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
