import { BulbOutlined, CheckCircleOutlined, CloseCircleOutlined, ClockCircleOutlined, DownOutlined, LoadingOutlined, RobotOutlined, StopOutlined, ToolOutlined, WarningOutlined } from "@ant-design/icons";
import type { ReactElement } from "react";
import { useEffect, useMemo, useState } from "react";
import { Steps, Tag, Typography } from "antd";
import type { AgentPlan, AgentPlanStepStatus, ToolCallDisplay } from "../types/chat";
import type { AgentProcessRound, AgentProcessTermination } from "../features/agent-process/agentProcess";
import { toolDisplayName } from "../features/agent-process/toolPresentation";
import ToolResultSummary from "../features/agent-process/ToolResultSummary";
import { formatToolArguments } from "../utils/toolCall";
import { semanticTagStyle } from "../styles/ui";
import type { SemanticTagColor } from "../styles/ui";
import "./agent-process-panel.css";

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
  const cancelled = tools.filter((tool) => tool.isCancelled).length;
  if (cancelled > 0) {
    return {
      color: "warning" as SemanticTagColor,
      label: tools.length > 1 ? `${cancelled}/${tools.length} 已停止` : "已停止",
      icon: <StopOutlined />,
    };
  }
  return {
    color: "down" as SemanticTagColor,
    label: tools.length > 1 ? `${tools.length} 次完成` : "已完成",
    icon: <CheckCircleOutlined />,
  };
}

function ToolCallGroups({ toolCalls }: { toolCalls: ToolCallDisplay[] }) {
  const toolGroups = useMemo(() => Array.from(
    toolCalls.reduce((groups, tool) => {
      const existing = groups.get(tool.name) ?? [];
      existing.push(tool);
      groups.set(tool.name, existing);
      return groups;
    }, new Map<string, ToolCallDisplay[]>()),
  ), [toolCalls]);

  if (toolGroups.length === 0) return null;

  return (
    <div className="agent-proc-tool-groups">
      {toolGroups.map(([name, tools]) => {
        const state = groupedToolStatus(tools);
        return (
          <details key={name} className="agent-proc-tool-group">
            <summary className="agent-proc-tool-summary">
              <ToolOutlined />
              <span className="agent-proc-tool-names">
                <Text>{toolDisplayName(name)}</Text>
                {toolDisplayName(name) !== name ? <Text code>{name}</Text> : null}
              </span>
              <Tag icon={state.icon} style={semanticTagStyle(state.color)}>{state.label}</Tag>
            </summary>
            {tools.map((tool, index) => {
              const callState = toolStatus(tool);
              return (
                <div key={tool.id} className="agent-proc-tool-call">
                  <div className="agent-proc-tool-call-header">
                    <Text type="secondary">{tools.length > 1 ? `第 ${index + 1} 次调用` : "调用参数"}</Text>
                    {tools.length > 1 ? <Text type="secondary">{callState.label}</Text> : null}
                  </div>
                  <pre className="agent-proc-tool-args">{formatToolArguments(tool.arguments)}</pre>
                  <ToolResultSummary value={tool.resultSummary} />
                </div>
              );
            })}
          </details>
        );
      })}
    </div>
  );
}

function RoundField({ label, children }: { label: string; children: ReactElement | string }) {
  return (
    <div>
      <Text type="secondary" className="agent-proc-sm-label">{label}</Text>
      <div className="agent-proc-field-value">{children}</div>
    </div>
  );
}

function RoundList({ values, emptyText = "暂无" }: { values: string[]; emptyText?: string }) {
  if (values.length === 0) return <Text type="secondary">{emptyText}</Text>;
  return (
    <ul className="agent-proc-round-list">
      {values.map((value, index) => <li key={`${value}-${index}`}>{value}</li>)}
    </ul>
  );
}

function roundStatus(round: AgentProcessRound) {
  if (round.status === "cancelled" || round.status === "detached") {
    return { color: "warning" as SemanticTagColor, label: round.status === "detached" ? "已停止等待" : "已停止", icon: <StopOutlined /> };
  }
  if (round.status === "failed") {
    return { color: "up" as SemanticTagColor, label: "失败", icon: <CloseCircleOutlined /> };
  }
  if (round.status === "running") {
    return { color: "primary" as SemanticTagColor, label: "调研中", icon: <LoadingOutlined spin /> };
  }
  if (round.status === "degraded") {
    return { color: "warning" as SemanticTagColor, label: "证据不足", icon: <WarningOutlined /> };
  }
  return { color: "down" as SemanticTagColor, label: "已完成", icon: <CheckCircleOutlined /> };
}

