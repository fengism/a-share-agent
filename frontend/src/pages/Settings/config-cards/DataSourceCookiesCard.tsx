import { GlobalOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import type { ConfigUpdate } from "../../../types/settings";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

const COOKIE_FIELDS = [
  {
    key: "eastmoney_cookie",
    label: "东方财富 Cookie",
    hint: "行情、资金流与数据中心接口的登录态，过期后相关数据会降级。",
  },
  {
    key: "baidu_cookie",
    label: "百度 Cookie",
    hint: "百度检索抓取的登录态，用于补充资讯与网页搜索结果。",
  },
  {
    key: "ths_cookie",
    label: "同花顺 Cookie",
    hint: "同花顺概念、热榜与行业数据的登录态。",
  },
  {
    key: "legulegu_token",
    label: "乐咕乐股 Token",
    hint: "乐咕乐股估值与宏观指标的访问令牌。",
  },
] as const;

export default function DataSourceCookiesCard({
  form,
  onChange,
  onSave,
  isSaving,
  stretch,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="数据源登录凭证（全局）"
      icon={<GlobalOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存数据源凭证"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        {COOKIE_FIELDS.map((field) => (
          <Col xs={24} lg={12} key={field.key}>
            <div style={fieldLabelStyle}>{field.label}</div>
            <Input.Password
              aria-label={field.label}
              value={form[field.key] || ""}
              onChange={(event) =>
                onChange({ [field.key]: event.target.value } as ConfigUpdate)
              }
              placeholder="已配置；输入新值以覆盖"
            />
            <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
              {field.hint}
            </div>
          </Col>
        ))}
      </Row>
    </SettingsCard>
  );
}
