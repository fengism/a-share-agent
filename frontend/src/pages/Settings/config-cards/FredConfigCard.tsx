import { KeyOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function FredConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="FRED 美国宏观数据（全局）"
      icon={<KeyOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 FRED 配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>FRED API Key</div>
          <Input.Password
            aria-label="FRED API Key"
            value={form.fred_api_key || ""}
            onChange={(event) => onChange({ fred_api_key: event.target.value })}
            placeholder="从 FRED 官网申请 API Key"
          />
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            由管理员统一配置，对所有用户生效；密钥会加密保存且不会明文展示。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
