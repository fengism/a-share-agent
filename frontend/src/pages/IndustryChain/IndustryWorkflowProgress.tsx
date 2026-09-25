import { CheckCircleOutlined, LoadingOutlined } from "@ant-design/icons";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import WorkflowProgressPanel from "../../components/workflows/WorkflowProgressPanel";
import type { AgentProcessState } from "../../features/agent-process/agentProcess";
import type { IndustryWorkflowStatus } from "../../store/industryChainWorkflowStore";
import { INDUSTRY_CHAIN_STAGES } from "./industryWorkflow";

export default function IndustryWorkflowProgress({ currentStage, status, message, agentProcess }: {
  currentStage: number;
  status: IndustryWorkflowStatus;
  message: string;
  agentProcess: AgentProcessState;
}) {
  const isRunning = status === "running";
  return (
    <WorkflowProgressPanel
      current={currentStage}
      status={status}
      message={message}
      items={INDUSTRY_CHAIN_STAGES.map((stage, index) => ({
        title: stage.title,
        icon: currentStage === index && isRunning
          ? <LoadingOutlined spin />
          : currentStage > index ? <CheckCircleOutlined /> : undefined,
      }))}
    >
      <AgentProcessPanel
        plan={agentProcess.plan}
        status={agentProcess.status}
        toolCalls={agentProcess.toolCalls}
        rounds={agentProcess.rounds}
        termination={agentProcess.termination}
        isRunning={isRunning && currentStage === 0}
      />
    </WorkflowProgressPanel>
  );
}
