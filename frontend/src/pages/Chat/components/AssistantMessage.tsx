import React, { useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  ExportOutlined,
  RedoOutlined,
} from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatDisplayMessage } from "../../../types/chat";
import { AssistantProcess } from "./AssistantProcess";
import { BlinkingCursor } from "./BlinkingCursor";

const markdownPlugins = [remarkGfm];

interface AssistantMessageProps {
  message: ChatDisplayMessage;
  onPush?: (messageId: string, content: string) => void;
  onRegenerate?: () => void;
}

export const AssistantMessage = React.memo(function AssistantMessage({
  message,
  onPush,
  onRegenerate,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);
  const hasContent = !!message.content;
  const isStreaming = message.isStreaming;
  const normalizedContent = message.content.replace(/\n{3,}/g, "\n\n");

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="chat-assistant-message">
      <AssistantProcess message={message} />

      {hasContent && (
        <div className="chat-assistant-answer">
          {isStreaming ? (
            <div style={{ whiteSpace: "pre-wrap" }}>{normalizedContent}</div>
          ) : (
            <div className="chat-markdown">
              <ReactMarkdown remarkPlugins={markdownPlugins}>{normalizedContent}</ReactMarkdown>
            </div>
          )}
          {isStreaming && <BlinkingCursor />}
        </div>
      )}

      {!isStreaming && (hasContent || onRegenerate) && (
        <div className="chat-message-actions">
          {hasContent && (
            <Tooltip title={copied ? "已复制" : "复制回答"}>
              <Button
                type="text"
                size="small"
                icon={copied ? <CheckOutlined /> : <CopyOutlined />}
                onClick={() => void handleCopy()}
                aria-label="复制回答"
              />
            </Tooltip>
          )}
          {hasContent && onPush && (
            <Tooltip title="推送回答">
              <Button
                type="text"
                size="small"
                icon={<ExportOutlined />}
                onClick={() => onPush(message.id, message.content)}
                aria-label="推送回答"
              />
            </Tooltip>
          )}
          {onRegenerate && (
            <Tooltip title="重新生成回答">
              <Button
                type="text"
                size="small"
                icon={<RedoOutlined />}
                onClick={onRegenerate}
                aria-label="重新生成回答"
              />
            </Tooltip>
          )}
        </div>
      )}
    </div>
  );
});
