import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function TwitterConfigCard({ form, onChange, onSave, isSaving, stretch }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="Twitter 财经账号配置（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Twitter 配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>Twitter/X 财经账号列表</div>
          <Input.TextArea
            rows={2}
            value={(form.twitter_feeds ?? []).join("\n")}
            onChange={(event) => onChange({ twitter_feeds: event.target.value.split("\n") })}
            placeholder={"qinbafrank\n账号2"}
          />
          <div style={{ marginTop: 6, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            跟踪知名财经博主与宏观分析师动态，每行一个账号（不含 @）。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
