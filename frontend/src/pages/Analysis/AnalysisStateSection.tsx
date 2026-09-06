import { memo } from "react";
import { Alert } from "antd";
import type { AnalysisStage } from "../../api/sse";
import { useTokens } from "../../theme/hooks";
import AnalysisProgressSteps from "../../components/workflows/AnalysisProgressSteps";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import type { AgentProcessState } from "../../features/agent-process/agentProcess";

interface AnalysisStateSectionProps {
  isAnalyzing: boolean;
  error: string | null;
  stages: Array<AnalysisStage | null>;
  currentStageIndex: number;
  agentProcess: AgentProcessState;
}

export default memo(function AnalysisStateSection({
  isAnalyzing,
  error,
  stages,
  currentStageIndex,
  agentProcess,
}: AnalysisStateSectionProps) {
  const t = useTokens();

  return (
    <>
      {(isAnalyzing || error) && stages.length > 0 && (
        <AnalysisProgressSteps
          stages={stages}
          currentStageIndex={currentStageIndex}
          status={error ? "error" : "running"}
        />
      )}
      <AgentProcessPanel
        plan={agentProcess.plan}
        status={agentProcess.status}
        toolCalls={agentProcess.toolCalls}
        isRunning={isAnalyzing}
      />
      {error && !isAnalyzing && (
        <Alert
          message={`研究失败: ${error}`}
          type="error"
          showIcon
          closable
          style={{ marginBottom: t.space[4], borderRadius: t.radius.md }}
        />
      )}
    </>
  );
});
