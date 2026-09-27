import { ThunderboltOutlined } from "@ant-design/icons";
import { Col, InputNumber, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function ResearchBudgetCard({ form, onChange, onSave, isSaving }: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="研究预算与超时（全局）"
      icon={<ThunderboltOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存研究预算"
      onSave={onSave}
      isSaving={isSaving}
    >
      <Row gutter={[24, 16]}>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>个股报告生成超时（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.analysis_llm_timeout_seconds ?? 1200}
            onChange={(value) => onChange({ analysis_llm_timeout_seconds: value ?? 1200 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>采集研究超时（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.agent_research_timeout_seconds ?? 1200}
            onChange={(value) => onChange({ agent_research_timeout_seconds: value ?? 1200 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链补证时限（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.industry_chain_repair_timeout_seconds ?? 600}
            onChange={(value) => onChange({ industry_chain_repair_timeout_seconds: value ?? 600 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链主调研工具调用上限</div>
          <InputNumber
            min={8}
            max={128}
            value={form.industry_chain_tool_calls_total ?? 72}
            onChange={(value) => onChange({ industry_chain_tool_calls_total: value ?? 72 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链补证工具调用上限</div>
          <InputNumber
            min={4}
            max={48}
            value={form.industry_chain_repair_tool_calls_total ?? 36}
            onChange={(value) => onChange({ industry_chain_repair_tool_calls_total: value ?? 36 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>Chat 工具调用上限</div>
          <InputNumber
            min={1}
            max={128}
            value={form.chat_max_tool_calls_total ?? 32}
            onChange={(value) => onChange({ chat_max_tool_calls_total: value ?? 32 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24}>
          <div style={{ fontSize: "var(--c-font-sm)", color: colors.textMuted }}>
            保存后立即生效，无需重启。注意：`采集研究超时` 与 `Chat 工具调用上限` 由对话和产业链分析共用，调整会同时影响两侧；
            补证时限超时会保留初稿并标记降级。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
