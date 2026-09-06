import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function DataSourceCookiesCard({
  form,
  onChange,
  onSave,
  isSaving,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="数据源 Cookie 配置（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存数据源 Cookie"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>东方财富 Cookie</div>
          <Input.Password
            value={form.eastmoney_cookie || ""}
            onChange={(event) => onChange({ eastmoney_cookie: event.target.value })}
            placeholder="留空使用内置默认值"
          />
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            从浏览器 DevTools → Network → 请求头中复制 Cookie 值
          </div>
        </Col>
        <Col span={24}>
          <div style={fieldLabelStyle}>百度 Cookie</div>
          <Input.Password
            value={form.baidu_cookie || ""}
            onChange={(event) => onChange({ baidu_cookie: event.target.value })}
            placeholder="留空使用内置默认值"
          />
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            从浏览器 DevTools → Network → 请求头中复制 Cookie 值
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
