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
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            配置后，Agent 的普通网页搜索会自动优先使用 AnySearch，无需显式选择引擎；失败时自动降级。
            支持单 Key、英文逗号分隔或 JSON 数组；多个 Key 按请求轮询，限流或失效时自动切换；密钥会加密保存。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
