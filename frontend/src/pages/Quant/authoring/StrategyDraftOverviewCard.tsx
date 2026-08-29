import { RobotOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Empty, Input, Select, Space, Tag, Typography } from "antd";
import type { QuantStrategyDraft } from "../../../api/queries";
import { STRATEGY_DRAFT_STATUS_META } from "../strategyAuthoring";

const { Paragraph, Text } = Typography;

interface StrategyDraftOverviewCardProps {
  drafts: QuantStrategyDraft[];
  isDefinitionDirty: boolean;
  isDraftsLoading: boolean;
  isGenerating: boolean;
  prompt: string;
  selectedDraft?: QuantStrategyDraft;
  selectedDraftId: string;
  onGenerate: () => Promise<void>;
  onPromptChange: (value: string) => void;
  onSelectDraft: (draftId: string) => void;
}

export default function StrategyDraftOverviewCard({
  drafts,
  isDefinitionDirty,
  isDraftsLoading,
  isGenerating,
  prompt,
  selectedDraft,
  selectedDraftId,
  onGenerate,
  onPromptChange,
  onSelectDraft,
}: StrategyDraftOverviewCardProps) {
  const status = selectedDraft ? STRATEGY_DRAFT_STATUS_META[selectedDraft.status] : null;
  const qualityGate = selectedDraft?.quality_gate;
  const hasHoldoutMetrics = qualityGate && (
    qualityGate.holdout_trade_count != null
    || qualityGate.holdout_max_drawdown != null
    || qualityGate.holdout_sharpe_ratio != null
  );

  return (
    <Card className="quant-authoring-card" title={<Space><RobotOutlined />生成与草稿</Space>}>
      <Text strong>策略需求</Text>
      <Input.TextArea
        value={prompt}
        onChange={(event) => onPromptChange(event.target.value)}
        rows={5}
        maxLength={4000}
        showCount
        placeholder="例如：使用 20 日和 60 日均线，短均线上穿时买入，下穿时退出，参数允许调整。"
      />
      <Button
        type="primary"
        icon={<RobotOutlined />}
        loading={isGenerating}
        onClick={() => void onGenerate()}
      >
        生成受限策略草稿
      </Button>

      <div className="quant-authoring-divider" />
      <Text strong>草稿版本</Text>
      <Select
        value={selectedDraftId || undefined}
        loading={isDraftsLoading}
        placeholder="选择策略草稿"
        onChange={onSelectDraft}
        options={drafts.map((draft) => ({
          value: draft.id,
          label: `${draft.definition.name} · ${STRATEGY_DRAFT_STATUS_META[draft.status].label}`,
        }))}
      />
      {selectedDraft ? (
        <div className="quant-draft-summary">
          <Space wrap>
            <Tag color={status?.color}>{status?.label}</Tag>
            <Tag>{selectedDraft.definition.key}@{selectedDraft.definition.version}</Tag>
            {isDefinitionDirty ? <Tag color="gold">有未保存修改</Tag> : null}
          </Space>
          <Text type="secondary" copyable>{selectedDraft.definition_hash}</Text>
          {selectedDraft.published_path ? (
            <Text type="secondary" copyable>发布文件：{selectedDraft.published_path}</Text>
          ) : null}
          <Paragraph>{selectedDraft.definition.description}</Paragraph>
        </div>
      ) : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="尚无在线策略草稿" />}

      {qualityGate ? (
        <Alert
          type={qualityGate.passed ? "success" : selectedDraft.status === "testing" ? "info" : "warning"}
          showIcon
          title={qualityGate.passed ? "回测质量门禁已通过" : `回测状态：${qualityGate.run_status}`}
          description={(
            <div className="quant-quality-gate-summary">
              <span>
                全样本：交易 {qualityGate.trade_count ?? "-"} 次 ·
                最大回撤 {qualityGate.max_drawdown ?? "-"}% ·
                夏普 {qualityGate.sharpe_ratio ?? "-"}
              </span>
              {hasHoldoutMetrics ? (
                <span>
                  后段样本：交易 {qualityGate.holdout_trade_count ?? "-"} 次 ·
                  最大回撤 {qualityGate.holdout_max_drawdown ?? "-"}% ·
                  夏普 {qualityGate.holdout_sharpe_ratio ?? "-"}
                </span>
              ) : null}
              {qualityGate.errors?.length ? (
                <Text type="danger">{qualityGate.errors.join("；")}</Text>
              ) : null}
            </div>
          )}
        />
      ) : null}
    </Card>
  );
}
