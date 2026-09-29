import type { AnalysisStage } from "../../api/sse";
import WorkflowProgressPanel, { type WorkflowProgressStatus } from "./WorkflowProgressPanel";

const STAGE_NAMES = ["Agent 调研与证据校验", "构造结构化请求", "AI 综合分析", "结果校验与数据时效", "报告归档与历史更新"];

interface Props {
  stages: Array<AnalysisStage | null>;
  currentStageIndex: number;
  status: WorkflowProgressStatus;
}

export default function AnalysisProgressSteps({ stages, currentStageIndex, status }: Props) {
  const items = stages.map((stage, index) => {
    const stepStatus =
      !stage
        ? ("wait" as const)
        : stage.status === "started"
        ? (status === "running" ? "process" as const : status === "error" ? "error" as const : "wait" as const)
        : stage.status === "completed"
          ? ("finish" as const)
          : stage.status === "failed"
            ? ("error" as const)
            : ("wait" as const);

    const description =
      stage?.detail ||
      (stage?.status === "completed" && stage.duration_ms
        ? `${stage.duration_ms}ms`
        : undefined);

    return {
      title: stage?.name || STAGE_NAMES[index] || `阶段 ${index + 1}`,
      status: stepStatus,
      description,
    };
  });

  return (
    <WorkflowProgressPanel
      current={currentStageIndex}
      items={items}
      status={status}
    />
  );
}
