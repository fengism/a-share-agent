import { memo, useId, useState } from "react";
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  DownOutlined,
  LoadingOutlined,
  ProfileOutlined,
  StopOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import type {
  AgentPlanStep,
  AgentPlanStepStatus,
  ChatDisplayMessage,
} from "../../../types/chat";
import { finalizeChatProcess } from "../../../features/chat/chatProcess";
import { ChatProcessTimeline } from "./ChatProcessTimeline";
import { ModelReasoning } from "./ModelReasoning";
import { ToolCallCard } from "./ToolCallCard";

const PLAN_STATUS_LABELS: Record<AgentPlanStepStatus, string> = {
  pending: "等待执行",
  running: "执行中",
  completed: "已完成",
  degraded: "数据缺口",
  failed: "执行失败",
  cancelled: "已停止",
};

function PlanStatusIcon({ status }: { status: AgentPlanStepStatus }) {
  switch (status) {
    case "running":
      return <LoadingOutlined spin />;
    case "completed":
      return <CheckCircleOutlined />;
    case "degraded":
      return <WarningOutlined />;
    case "failed":
      return <CloseCircleOutlined />;
    case "cancelled":
      return <StopOutlined />;
    case "pending":
      return <ClockCircleOutlined />;
  }
}

function planStepDescription(step: AgentPlanStep): string {
  const retry = step.attempt > 1 ? `第 ${step.attempt} 次执行` : "";
  const description = step.detail || step.description || "等待前置步骤完成";
  return [retry, description].filter(Boolean).join(" · ");
}

