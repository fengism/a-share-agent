import { SendOutlined } from "@ant-design/icons";
import { Col, Input, Row, Switch } from "antd";
import { useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function FeishuConfigCard({
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
      title="飞书推送配置"
      icon={<SendOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存飞书配置"
      onSave={onSave}
      isSaving={isSaving}
      stretch={stretch}
      isDirty={isDirty}
      onReset={onReset}
    >
      <Row gutter={[24, 16]}>
        <Col span={24}>
          <div style={fieldLabelStyle}>启用飞书推送</div>
          <Switch
            checked={form.feishu_enabled ?? true}
            onChange={(value) => onChange({ feishu_enabled: value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>App ID</div>
          <Input
            value={form.feishu_app_id || ""}
            onChange={(event) => onChange({ feishu_app_id: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>App Secret</div>
          <Input.Password
            value={form.feishu_app_secret || ""}
            onChange={(event) => onChange({ feishu_app_secret: event.target.value })}
            placeholder="输入新的 Secret 以覆盖"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>默认文档目录 Token</div>
          <Input
            value={form.feishu_folder_token || ""}
            onChange={(event) => onChange({ feishu_folder_token: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>Wiki 空间 ID（优先于文档目录）</div>
          <Input
            value={form.feishu_wiki_space_id || ""}
            onChange={(event) => onChange({ feishu_wiki_space_id: event.target.value })}
            placeholder="填写后文档将推送到知识库"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>复盘 Wiki 父节点 Token</div>
          <Input
            value={form.feishu_wiki_daily_review_parent || ""}
            onChange={(event) => onChange({ feishu_wiki_daily_review_parent: event.target.value })}
            placeholder="复盘文档挂载到此节点下"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>分析 Wiki 父节点 Token</div>
          <Input
            value={form.feishu_wiki_analysis_parent || ""}
            onChange={(event) => onChange({ feishu_wiki_analysis_parent: event.target.value })}
            placeholder="分析文档挂载到此节点下"
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>复盘文档目录 Token</div>
          <Input
            value={form.feishu_daily_review_folder || ""}
            onChange={(event) => onChange({ feishu_daily_review_folder: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>分析文档目录 Token</div>
          <Input
            value={form.feishu_analysis_folder || ""}
            onChange={(event) => onChange({ feishu_analysis_folder: event.target.value })}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>默认接收人 (open_id / chat_id)</div>
          <Input
            value={form.feishu_default_receiver || ""}
            onChange={(event) => onChange({ feishu_default_receiver: event.target.value })}
          />
        </Col>
      </Row>
    </SettingsCard>
  );
}
