import { RobotOutlined } from "@ant-design/icons";
import type { QuantBacktestRun } from "../../api/queries";
import StrategyDefinitionCard from "./authoring/StrategyDefinitionCard";
import StrategyDraftBacktestCard from "./authoring/StrategyDraftBacktestCard";
import StrategyDraftOverviewCard from "./authoring/StrategyDraftOverviewCard";
import { useStrategyAuthoringController } from "./useStrategyAuthoringController";
import "./quant-authoring.css";

interface StrategyAuthoringWorkbenchProps {
  isAdmin: boolean;
  onBacktestCreated: (run: QuantBacktestRun) => void;
}

export default function StrategyAuthoringWorkbench({
  isAdmin,
  onBacktestCreated,
}: StrategyAuthoringWorkbenchProps) {
  const controller = useStrategyAuthoringController(onBacktestCreated, isAdmin);
  // 发布写的是全局策略注册表，只有管理员能触发；普通用户可以用同一套草稿+回测流程
  const canPublish = (
    isAdmin
    && !controller.isDefinitionDirty
    && controller.selectedDraft?.status === "backtested"
    && Boolean(controller.selectedDraft.quality_gate?.passed)
  );
  const isBacktestDisabled = (
    !controller.selectedDraft
    || !["validated", "backtested"].includes(controller.selectedDraft.status)
    || controller.isBusy
    || controller.isDefinitionDirty
  );

  return (
    <section className="quant-authoring" aria-label="在线策略生成工作台">
      <div className="quant-section-heading">
        <div className="quant-section-heading-icon"><RobotOutlined /></div>
        <div>
          <span>{isAdmin ? "管理员能力" : "策略实验"}</span>
          <h2>在线策略生成工作台</h2>
          <p>
            自然语言生成受限 DSL，经过人工编辑、编译校验和回测门禁后再
            {isAdmin ? "发布到全局策略库" : "用于自己的回测"}。
          </p>
        </div>
      </div>

      <div className="quant-authoring-grid">
        <StrategyDraftOverviewCard
          drafts={controller.drafts}
          isDefinitionDirty={controller.isDefinitionDirty}
          isDraftsLoading={controller.isDraftsLoading}
          isGenerating={controller.isGenerating}
          prompt={controller.prompt}
          selectedDraft={controller.selectedDraft}
          selectedDraftId={controller.selectedDraftId}
          onGenerate={controller.generate}
          onPromptChange={controller.setPrompt}
          onSelectDraft={controller.selectDraftId}
        />
        <StrategyDefinitionCard
          canPublish={canPublish}
          definitionText={controller.definitionText}
          isDefinitionDirty={controller.isDefinitionDirty}
          isDefinitionLocked={controller.isDefinitionLocked}
          isPublishing={controller.isPublishing}
          isSaving={controller.isSaving}
          isValidating={controller.isValidating}
          registry={controller.registry}
          onDefinitionChange={controller.setDefinitionText}
          canManagePublish={isAdmin}
          onPublish={controller.publish}
          onSave={controller.save}
          onValidate={controller.validate}
        />
      </div>

      <StrategyDraftBacktestCard
        isBacktesting={controller.isBacktesting}
        isDisabled={isBacktestDisabled}
        onBacktest={controller.backtest}
      />
    </section>
  );
}
