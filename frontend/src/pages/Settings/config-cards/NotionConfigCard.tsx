import { BookOutlined } from "@ant-design/icons";
import { Col, Input, Row, Switch } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function NotionConfigCard({ form, onChange, onSave, isSaving, stretch }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();

  return (
    <SettingsCard
      title="Notion 转存配置"
      icon={<BookOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Notion 配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用 Notion 转存</div>
          <Switch
            checked={form.notion_enabled ?? false}
            onChange={(value) => onChange({ notion_enabled: value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Parent Page ID</div>
          <Input
            value={form.notion_parent_page_id || ""}
            onChange={(event) => onChange({ notion_parent_page_id: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Database ID</div>
          <Input
            value={form.notion_database_id || ""}
            onChange={(event) => onChange({ notion_database_id: event.target.value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
