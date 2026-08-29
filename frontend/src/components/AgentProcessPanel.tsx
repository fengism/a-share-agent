import { BulbOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, DownOutlined, LoadingOutlined, RobotOutlined, StopOutlined, ToolOutlined, WarningOutlined } from "@ant-design/icons";
import type { ReactElement } from "react";
import { useEffect, useState } from "react";
import { Steps, Tag, Typography } from "antd";
import type { AgentPlan, AgentPlanStepStatus, ToolCallDisplay } from "../types/chat";
import { toolDisplayName } from "../features/agent-process/toolPresentation";
import ToolResultSummary from "../features/agent-process/ToolResultSummary";
import { formatToolArguments } from "../utils/toolCall";
import { semanticTagStyle } from "../styles/ui";
import type { SemanticTagColor } from "../styles/ui";

const { Text } = Typography;

const PLAN_STATUS: Record<AgentPlanStepStatus, "wait" | "process" | "finish" | "error"> = {
  pending: "wait",
  running: "process",
  completed: "finish",
  degraded: "finish",
  failed: "error",
  cancelled: "error",
};

function toolStatus(tool: ToolCallDisplay): { color: SemanticTagColor; label: string; icon: ReactElement } {
  if (tool.isExecuting) return { color: "primary", label: "执行中", icon: <LoadingOutlined spin /> };
  if (tool.isSkipped) return { color: "warning", label: "已跳过", icon: <WarningOutlined /> };
  if (tool.isError) return { color: "up", label: "失败", icon: <CloseCircleOutlined /> };
  if (tool.isCancelled) return { color: "warning", label: "已停止", icon: <StopOutlined /> };
  return { color: "down", label: "已完成", icon: <CheckCircleOutlined /> };
}

function groupedToolStatus(tools: ToolCallDisplay[]) {
  if (tools.some((tool) => tool.isExecuting)) {
    return { color: "primary" as SemanticTagColor, label: "执行中", icon: <LoadingOutlined spin /> };
  }
  const failed = tools.filter((tool) => tool.isError).length;
  if (failed > 0) {
    return {
      color: "up" as SemanticTagColor,
      label: tools.length > 1 ? `${failed}/${tools.length} 失败` : "失败",
      icon: <CloseCircleOutlined />,
    };
  }
  const skipped = tools.filter((tool) => tool.isSkipped).length;
  if (skipped > 0) {
    return {
      color: "warning" as SemanticTagColor,
      label: tools.length > 1 ? `${skipped}/${tools.length} 已跳过` : "已跳过",
      icon: <WarningOutlined />,
    };
  }
  if (tools.every((tool) => tool.isCancelled)) {
    return { color: "warning" as SemanticTagColor, label: "已停止", icon: <StopOutlined /> };
  }
  return {
    color: "down" as SemanticTagColor,
    label: tools.length > 1 ? `${tools.length} 次完成` : "已完成",
    icon: <CheckCircleOutlined />,
  };
}

