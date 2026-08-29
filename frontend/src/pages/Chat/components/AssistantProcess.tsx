import { memo, useEffect, useState } from "react";
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
  message,
}: {
  message: ChatDisplayMessage;
}) {
  const toolCalls = message.toolCalls || [];
  const planSteps = message.plan?.steps || [];
  const hasPlan = Boolean(message.plan);
  const hasTools = toolCalls.length > 0;
  const hasContent = Boolean(message.content);
  const isStreaming = Boolean(message.isStreaming);
  const hasProcess = hasPlan || hasTools
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
      ? `正在调用 ${runningTool.name}`
      : runningPlanStep
        ? `正在执行 ${runningPlanStep.title}`
        : message.status || "正在准备回答"
    : hasPlanCancellation || hasCancelledTool
        ? "处理已停止"
        : hasPlanFailure
          ? "处理完成，部分步骤失败"
          : hasToolError
            ? "处理完成，部分工具失败"
            : hasPlanDegradation || hasSkippedTool
              ? "处理完成，存在数据缺口"
            : "已完成处理";
  const detail = isStreaming && hasPlan
    ? `${settledPlanSteps}/${planSteps.length} 个步骤已处理`
    : [hasPlan ? `${planSteps.length} 个规划步骤` : "", hasTools ? `${toolCalls.length} 次工具调用` : ""]
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

          {toolCalls.map((toolCall) => (
            <ToolCallCard key={toolCall.id} toolCall={toolCall} />
          ))}

          {isStreaming && !hasPlan && !hasTools && (
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
