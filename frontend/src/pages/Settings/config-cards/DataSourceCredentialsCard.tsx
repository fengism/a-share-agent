import { ApiOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

interface DataSourceCredentialsCardProps extends ConfigCardProps {
  fuyaoConfigured: boolean;
}

export default function DataSourceCredentialsCard({
  form,
  onChange,
  onSave,
  isSaving,
  fuyaoConfigured,
  stretch,
  isDirty,
  onReset,
}: DataSourceCredentialsCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="fuyao 备用数据源"
      icon={<ApiOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 fuyao API Key"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>fuyao API Key</div>
          <Input.Password
            value={form.fuyao_api_key || ""}
            onChange={(event) => onChange({ fuyao_api_key: event.target.value })}
            placeholder={
              fuyaoConfigured ? "已配置；输入新的 Key 以覆盖现有配置" : "留空则不启用备用源"
            }
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            涨跌停与连板天梯备用兜底源，仅在主源异常时自动接管。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}