function ResearchRounds({ rounds }: { rounds: AgentProcessRound[] }) {
  if (rounds.length === 0) return null;

  return (
    <div aria-label="调研轮次" className="agent-proc-rounds-container">
      <div className="agent-proc-rounds-header">
        <BulbOutlined className="agent-proc-accent-icon" />
        <Text strong>调研轮次</Text>
        <Text type="secondary">结构化推理摘要</Text>
      </div>
      <div className="agent-proc-rounds-list">
        {rounds.map((round) => {
          const state = roundStatus(round);
          return (
            <section
              key={`${round.phase ?? "research"}:${round.roundIndex}`}
              aria-label={`${round.phase === "verification_repair" ? "补证 · " : ""}第 ${round.roundIndex} 轮调研`}
              className={`agent-proc-round-card ${round.status === "degraded" ? "agent-proc-round-card--degraded" : "agent-proc-round-card--primary"}`}
            >
              <div className="agent-proc-round-header">
                <div className="agent-proc-round-title-group">
                  <Text strong>{round.phase === "verification_repair" ? "定向补证 · " : round.phase === "research" ? "主调研 · " : ""}第 {round.roundIndex} 轮</Text>
                  <Text type="secondary">计划最多 {round.roundTotal} 轮</Text>
                </div>
                <Tag icon={state.icon} style={semanticTagStyle(state.color)}>{state.label}</Tag>
              </div>

              <div className="agent-proc-round-body">
                <RoundField label="研究目标">{round.objective || "待确定"}</RoundField>
                <RoundField label="当前证据缺口">
                  <RoundList values={round.evidenceGaps} emptyText="无" />
                </RoundField>
                <RoundField label="工具选择依据">{round.toolSelectionReason || "待确定"}</RoundField>
                <RoundField label="工具名称">
                  {round.toolNames.length > 0 ? (
                    <div className="agent-proc-tool-tags">
                      {round.toolNames.map((name) => <Text code key={name}>{name}</Text>)}
                    </div>
                  ) : <Text type="secondary">暂无</Text>}
                </RoundField>
                {round.statusText ? <RoundField label="执行进度">{round.statusText}</RoundField> : null}
                <RoundField label="关键判断依据">
                  <RoundList values={round.judgmentBasis} emptyText={round.status === "running" ? "调研中" : "暂无"} />
                </RoundField>
                <RoundField label="新增证据">
                  <RoundList values={round.evidenceAdded} emptyText={round.status === "running" ? "调研中" : "暂无"} />
                </RoundField>
                <RoundField label="本轮结论">{round.conclusion || (round.status === "running" ? "调研中" : "暂无")}</RoundField>
                <RoundField label="下一轮计划">{round.nextStep || (round.status === "running" ? "待本轮完成后生成" : "暂无")}</RoundField>
                {round.toolCalls.length > 0 ? (
                  <div>
                    <Text type="secondary" className="agent-proc-sm-label">工具调用</Text>
                    <ToolCallGroups toolCalls={round.toolCalls} />
                  </div>
                ) : null}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}

export default function AgentProcessPanel({
  plan,
  status,
  toolCalls,
  rounds = [],
  isRunning,
  termination,
}: {
  plan?: AgentPlan;
  status: string;
  toolCalls: ToolCallDisplay[];
  rounds?: AgentProcessRound[];
  isRunning: boolean;
  termination?: AgentProcessTermination;
}) {
  const steps = plan?.steps ?? [];
  // A failed tool call is a local evidence gap, not a failed workflow. The
  // report may still complete from other tools, so only terminal/plan/round
  // failures should turn the whole Agent process red.
  const hasFailure = termination === "failed"
    || rounds.some((round) => round.status === "failed")
    || steps.some((step) => step.status === "failed");
  const hasFailedTool = toolCalls.some((tool) => tool.isError);
  const hasCancellation = rounds.some((round) => round.status === "cancelled" || round.status === "detached")
    || steps.some((step) => step.status === "cancelled")
    || toolCalls.some((tool) => tool.isCancelled);
  const hasDegradation = steps.some((step) => step.status === "degraded")
    || rounds.some((round) => round.status === "degraded");
  const hasSkippedTool = toolCalls.some((tool) => tool.isSkipped);
  const degradedSteps = steps.filter((step) => step.status === "degraded");
  const regularSteps = steps.filter((step) => step.status !== "degraded");
  const settledSteps = steps.filter((step) => (
    step.status !== "pending" && step.status !== "running"
  )).length;
  const [expanded, setExpanded] = useState(isRunning);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);

  useEffect(() => {
    setExpanded(isRunning);
  }, [isRunning]);

  useEffect(() => {
    if (!isRunning) {
      setElapsedSeconds(0);
      return;
    }
    const timer = setInterval(() => {
      setElapsedSeconds((prev) => prev + 1);
    }, 1000);
    return () => clearInterval(timer);
  }, [isRunning]);

  if (!plan && toolCalls.length === 0 && rounds.length === 0 && !status) return null;

  const badge = termination === "cancelled" || termination === "detached"
    ? { color: "warning" as SemanticTagColor, label: termination === "detached" ? "已停止等待" : "已停止", icon: <StopOutlined /> }
    : hasFailure
      ? { color: "up" as SemanticTagColor, label: "执行失败", icon: <CloseCircleOutlined /> }
      : isRunning
        ? { color: "primary" as SemanticTagColor, label: "执行中", icon: <LoadingOutlined spin /> }
        : hasCancellation
          ? { color: "warning" as SemanticTagColor, label: "已停止", icon: <StopOutlined /> }
          : hasFailedTool
            ? { color: "warning" as SemanticTagColor, label: "已完成，部分工具失败", icon: <WarningOutlined /> }
            : hasDegradation || hasSkippedTool
              ? { color: "warning" as SemanticTagColor, label: "数据缺口", icon: <WarningOutlined /> }
              : { color: "down" as SemanticTagColor, label: "已完成", icon: <CheckCircleOutlined /> };
  const detail = [
    steps.length > 0 ? `${settledSteps}/${steps.length} 个步骤` : "",
    rounds.length > 0 ? `${rounds.length} 轮调研` : "",
    toolCalls.length > 0 ? `${toolCalls.length} 次工具调用` : "",
  ].filter(Boolean).join(" · ");

  return (
    <section className="agent-process-panel pdf-hide agent-proc-section">
      <button
        type="button"
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="agent-proc-toggle-btn"
      >
        <div className="agent-proc-toggle-left">
          <RobotOutlined className="agent-proc-robot-icon" />
          <div>
            <Text strong>Agent 思考与执行</Text>
            {detail ? <div className="agent-proc-toggle-detail">{detail}</div> : null}
          </div>
        </div>
        <div className="agent-proc-toggle-right">
          <Tag icon={badge.icon} style={semanticTagStyle(badge.color)}>
            {badge.label}
          </Tag>
          <DownOutlined className={`agent-proc-down-icon ${expanded ? "agent-proc-down-icon--expanded" : ""}`} />
        </div>
      </button>

      {expanded ? (
        <div className="agent-proc-content">
          {status && (
            <div
              className={`agent-proc-status-bar ${isRunning ? "agent-proc-status-bar--running" : ""}`}
            >
              {isRunning ? <LoadingOutlined spin className="agent-proc-loading-icon" /> : null}
              <span className="agent-proc-status-text">{status}</span>
              {isRunning && elapsedSeconds > 0 ? (
                <span className="agent-proc-elapsed-time">
                  已耗时 {elapsedSeconds}s
                </span>
              ) : null}
            </div>
          )}

          {plan?.summary ? (
            <div className="agent-proc-plan-summary-row">
              <BulbOutlined className="agent-proc-bulb-icon" />
              <div>
                <Text strong>思路摘要</Text>
                <div className="agent-proc-plan-text">{plan.summary}</div>
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
            <div aria-label="Agent 数据缺口" className="agent-proc-degraded-box">
              <div className="agent-proc-degraded-header">
                <WarningOutlined />
                数据缺口
              </div>
              {degradedSteps.map((step) => (
                <div key={step.id} className="agent-proc-degraded-item">
                  <strong>{step.title}</strong>
                  {step.detail || step.description ? ` · ${step.detail || step.description}` : ""}
                </div>
              ))}
            </div>
          ) : null}

          <ResearchRounds rounds={rounds} />
          {rounds.length === 0 ? <ToolCallGroups toolCalls={toolCalls} /> : null}
        </div>
      ) : null}
    </section>
  );
}
