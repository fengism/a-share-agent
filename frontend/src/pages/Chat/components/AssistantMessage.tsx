import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  CheckOutlined,
  CopyOutlined,
  DownloadOutlined,
  ExportOutlined,
  RedoOutlined,
} from "@ant-design/icons";
import { Button, Tooltip } from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ChatDisplayMessage } from "../../../types/chat";
import {
  extractChatResultContext,
  type ChatResultActionHandler,
} from "../chatResultActions";
import { AssistantProcess } from "./AssistantProcess";
import { BlinkingCursor } from "./BlinkingCursor";
import { marketDateStamp } from "../../../utils/marketTime";
import { ChatResultActions } from "./ChatResultActions";

const markdownPlugins = [remarkGfm];

interface AssistantMessageProps {
  message: ChatDisplayMessage;
  onPush?: (messageId: string, content: string) => void;
  onRegenerate?: () => void;
  onResultAction?: ChatResultActionHandler;
}

export const AssistantMessage = React.memo(function AssistantMessage({
  message,
  onPush,
  onRegenerate,
  onResultAction,
}: AssistantMessageProps) {
  const [copied, setCopied] = useState(false);
  const copyTimerRef = useRef<number | null>(null);
  const hasContent = !!message.content;
  const isStreaming = message.isStreaming;
  const normalizedContent = message.content.replace(/\n{3,}/g, "\n\n");
  const resultContext = useMemo(() => extractChatResultContext(message), [message]);

  useEffect(() => {
    return () => {
      if (copyTimerRef.current !== null) window.clearTimeout(copyTimerRef.current);
    };
  }, []);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      if (copyTimerRef.current !== null) window.clearTimeout(copyTimerRef.current);
      copyTimerRef.current = window.setTimeout(() => {
        copyTimerRef.current = null;
        setCopied(false);
      }, 1600);
    } catch {
      setCopied(false);
    }
  };

  const handleDownloadMarkdown = () => {
    const blob = new Blob([message.content], { type: "text/markdown;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `AI投研回答_${message.id.slice(0, 8)}_${marketDateStamp()}.md`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };

  return (
    <div className="chat-assistant-message">
      <AssistantProcess message={message} />

      {hasContent && (
        <div className="chat-assistant-answer">
          <div className="chat-markdown">
            <ReactMarkdown remarkPlugins={markdownPlugins}>{normalizedContent}</ReactMarkdown>
          </div>
          {isStreaming && <BlinkingCursor />}
        </div>
      )}

      {!isStreaming && onResultAction ? (
        <ChatResultActions context={resultContext} onAction={onResultAction} />
      ) : null}

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
          {hasContent && (
            <Tooltip title="下载 Markdown">
              <Button
                type="text"
                size="small"
                icon={<DownloadOutlined />}
                onClick={handleDownloadMarkdown}
                aria-label="下载 Markdown"
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
