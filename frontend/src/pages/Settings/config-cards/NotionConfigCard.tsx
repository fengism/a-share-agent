import { BookOutlined } from "@ant-design/icons";
import { Col, Input, Row, Switch } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function NotionConfigCard({
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
      title="Notion 转存配置"
      icon={<BookOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Notion 配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用 Notion 转存</div>
          <Switch
            checked={form.notion_enabled ?? false}
            onChange={(value) => onChange({ notion_enabled: value })}
          />
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>Notion API Token</div>
          <Input.Password
            value={form.notion_api_token || ""}
            onChange={(event) => onChange({ notion_api_token: event.target.value })}
            placeholder="输入新的 Integration Secret 以覆盖 (secret_...)"
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
            来自 Notion Integrations 的 Internal Integration Secret，用于调用 Notion 官方 API 创建页面
          </div>
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Parent Page ID</div>
          <Input
            value={form.notion_parent_page_id || ""}
            onChange={(event) => onChange({ notion_parent_page_id: event.target.value })}
            placeholder="例如 32 位页面 ID"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Database ID（可选）</div>
          <Input
            value={form.notion_database_id || ""}
            onChange={(event) => onChange({ notion_database_id: event.target.value })}
            placeholder="例如 32 位数据库 ID"
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
