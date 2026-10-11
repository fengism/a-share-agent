import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

interface AnySearchConfigCardProps extends ConfigCardProps {
  configured?: boolean;
}

export default function AnySearchConfigCard({
  form,
  onChange,
  onSave,
  isSaving,
  configured = false,
  stretch,
  isDirty,
  onReset,
}: AnySearchConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="AnySearch 网页搜索（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 AnySearch 配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>AnySearch API Key</div>
          <Input.Password
            aria-label="AnySearch API Key"
            value={form.anysearch_api_key || ""}
            onChange={(event) => onChange({ anysearch_api_key: event.target.value })}
            placeholder={
              configured
                ? "已配置；输入新的 Key 以覆盖现有配置"
                : "单个 Key，或用英文逗号分隔多个 Key"
            }
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            普通网页搜索会自动优先使用 AnySearch，支持英文逗号分隔多 Key 轮询容灾。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
