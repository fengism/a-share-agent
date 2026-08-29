import { useState } from "react";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  DownOutlined,
  LoadingOutlined,
  StopOutlined,
  ToolOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import type { ToolCallDisplay } from "../../../types/chat";
import { formatToolArguments } from "../../../utils/toolCall";
import { toolDisplayName } from "../../../features/agent-process/toolPresentation";
import ToolResultSummary from "../../../features/agent-process/ToolResultSummary";

export function ToolCallCard({ toolCall }: { toolCall: ToolCallDisplay }) {
  const [expanded, setExpanded] = useState(false);
  const status = toolCall.isExecuting
    ? "执行中"
    : toolCall.isSkipped
      ? "已跳过"
    : toolCall.isError
      ? "失败"
      : toolCall.isCancelled
        ? "已停止"
        : "已完成";
  const statusClass = toolCall.isExecuting
    ? "is-running"
    : toolCall.isSkipped
      ? "is-skipped"
    : toolCall.isError
      ? "is-error"
      : toolCall.isCancelled
        ? "is-cancelled"
        : "is-success";
  const StatusIcon = toolCall.isExecuting
    ? LoadingOutlined
    : toolCall.isSkipped
      ? WarningOutlined
    : toolCall.isError
      ? CloseCircleFilled
      : toolCall.isCancelled
        ? StopOutlined
        : CheckCircleFilled;

  return (
    <div className={`chat-process-step chat-tool-step ${statusClass}`}>
      <span className="chat-process-step-icon" aria-hidden="true">
        <ToolOutlined />
      </span>
      <div className="chat-process-step-content">
        <button
          type="button"
          className="chat-tool-toggle"
          aria-expanded={expanded}
          onClick={() => setExpanded((current) => !current)}
        >
          <span className="chat-tool-heading">
            <span>{toolDisplayName(toolCall.name)}</span>
            {toolDisplayName(toolCall.name) !== toolCall.name ? <code>{toolCall.name}</code> : null}
          </span>
          <span className={`chat-tool-status ${statusClass}`}>
            <StatusIcon spin={Boolean(toolCall.isExecuting)} />
            {status}
          </span>
          <DownOutlined className={`chat-tool-chevron${expanded ? " is-expanded" : ""}`} />
        </button>

        {expanded && (
          <div className="chat-tool-details">
            <div className="chat-tool-detail-label">调用参数</div>
            <pre>{formatToolArguments(toolCall.arguments)}</pre>
            <ToolResultSummary value={toolCall.resultSummary} />
          </div>
        )}
      </div>
    </div>
  );
}