export const AssistantProcess = memo(function AssistantProcess({
  message: inputMessage,
}: {
  message: ChatDisplayMessage;
}) {
  // Defensive projection for old snapshots with stale child execution flags.
  const message = inputMessage.isStreaming && !inputMessage.processOutcome
    ? inputMessage : finalizeChatProcess(inputMessage);
  const toolCalls = message.toolCalls || [];
  const planSteps = message.plan?.steps || [];
  const hasPlan = Boolean(message.plan);
  const hasTools = toolCalls.length > 0;
  const hasContent = Boolean(message.content);
  const hasReasoning = Boolean(message.reasoningContent?.trim());
  const isStreaming = Boolean(message.isStreaming);
  const updates = message.processUpdates || [];
  const hasUpdates = updates.length > 0;
  const outcome = message.processOutcome;
  const rounds = updates.flatMap((update) => update.type === "round" ? [update.round] : []);
  const runningRound = rounds.find((round) => round.status === "running");
  const hasDegradedRound = rounds.some((round) => round.status === "degraded");
  const hasCancelledRound = rounds.some((round) => round.status === "cancelled");
  const hasFailedRound = rounds.some((round) => round.status === "failed");
  const hasProcess = hasPlan || hasTools || hasUpdates || hasReasoning
    || (Boolean(outcome) && outcome !== "completed")
    || (isStreaming && (Boolean(message.status) || !hasContent));
  const runningTool = toolCalls.find((toolCall) => toolCall.isExecuting);
  const runningPlanStep = planSteps.find((step) => step.status === "running");
  const settledPlanSteps = planSteps.filter(
    (step) => step.status !== "pending" && step.status !== "running",
  ).length;
  const hasPlanFailure = planSteps.some((step) => step.status === "failed");
  const hasPlanDegradation = planSteps.some((step) => step.status === "degraded");
  const degradedPlanSteps = planSteps.filter((step) => step.status === "degraded");
  const regularPlanSteps = planSteps.filter((step) => step.status !== "degraded");
  const hasPlanCancellation = planSteps.some((step) => step.status === "cancelled");
  const hasToolError = toolCalls.some((toolCall) => toolCall.isError);
  const hasSkippedTool = toolCalls.some((toolCall) => toolCall.isSkipped);
  const hasCancelledTool = toolCalls.some((toolCall) => toolCall.isCancelled);
  // Follow streaming by default, but never override the user's manual choice.
  const [expandedOverride, setExpandedOverride] = useState<boolean | null>(null);
  const expanded = expandedOverride ?? isStreaming;
  const bodyId = useId();

  if (!hasProcess) return null;

  const summary = isStreaming
    ? runningTool
      ? `正在调用 ${runningTool.name}`
      : runningPlanStep
        ? `正在执行 ${runningPlanStep.title}`
        : message.status || (hasContent ? "正在生成回答" : hasReasoning ? "模型正在推理" : runningRound ? `正在调研：${runningRound.objective || `第 ${runningRound.round_index} 轮`}` : "正在准备回答")
    : outcome === "failed"
      ? "处理失败"
      : outcome === "cancelled" || hasPlanCancellation || hasCancelledTool || hasCancelledRound
        ? "处理已停止"
          : hasPlanFailure || hasFailedRound
          ? "处理完成，部分步骤失败"
          : hasToolError
            ? "处理完成，部分工具失败"
            : outcome === "partial" || hasPlanDegradation || hasSkippedTool || hasDegradedRound
              ? "处理完成，存在数据缺口"
            : "已完成处理";
  const detail = isStreaming && hasPlan
    ? `${settledPlanSteps}/${planSteps.length} 个步骤已处理`
    : [hasReasoning ? "模型推理" : "", hasUpdates ? `${updates.length} 条过程记录` : "", hasPlan ? `${planSteps.length} 个规划步骤` : "", hasTools ? `${toolCalls.length} 次工具调用` : ""]
        .filter(Boolean)
        .join(" · ");

  return (
    <section className={`chat-process${isStreaming ? " is-active" : ""}`} aria-label="思考与执行过程">
      <button
        type="button"
        className="chat-process-toggle"
        aria-expanded={expanded}
        aria-controls={bodyId}
        onClick={() => setExpandedOverride(!expanded)}
      >
        <span className="chat-process-summary-icon" aria-hidden="true">
          {isStreaming ? <LoadingOutlined spin />
            : outcome === "failed" ? <CloseCircleOutlined />
            : outcome === "cancelled" || hasPlanCancellation || hasCancelledTool || hasCancelledRound ? <StopOutlined />
              : hasPlanFailure || hasToolError || hasFailedRound ? <CloseCircleOutlined />
                : outcome === "partial" || hasPlanDegradation || hasSkippedTool || hasDegradedRound ? <WarningOutlined />
                  : <CheckCircleOutlined />}
        </span>
        <span className="chat-process-summary">
          <strong>{summary}</strong>
          <span>思考与执行过程{detail ? ` · ${detail}` : ""}</span>
        </span>
        <DownOutlined className={`chat-process-chevron${expanded ? " is-expanded" : ""}`} />
      </button>

      {expanded && (
        <div className="chat-process-body" id={bodyId}>
          <p className="chat-process-note">展示模型接口返回的推理、执行进度与调研摘要；推理内容不等同于最终结论。</p>
          {hasReasoning && <ModelReasoning content={message.reasoningContent!} blocks={message.reasoningBlocks} isStreaming={isStreaming} />}
          {hasPlan && (
            <div className="chat-process-step">
              <span className="chat-process-step-icon is-plan" aria-hidden="true">
                <ProfileOutlined />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title">思路与计划</div>
                <div className="chat-process-step-description">
                  {message.plan?.summary || `已拆分为 ${planSteps.length} 个专业分析步骤`}
                </div>
              </div>
            </div>
          )}

          {regularPlanSteps.map((step) => (
            <div className="chat-process-step" key={step.id}>
              <span
                className={`chat-process-step-icon is-${step.status}`}
                aria-hidden="true"
              >
                <PlanStatusIcon status={step.status} />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title chat-plan-step-title">
                  <span>{step.title}</span>
                  <span className={`chat-plan-step-status is-${step.status}`}>
                    {PLAN_STATUS_LABELS[step.status]}
                  </span>
                </div>
                <div className="chat-process-step-description">
                  {planStepDescription(step)}
                </div>
              </div>
            </div>
          ))}

          {degradedPlanSteps.length > 0 ? (
            <div className="chat-process-step">
              <span className="chat-process-step-icon is-degraded" aria-hidden="true">
                <WarningOutlined />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title">数据缺口</div>
                <div className="chat-process-step-description">
                  {degradedPlanSteps.map((step) => (
                    <div key={step.id}>
                      {step.title}{step.detail || step.description ? ` · ${step.detail || step.description}` : ""}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : null}

          <ChatProcessTimeline updates={updates} isStreaming={isStreaming} />

          {toolCalls.map((toolCall) => (
            <ToolCallCard key={toolCall.id} toolCall={toolCall} />
          ))}

          {isStreaming && !hasPlan && !hasTools && !hasUpdates && !hasReasoning && (
            <div className="chat-process-step">
              <span className="chat-process-step-icon" aria-hidden="true">
                <LoadingOutlined spin />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title">{message.status || "正在理解你的问题"}</div>
                <div className="chat-process-step-description">请稍候，正在组织回答…</div>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
});