export default function AgentProcessPanel({
  plan,
  status,
  toolCalls,
  isRunning,
}: {
  plan?: AgentPlan;
  status: string;
  toolCalls: ToolCallDisplay[];
  isRunning: boolean;
}) {
  const steps = plan?.steps ?? [];
  const hasFailure = steps.some((step) => step.status === "failed")
    || toolCalls.some((tool) => tool.isError);
  const hasCancellation = steps.some((step) => step.status === "cancelled")
    || toolCalls.some((tool) => tool.isCancelled);
  const hasDegradation = steps.some((step) => step.status === "degraded");
  const hasSkippedTool = toolCalls.some((tool) => tool.isSkipped);
  const degradedSteps = steps.filter((step) => step.status === "degraded");
  const regularSteps = steps.filter((step) => step.status !== "degraded");
  const settledSteps = steps.filter((step) => (
    step.status !== "pending" && step.status !== "running"
  )).length;
  const [expanded, setExpanded] = useState(isRunning);

  useEffect(() => {
    setExpanded(isRunning);
  }, [isRunning]);

  if (!plan && toolCalls.length === 0 && !status) return null;

  const badge = hasFailure
    ? { color: "up" as SemanticTagColor, label: "执行失败", icon: <CloseCircleOutlined /> }
    : isRunning
      ? { color: "primary" as SemanticTagColor, label: "执行中", icon: <LoadingOutlined spin /> }
      : hasCancellation
        ? { color: "warning" as SemanticTagColor, label: "已停止", icon: <StopOutlined /> }
        : hasDegradation || hasSkippedTool
          ? { color: "warning" as SemanticTagColor, label: "数据缺口", icon: <WarningOutlined /> }
          : { color: "down" as SemanticTagColor, label: "已完成", icon: <CheckCircleOutlined /> };
  const detail = [
    steps.length > 0 ? `${settledSteps}/${steps.length} 个步骤` : "",
    toolCalls.length > 0 ? `${toolCalls.length} 次工具调用` : "",
  ].filter(Boolean).join(" · ");
  const toolGroups = Array.from(
    toolCalls.reduce((groups, tool) => {
      const existing = groups.get(tool.name) ?? [];
      existing.push(tool);
      groups.set(tool.name, existing);
      return groups;
    }, new Map<string, ToolCallDisplay[]>()),
  );

  return (
    <section style={{ marginTop: "var(--c-space-5)", paddingTop: "var(--c-space-4)", borderTop: "1px solid var(--c-border)" }}>
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        style={{ display: "flex", width: "100%", alignItems: "center", justifyContent: "space-between", gap: "var(--c-space-3)", padding: 0, border: 0, color: "inherit", background: "transparent", textAlign: "left", cursor: "pointer" }}
      >
        <div style={{ display: "flex", minWidth: 0, alignItems: "center", gap: "var(--c-space-2)" }}>
          <RobotOutlined style={{ color: "var(--c-primary)" }} />
          <div>
            <Text strong>Agent 思考与执行</Text>
            {detail ? <div style={{ color: "var(--c-text-muted)", fontSize: "var(--c-font-sm)" }}>{detail}</div> : null}
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--c-space-2)" }}>
          <Tag icon={badge.icon} style={semanticTagStyle(badge.color)}>
            {badge.label}
          </Tag>
          <DownOutlined style={{ transform: expanded ? "rotate(180deg)" : undefined, transition: "transform .2s" }} />
        </div>
      </button>

      {expanded ? (
        <div style={{ marginTop: "var(--c-space-3)" }}>
          {status && <div style={{ color: "var(--c-text-secondary)", fontSize: "var(--c-font-md)", marginBottom: "var(--c-space-3)" }}>{status}</div>}

          {plan?.summary ? (
            <div style={{ display: "flex", alignItems: "flex-start", gap: "var(--c-space-2)", marginBottom: "var(--c-space-3)", color: "var(--c-text-secondary)" }}>
              <BulbOutlined style={{ marginTop: 3, color: "var(--c-accent)" }} />
              <div>
                <Text strong>思路摘要</Text>
                <div style={{ marginTop: "var(--c-space-1)" }}>{plan.summary}</div>
              </div>
            </div>
          ) : null}

          {regularSteps.length ? (
            <Steps
              orientation="vertical"
              size="small"
              items={regularSteps.map((step) => ({
                title: step.title,
                content: step.detail || step.description,
                status: PLAN_STATUS[step.status],
                icon: step.status === "pending" ? <ClockCircleOutlined /> : undefined,
              }))}
            />
          ) : null}

          {degradedSteps.length > 0 ? (
            <div aria-label="Agent 数据缺口" style={{ marginBottom: "var(--c-space-3)", padding: "var(--c-space-3)", border: "1px solid color-mix(in srgb, var(--c-warning) 45%, var(--c-border))", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-warning) 8%, transparent)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "var(--c-space-2)", color: "var(--c-warning)", fontWeight: 600 }}>
                <WarningOutlined />
                数据缺口
              </div>
              {degradedSteps.map((step) => (
                <div key={step.id} style={{ marginTop: "var(--c-space-2)", color: "var(--c-text-secondary)" }}>
                  <strong>{step.title}</strong>
                  {step.detail || step.description ? ` · ${step.detail || step.description}` : ""}
                </div>
              ))}
            </div>
          ) : null}

          {toolGroups.length > 0 && (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--c-space-2)", marginTop: "var(--c-space-1)" }}>
              {toolGroups.map(([name, tools]) => {
                const state = groupedToolStatus(tools);
                return (
                  <details key={name} style={{ border: "1px solid var(--c-border)", borderRadius: "var(--c-radius-md)", padding: "var(--c-space-2) var(--c-space-3)" }}>
                    <summary style={{ display: "flex", alignItems: "center", gap: "var(--c-space-2)", cursor: "pointer" }}>
                      <ToolOutlined />
                      <span style={{ display: "flex", minWidth: 0, flex: 1, flexWrap: "wrap", alignItems: "center", gap: "var(--c-space-2)" }}>
                        <Text>{toolDisplayName(name)}</Text>
                        {toolDisplayName(name) !== name ? <Text code>{name}</Text> : null}
                      </span>
                      <Tag icon={state.icon} style={semanticTagStyle(state.color)}>{state.label}</Tag>
                    </summary>
                    {tools.map((tool, index) => {
                      const callState = toolStatus(tool);
                      return (
                        <div key={tool.id} style={{ marginTop: "var(--c-space-2)", paddingTop: "var(--c-space-2)", borderTop: "1px solid var(--c-border)" }}>
                          <div style={{ display: "flex", justifyContent: "space-between", gap: "var(--c-space-2)" }}>
                            <Text type="secondary">{tools.length > 1 ? `第 ${index + 1} 次调用` : "调用参数"}</Text>
                            {tools.length > 1 ? <Text type="secondary">{callState.label}</Text> : null}
                          </div>
                          <pre style={{ maxHeight: 180, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{formatToolArguments(tool.arguments)}</pre>
                          <ToolResultSummary value={tool.resultSummary} />
                        </div>
                      );
                    })}
                  </details>
                );
              })}
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
