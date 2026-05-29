import { LoadingOutlined, ToolOutlined } from "@ant-design/icons";
import { Collapse, Tag, Typography } from "antd";
import type { ToolCallDisplay } from "../../../types/chat";
import { darkColors } from "../../../styles/ui";
import { TOOL_LABELS } from "../constants";

const { Text } = Typography;

function formatToolArgs(argsStr: string): string {
  try {
    const args = JSON.parse(argsStr);
    return Object.entries(args)
      .map(([key, value]) => `${key}=${JSON.stringify(value)}`)
      .join(", ");
  } catch {
    return argsStr;
  }
}

function truncateText(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  return `${text.slice(0, maxLen)}...`;
}

export function ToolCallCard({ toolCall }: { toolCall: ToolCallDisplay }) {
  const label = TOOL_LABELS[toolCall.name] || toolCall.name;
  const items = [
    {
      key: "args",
      label: (
        <span style={{ color: darkColors.textSecondary, fontSize: 12 }}>
          <ToolOutlined style={{ marginRight: 4 }} />
          {label}
          {toolCall.isExecuting && (
            <LoadingOutlined style={{ marginLeft: 6, fontSize: 11 }} spin />
          )}
          {toolCall.isError && (
            <Tag color="error" style={{ marginLeft: 6, fontSize: 11 }}>
              失败
            </Tag>
          )}
          {!toolCall.isExecuting && !toolCall.isError && toolCall.result && (
            <Tag color="success" style={{ marginLeft: 6, fontSize: 11 }}>
              完成
            </Tag>
          )}
        </span>
      ),
      children: (
        <div style={{ fontSize: 12, color: darkColors.textSecondary }}>
          <div style={{ marginBottom: 4 }}>
            <Text type="secondary" style={{ fontSize: 11 }}>
              参数:
            </Text>{" "}
            {truncateText(formatToolArgs(toolCall.arguments), 120)}
          </div>
          {toolCall.result && (
            <div>
              <Text type="secondary" style={{ fontSize: 11 }}>
                结果:
              </Text>{" "}
              <span style={{ wordBreak: "break-all" }}>
                {truncateText(toolCall.result, 500)}
              </span>
            </div>
          )}
        </div>
      ),
    },
  ];

  return (
    <Collapse
      items={items}
      size="small"
      style={{
        marginBottom: 6,
        background: darkColors.nestedBg,
        border: `1px solid ${darkColors.border}`,
        borderRadius: 6,
      }}
    />
  );
}
