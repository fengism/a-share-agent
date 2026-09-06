import { LoadingOutlined, StopOutlined } from "@ant-design/icons";
import { Button, Dropdown, Space, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useActiveWorkflows, useCancelWorkflow, type WorkflowJob } from "../api/queries";
import { stopChatRuntime } from "../features/chat/chatRuntime";
import { useAnalysisStore } from "../store/analysisStore";
import { useChatStore } from "../store/chatStore";
import { useIndustryChainWorkflowStore } from "../store/industryChainWorkflowStore";
import { buildStockAnalysisUrl } from "../utils/stockLinks";

const { Text } = Typography;

function workflowLabel(job: WorkflowJob) {
  if (job.kind === "analysis") return `个股研究 · ${String(job.request.code || job.dedupe_key)}`;
  if (job.kind === "industry_chain") return `产业研究 · ${String(job.request.name || job.dedupe_key)}`;
  return null;
}

function workflowTarget(job: WorkflowJob) {
  if (job.kind === "analysis") return buildStockAnalysisUrl(String(job.request.code || job.dedupe_key));
  if (job.kind === "industry_chain") return `/industry-chain/${encodeURIComponent(String(job.request.name || job.dedupe_key))}`;
  return "/";
}

export default function GlobalTaskIndicator({ compact = false }: { compact?: boolean }) {
  const navigate = useNavigate();
  const activeWorkflows = useActiveWorkflows();
  const cancelWorkflow = useCancelWorkflow();
  const chatStreaming = useChatStore((state) => state.isStreaming);
  const chatLabel = useChatStore((state) => state.activeRunLabel);
  const localAnalysisRun = useAnalysisStore((state) => state.activeRun);
  const localAnalysisJobId = useAnalysisStore((state) => state.jobId);
  const localAnalysisRunning = useAnalysisStore((state) => state.isAnalyzing);
  const localAnalysisCancelling = useAnalysisStore((state) => state.isCancelling);
  const cancelLocalAnalysis = useAnalysisStore((state) => state.cancelActiveRun);
  const localIndustryName = useIndustryChainWorkflowStore((state) => state.name);
  const localIndustryJobId = useIndustryChainWorkflowStore((state) => state.jobId);
  const localIndustryRunning = useIndustryChainWorkflowStore((state) => state.isAnalyzing);
  const localIndustryCancelling = useIndustryChainWorkflowStore((state) => state.isCancelling);
  const cancelLocalIndustry = useIndustryChainWorkflowStore((state) => state.cancelActiveRun);
  const workflows = (activeWorkflows.data ?? []).filter((job) => (
    (job.kind === "analysis" || job.kind === "industry_chain")
    && !(job.kind === "analysis" && localAnalysisJobId === job.id)
    && !(job.kind === "industry_chain" && localIndustryJobId === job.id)
  ));
  const localTasks = [
    ...(localAnalysisRun && localAnalysisRunning ? [{
      key: `local-analysis:${localAnalysisRun.runId}`,
      label: `个股研究 · ${localAnalysisRun.code}`,
      target: `/${useAnalysisStore.getState().preferredRoute}/${encodeURIComponent(localAnalysisRun.code)}`,
      cancelling: localAnalysisCancelling,
      stop: () => cancelLocalAnalysis(),
    }] : []),
    ...(localIndustryRunning ? [{
      key: "local-industry",
      label: `产业研究 · ${localIndustryName}`,
      target: `/industry-chain/${encodeURIComponent(localIndustryName)}`,
      cancelling: localIndustryCancelling,
      stop: () => cancelLocalIndustry(),
    }] : []),
  ];
  const count = workflows.length + localTasks.length + (chatStreaming ? 1 : 0);
  if (count === 0) return null;

  const stopWorkflow = async (job: WorkflowJob) => {
    try {
      const stopped = await cancelWorkflow.mutateAsync(job.id);
      message.info(
        stopped.status === "cancelled"
          ? `${workflowLabel(job)}已停止`
          : `${workflowLabel(job)}已结束`,
      );
    } catch (error) {
      message.error(error instanceof Error ? error.message : "停止任务失败");
    }
  };

  const items = [
    ...localTasks.map((task) => ({
      key: task.key,
      label: (
        <div className="global-task-indicator__item">
          <button type="button" onClick={() => navigate(task.target)}>
            <LoadingOutlined spin /> {task.label}
          </button>
          <Button
            type="text"
            danger
            size="small"
            icon={<StopOutlined />}
            aria-label={`停止${task.label}`}
            loading={task.cancelling}
            onClick={(event) => {
              event.stopPropagation();
              void task.stop();
            }}
          />
        </div>
      ),
    })),
    ...workflows.map((job) => ({
      key: job.id,
      label: (
        <div className="global-task-indicator__item">
          <button type="button" onClick={() => navigate(workflowTarget(job))}>
            <LoadingOutlined spin /> {workflowLabel(job)}
          </button>
          <Button
            type="text"
            danger
            size="small"
            icon={<StopOutlined />}
            aria-label={`停止${workflowLabel(job)}`}
            loading={cancelWorkflow.isPending && cancelWorkflow.variables === job.id}
            onClick={(event) => {
              event.stopPropagation();
              void stopWorkflow(job);
            }}
          />
        </div>
      ),
    })),
    ...(chatStreaming ? [{
      key: "chat-runtime",
      label: (
        <div className="global-task-indicator__item">
          <button type="button" onClick={() => navigate("/chat")}>
            <LoadingOutlined spin /> {chatLabel ? `对话 · ${chatLabel}` : "对话生成中"}
          </button>
          <Button
            type="text"
            danger
            size="small"
            icon={<StopOutlined />}
            aria-label="停止对话生成"
            onClick={(event) => {
              event.stopPropagation();
              stopChatRuntime();
            }}
          />
        </div>
      ),
    }] : []),
  ];

  return (
    <Dropdown menu={{ items }} trigger={["click"]} placement="bottomRight">
      <Button
        className="global-task-indicator"
        aria-label={`${count} 个任务运行中`}
        icon={<LoadingOutlined spin />}
      >
        {compact ? count : <Space size={4}><Text>运行中</Text><strong>{count}</strong></Space>}
      </Button>
    </Dropdown>
  );
}
