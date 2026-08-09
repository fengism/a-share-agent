import { memo, useEffect, useState } from "react";
import {
  BulbOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  DownOutlined,
  LoadingOutlined,
  ProfileOutlined,
  StopOutlined,
} from "@ant-design/icons";
import type {
  AgentPlanStep,
  AgentPlanStepStatus,
  ChatDisplayMessage,
} from "../../../types/chat";
import { TOOL_LABELS } from "../constants";
import { BlinkingCursor } from "./BlinkingCursor";
import { ToolCallCard } from "./ToolCallCard";

const PLAN_STATUS_LABELS: Record<AgentPlanStepStatus, string> = {
  pending: "等待执行",
  running: "执行中",
  completed: "已完成",
  failed: "执行失败",
  cancelled: "已停止",
};

function PlanStatusIcon({ status }: { status: AgentPlanStepStatus }) {
  switch (status) {
    case "running":
      return <LoadingOutlined spin />;
    case "completed":
      return <CheckCircleOutlined />;
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
  message,
}: {
  message: ChatDisplayMessage;
}) {
  const toolCalls = message.toolCalls || [];
  const planSteps = message.plan?.steps || [];
  const hasReasoning = Boolean(message.reasoningContent);
  const hasPlan = planSteps.length > 0;
  const hasTools = toolCalls.length > 0;
  const hasContent = Boolean(message.content);
  const isStreaming = Boolean(message.isStreaming);
  const hasProcess = hasPlan || hasReasoning || hasTools
    || (isStreaming && (Boolean(message.status) || !hasContent));
  const runningTool = toolCalls.find((toolCall) => toolCall.isExecuting);
  const runningPlanStep = planSteps.find((step) => step.status === "running");
  const settledPlanSteps = planSteps.filter(
    (step) => step.status !== "pending" && step.status !== "running",
  ).length;
  const hasPlanFailure = planSteps.some((step) => step.status === "failed");
  const hasPlanCancellation = planSteps.some((step) => step.status === "cancelled");
  const hasToolError = toolCalls.some((toolCall) => toolCall.isError);
  const hasCancelledTool = toolCalls.some((toolCall) => toolCall.isCancelled);
  const [expanded, setExpanded] = useState(isStreaming);

  useEffect(() => {
    if (isStreaming) {
      setExpanded(true);
    } else {
      setExpanded(false);
    }
  }, [isStreaming]);

  if (!hasProcess) return null;

  const summary = isStreaming
    ? runningTool
      ? `正在调用 ${TOOL_LABELS[runningTool.name] || runningTool.name}`
      : runningPlanStep
        ? `正在执行 ${runningPlanStep.title}`
        : message.status || (hasReasoning ? "正在思考" : "正在准备回答")
    : hasPlanCancellation || hasCancelledTool
        ? "处理已停止"
        : hasPlanFailure
          ? "处理完成，部分步骤失败"
          : hasToolError
            ? "处理完成，部分工具失败"
            : "已完成处理";
  const detail = isStreaming && hasPlan
    ? `${settledPlanSteps}/${planSteps.length} 个步骤已处理`
    : [hasPlan ? `${planSteps.length} 个规划步骤` : "", hasReasoning ? "包含思考过程" : "", hasTools ? `${toolCalls.length} 次工具调用` : ""]
        .filter(Boolean)
        .join(" · ");

  return (
    <section className={`chat-process${isStreaming ? " is-active" : ""}`}>
      <button
        type="button"
        className="chat-process-toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
      >
        <span className="chat-process-summary-icon" aria-hidden="true">
          {isStreaming ? <LoadingOutlined spin /> : <CheckCircleOutlined />}
        </span>
        <span className="chat-process-summary">
          <strong>{summary}</strong>
          {detail && <span>{detail}</span>}
        </span>
        <DownOutlined className={`chat-process-chevron${expanded ? " is-expanded" : ""}`} />
      </button>

      {expanded && (
        <div className="chat-process-body">
          {hasPlan && (
            <div className="chat-process-step">
              <span className="chat-process-step-icon is-plan" aria-hidden="true">
                <ProfileOutlined />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title">执行计划</div>
                <div className="chat-process-step-description">
                  {message.plan?.summary || `已拆分为 ${planSteps.length} 个专业分析步骤`}
                </div>
              </div>
            </div>
          )}

          {planSteps.map((step) => (
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

          {hasReasoning && (
            <div className="chat-process-step">
              <span className="chat-process-step-icon is-reasoning" aria-hidden="true">
                <BulbOutlined />
              </span>
              <div className="chat-process-step-content">
                <div className="chat-process-step-title">思考过程</div>
                <div className="chat-reasoning-content">
                  {message.reasoningContent}
                  {isStreaming && !hasTools && !hasContent && <BlinkingCursor />}
                </div>
              </div>
            </div>
          )}

          {toolCalls.map((toolCall) => (
            <ToolCallCard key={toolCall.id} toolCall={toolCall} />
          ))}

          {isStreaming && !hasPlan && !hasReasoning && !hasTools && (
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
