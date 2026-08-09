import { useState } from "react";
import {
  CheckCircleFilled,
  CloseCircleFilled,
  DownOutlined,
  LoadingOutlined,
  StopOutlined,
  ToolOutlined,
} from "@ant-design/icons";
import type { ToolCallDisplay } from "../../../types/chat";
import { TOOL_LABELS } from "../constants";

function formatJsonText(value: string): string {
  try {
    return JSON.stringify(JSON.parse(value), null, 2);
  } catch {
    return value;
  }
}

export function ToolCallCard({ toolCall }: { toolCall: ToolCallDisplay }) {
  const [expanded, setExpanded] = useState(false);
  const label = TOOL_LABELS[toolCall.name] || toolCall.name;
  const status = toolCall.isExecuting
    ? "执行中"
    : toolCall.isError
      ? "失败"
      : toolCall.isCancelled
        ? "已停止"
        : "已完成";
  const statusClass = toolCall.isExecuting
    ? "is-running"
    : toolCall.isError
      ? "is-error"
      : toolCall.isCancelled
        ? "is-cancelled"
        : "is-success";
  const StatusIcon = toolCall.isExecuting
    ? LoadingOutlined
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
            <strong>{label}</strong>
            <code>{toolCall.name}</code>
          </span>
          <span className={`chat-tool-status ${statusClass}`}>
            <StatusIcon spin={Boolean(toolCall.isExecuting)} />
            {status}
          </span>
          <DownOutlined className={`chat-tool-chevron${expanded ? " is-expanded" : ""}`} />
        </button>

        {expanded && (
          <div className="chat-tool-details">
            <div className="chat-tool-detail-label">输入参数</div>
            <pre>{formatJsonText(toolCall.arguments || "{}")}</pre>
            {toolCall.result !== undefined && (
              <>
                <div className="chat-tool-detail-label">执行结果</div>
                <pre className={toolCall.isError ? "is-error" : ""}>
                  {formatJsonText(toolCall.result || "（无返回内容）")}
                </pre>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
