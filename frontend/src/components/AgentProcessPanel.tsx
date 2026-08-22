import { CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, LoadingOutlined, RobotOutlined, StopOutlined, ToolOutlined } from "@ant-design/icons";
import type { ReactElement } from "react";
import { Steps, Tag, Typography } from "antd";
import type { AgentPlan, AgentPlanStepStatus, ToolCallDisplay } from "../types/chat";
import { formatToolArguments } from "../utils/toolCall";
import { semanticTagStyle } from "../styles/ui";
import type { SemanticTagColor } from "../styles/ui";

const { Text } = Typography;

const PLAN_STATUS: Record<AgentPlanStepStatus, "wait" | "process" | "finish" | "error"> = {
  pending: "wait",
  running: "process",
  completed: "finish",
  failed: "error",
  cancelled: "error",
};

function toolStatus(tool: ToolCallDisplay): { color: SemanticTagColor; label: string; icon: ReactElement } {
  if (tool.isExecuting) return { color: "primary", label: "执行中", icon: <LoadingOutlined spin /> };
  if (tool.isError) return { color: "up", label: "失败", icon: <CloseCircleOutlined /> };
  if (tool.isCancelled) return { color: "warning", label: "已停止", icon: <StopOutlined /> };
  return { color: "down", label: "已完成", icon: <CheckCircleOutlined /> };
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
  if (!plan && toolCalls.length === 0 && !status) return null;
  const hasFailure = Boolean(plan?.steps.some((step) => step.status === "failed"))
    || toolCalls.some((tool) => tool.isError);
  const hasCancellation = Boolean(plan?.steps.some((step) => step.status === "cancelled"))
    || toolCalls.some((tool) => tool.isCancelled);
  const badge = hasFailure
    ? { color: "up" as SemanticTagColor, label: "执行失败", icon: <CloseCircleOutlined /> }
    : isRunning
      ? { color: "primary" as SemanticTagColor, label: "执行中", icon: <LoadingOutlined spin /> }
      : hasCancellation
        ? { color: "warning" as SemanticTagColor, label: "已停止", icon: <StopOutlined /> }
      : { color: "down" as SemanticTagColor, label: "已完成", icon: <CheckCircleOutlined /> };

  return (
    <section style={{ marginTop: "var(--c-space-5)", paddingTop: "var(--c-space-4)", borderTop: "1px solid var(--c-border)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "var(--c-space-3)", marginBottom: "var(--c-space-3)" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "var(--c-space-2)" }}>
          <RobotOutlined style={{ color: "var(--c-primary)" }} />
          <Text strong>Agent 执行过程</Text>
        </div>
        <Tag icon={badge.icon} style={semanticTagStyle(badge.color)}>
          {badge.label}
        </Tag>
      </div>

      {status && <div style={{ color: "var(--c-text-secondary)", fontSize: "var(--c-font-md)", marginBottom: "var(--c-space-3)" }}>{status}</div>}

      {plan?.steps.length ? (
        <Steps
          orientation="vertical"
          size="small"
          items={plan.steps.map((step) => ({
            title: step.title,
            content: step.detail || step.description,
            status: PLAN_STATUS[step.status],
            icon: step.status === "pending" ? <ClockCircleOutlined /> : undefined,
          }))}
        />
      ) : null}

      {toolCalls.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--c-space-2)", marginTop: "var(--c-space-1)" }}>
          {toolCalls.map((tool) => {
            const state = toolStatus(tool);
            return (
              <details key={tool.id} style={{ border: "1px solid var(--c-border)", borderRadius: "var(--c-radius-md)", padding: "var(--c-space-2) var(--c-space-3)" }}>
                <summary style={{ display: "flex", alignItems: "center", gap: "var(--c-space-2)", cursor: "pointer" }}>
                  <ToolOutlined />
                  <Text code style={{ flex: 1 }}>{tool.name}</Text>
                  <Tag icon={state.icon} style={semanticTagStyle(state.color)}>{state.label}</Tag>
                </summary>
                <div style={{ marginTop: "var(--c-space-2)" }}>
                  <Text type="secondary">调用参数</Text>
                  <pre style={{ maxHeight: 180, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{formatToolArguments(tool.arguments)}</pre>
                </div>
              </details>
            );
          })}
        </div>
      )}
    </section>
  );
}
