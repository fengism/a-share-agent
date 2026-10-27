import { ThunderboltOutlined } from "@ant-design/icons";
import { Col, InputNumber, Row } from "antd";
import { useColors, useStyles } from "../../../styles/ui";
import { SettingsCard, type ConfigCardProps } from "../SettingsCard";

export default function ResearchBudgetCard({
  form,
  onChange,
  onSave,
  isSaving,
  isDirty,
  onReset,
}: ConfigCardProps) {
  const { fieldLabelStyle } = useStyles();
  const colors = useColors();

  return (
    <SettingsCard
      title="研究预算与超时（全局）"
      icon={<ThunderboltOutlined style={{ marginRight: 8 }} />}
      saveLabel="保存研究预算"
      onSave={onSave}
      isSaving={isSaving}
      isDirty={isDirty}
      onReset={onReset}
    >
      <div style={{ color: colors.textMuted, marginTop: -4, marginBottom: 16, fontSize: "var(--c-font-sm)" }}>
        控制 AI Agent 在生成深度研报和梳理产业链图谱时的思考耗时与调用轮次上限。默认参数经过实测调优，超时越长研究越详实，轮次上限可防止推理死循环。
      </div>

      <div style={{ fontWeight: "var(--c-weight-semibold)", color: colors.textPrimary, marginBottom: 12 }}>
        📊 个股深度研报时限
      </div>
      <Row gutter={[24, 16]} style={{ marginBottom: 20 }}>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>个股报告生成超时（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.analysis_llm_timeout_seconds ?? 1200}
            onChange={(value) => onChange({ analysis_llm_timeout_seconds: value ?? 1200 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={12}>
          <div style={fieldLabelStyle}>采集研究超时（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.agent_research_timeout_seconds ?? 1200}
            onChange={(value) => onChange({ agent_research_timeout_seconds: value ?? 1200 })}
            style={{ width: "100%" }}
          />
        </Col>
      </Row>

      <div style={{ fontWeight: "var(--c-weight-semibold)", color: colors.textPrimary, marginBottom: 12 }}>
        🕸️ 产业链图谱调研与补证预算
      </div>
      <Row gutter={[24, 16]} style={{ marginBottom: 20 }}>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链主调研时限（秒）</div>
          <InputNumber
            min={60}
            max={14400}
            value={form.industry_chain_research_timeout_seconds ?? 2400}
            onChange={(value) => onChange({ industry_chain_research_timeout_seconds: value ?? 2400 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链补证取证时限（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.industry_chain_repair_research_timeout_seconds ?? 1200}
            onChange={(value) => onChange({ industry_chain_repair_research_timeout_seconds: value ?? 1200 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={8}>
          <div style={fieldLabelStyle}>产业链补证重写时限（秒）</div>
          <InputNumber
            min={30}
            max={7200}
            value={form.industry_chain_repair_synthesis_timeout_seconds ?? 900}
            onChange={(value) => onChange({ industry_chain_repair_synthesis_timeout_seconds: value ?? 900 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={6}>
          <div style={fieldLabelStyle}>主调研最大轮次</div>
          <InputNumber
            min={2}
            max={24}
            value={form.industry_chain_max_rounds ?? 10}
            onChange={(value) => onChange({ industry_chain_max_rounds: value ?? 10 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={6}>
          <div style={fieldLabelStyle}>补证最大轮次</div>
          <InputNumber
            min={1}
            max={12}
            value={form.industry_chain_repair_max_rounds ?? 5}
            onChange={(value) => onChange({ industry_chain_repair_max_rounds: value ?? 5 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={6}>
          <div style={fieldLabelStyle}>主调研工具调用上限</div>
          <InputNumber
            min={8}
            max={300}
            value={form.industry_chain_tool_calls_total ?? 160}
            onChange={(value) => onChange({ industry_chain_tool_calls_total: value ?? 160 })}
            style={{ width: "100%" }}
          />
        </Col>
        <Col span={24} sm={6}>
          <div style={fieldLabelStyle}>补证工具调用上限</div>
          <InputNumber
            min={4}
            max={160}
            value={form.industry_chain_repair_tool_calls_total ?? 80}
            onChange={(value) => onChange({ industry_chain_repair_tool_calls_total: value ?? 80 })}
            style={{ width: "100%" }}
          />
        </Col>
      </Row>

      <div style={{ fontWeight: "var(--c-weight-semibold)", color: colors.textPrimary, marginBottom: 12 }}>
        💬 对话与交互上限
      </div>
      <Row gutter={[24, 16]}>
        <Col span={24} sm={12}>
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
            保存后立即生效，无需重启。主调研与补证阶段使用独立轮次、时限和工具预算；轮次只是上限，只有证据缺口持续缩小时才继续，无进展会提前停止，避免无意义消耗 Token。
          </div>
        </Col>
      </Row>
    </SettingsCard>
  );
}
