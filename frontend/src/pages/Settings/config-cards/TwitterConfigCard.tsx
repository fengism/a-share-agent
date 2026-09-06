import { SearchOutlined } from "@ant-design/icons";
import { Col, Input, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function TwitterConfigCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="Twitter 财经账号配置（全局）"
      icon={<SearchOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存 Twitter 配置"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>Twitter/X 财经账号列表（每行一个，不含 @）</div>
          <Input.TextArea
            rows={4}
            value={(form.twitter_feeds ?? []).join("\n")}
            onChange={(event) => onChange({ twitter_feeds: event.target.value.split("\n") })}
            placeholder={"qinbafrank\n账号2\n账号3"}
          />
          <div style={{ marginTop: 4, fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            用于拉取 Twitter/X 上的财经推文和文章，每行填写一个账号名（不带 @）
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
