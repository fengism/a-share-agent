import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
  RobotOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import { Steps, Tag, Typography } from "antd";
import { AGENT_TOOL_LABELS } from "../constants/agentTools";
import type { AgentPlan, AgentPlanStepStatus, ToolCallDisplay } from "../types/chat";

const { Text } = Typography;

const PLAN_STATUS: Record<AgentPlanStepStatus, "wait" | "process" | "finish" | "error"> = {
  pending: "wait",
  running: "process",
  completed: "finish",
  failed: "error",
  cancelled: "error",
};

function toolStatus(tool: ToolCallDisplay) {
  if (tool.isExecuting) return { color: "processing", label: "执行中", icon: <LoadingOutlined spin /> };
  if (tool.isError) return { color: "error", label: "失败", icon: <CloseCircleOutlined /> };
  return { color: "success", label: "已完成", icon: <CheckCircleOutlined /> };
}

function formatPayload(value: string | undefined): string {
  if (!value) return "（无）";
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
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
  const hasFailure = Boolean(plan?.steps.some((step) => step.status === "failed"));
  const badge = hasFailure
    ? { color: "error", label: "执行失败", icon: <CloseCircleOutlined /> }
    : isRunning
      ? { color: "processing", label: "执行中", icon: <LoadingOutlined spin /> }
      : { color: "success", label: "已完成", icon: <CheckCircleOutlined /> };

  return (
    <section style={{ marginTop: 18, paddingTop: 16, borderTop: "1px solid var(--theme-border)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <RobotOutlined style={{ color: "var(--theme-primary)" }} />
          <Text strong>Agent 执行过程</Text>
        </div>
        <Tag icon={badge.icon} color={badge.color}>
          {badge.label}
        </Tag>
      </div>

      {status && <div style={{ color: "var(--theme-text-secondary)", fontSize: 13, marginBottom: 12 }}>{status}</div>}

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
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4 }}>
          {toolCalls.map((tool) => {
            const state = toolStatus(tool);
            return (
              <details key={tool.id} style={{ border: "1px solid var(--theme-border)", borderRadius: 8, padding: "8px 10px" }}>
                <summary style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
                  <ToolOutlined />
                  <span style={{ flex: 1 }}>{AGENT_TOOL_LABELS[tool.name] || tool.name}</span>
                  <Tag icon={state.icon} color={state.color}>{state.label}</Tag>
                </summary>
                <div style={{ marginTop: 10 }}>
                  <Text type="secondary">输入参数</Text>
                  <pre style={{ maxHeight: 180, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{formatPayload(tool.arguments)}</pre>
                  {tool.result !== undefined && (
                    <>
                      <Text type="secondary">执行结果</Text>
                      <pre style={{ maxHeight: 220, overflow: "auto", whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{formatPayload(tool.result)}</pre>
                    </>
                  )}
                </div>
              </details>
            );
          })}
        </div>
      )}
    </section>
  );
}
