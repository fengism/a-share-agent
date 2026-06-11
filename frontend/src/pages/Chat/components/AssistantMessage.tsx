import {
  BulbOutlined,
  ExportOutlined,
  FileTextOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { Button, Collapse } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatDisplayMessage } from "../../../types/chat";
import { useColors} from "../../../styles/ui";
import { BlinkingCursor } from "./BlinkingCursor";
import { ToolCallCard } from "./ToolCallCard";

const markdownPlugins = [remarkGfm];

interface AssistantMessageProps {
  message: ChatDisplayMessage;
  onPush?: (messageId: string, content: string) => void;
}

export function AssistantMessage({ message, onPush }: AssistantMessageProps) {
  const c = useColors();
  const hasReasoning = !!message.reasoningContent;
  const hasTools = !!message.toolCalls?.length;
  const hasContent = !!message.content;
  const isStreaming = message.isStreaming;

  return (
    <div style={{ minWidth: 60 }}>
      {hasReasoning && (
        <div style={{ marginBottom: 8 }}>
          <Collapse
            size="small"
            defaultActiveKey={isStreaming ? ["reasoning"] : []}
            items={[
              {
                key: "reasoning",
                label: (
                  <span
                    style={{ fontSize: 12, color: c.textSecondary }}
                  >
                    <BulbOutlined
                      style={{ marginRight: 4, color: "#f59e0b" }}
                    />
                    思考过程
                    {isStreaming && !hasTools && !hasContent && (
                      <LoadingOutlined
                        style={{ marginLeft: 6, fontSize: 11 }}
                        spin
                      />
                    )}
                  </span>
                ),
                children: (
                  <div
                    style={{
                      fontSize: 12,
                      color: c.textSecondary,
                      lineHeight: 1.7,
                      whiteSpace: "pre-wrap",
                    }}
                  >
                    {message.reasoningContent}
                  </div>
                ),
              },
            ]}
            style={{
              background: "rgba(245, 158, 11, 0.06)",
              border: "1px solid rgba(245, 158, 11, 0.2)",
              borderRadius: 8,
            }}
          />
        </div>
      )}

      {hasTools && (
        <div style={{ marginBottom: 8 }}>
          {message.toolCalls?.map((toolCall) => (
            <ToolCallCard key={toolCall.id} toolCall={toolCall} />
          ))}
          {isStreaming && !hasContent && <BlinkingCursor />}
        </div>
      )}

      {hasContent && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 12,
            background: c.elevatedBg,
            border: `1px solid ${c.border}`,
            fontSize: 14,
            lineHeight: 1.7,
            color: c.textPrimary,
            wordBreak: "break-word",
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 6,
              paddingBottom: 6,
              borderBottom: `1px solid ${c.border}`,
            }}
          >
            <div style={{ display: "flex", alignItems: "center" }}>
              <FileTextOutlined
                style={{
                  marginRight: 6,
                  color: c.primary,
                  fontSize: 12,
                }}
              />
              <span
                style={{
                  fontSize: 11,
                  color: c.textSecondary,
                  fontWeight: 600,
                }}
              >
                分析结果
              </span>
            </div>
            {!isStreaming && onPush && (
              <Button
                type="text"
                size="small"
                icon={<ExportOutlined />}
                onClick={() => onPush(message.id, message.content)}
                style={{
                  fontSize: 12,
                  color: c.textSecondary,
                  padding: "0 6px",
                }}
              >
                推送
              </Button>
            )}
          </div>
          <div className="chat-markdown">
            <ReactMarkdown remarkPlugins={markdownPlugins}>
              {message.content.replace(/\n{3,}/g, "\n\n")}
            </ReactMarkdown>
          </div>
          {isStreaming && <BlinkingCursor />}
        </div>
      )}

      {isStreaming && !hasReasoning && !hasTools && !hasContent && (
        <div
          style={{
            padding: "10px 14px",
            borderRadius: 12,
            background: c.elevatedBg,
            border: `1px solid ${c.border}`,
            color: c.textSecondary,
            fontSize: 13,
          }}
        >
          <LoadingOutlined style={{ marginRight: 8 }} />
          正在思考...
        </div>
      )}
    </div>
  );
}
