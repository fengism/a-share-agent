import React, { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { RobotOutlined } from "@ant-design/icons";
import { Button } from "antd";
import type { ChatDisplayMessage } from "../../../types/chat";
import type { ChatResultActionHandler } from "../chatResultActions";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { useColors, useStyles, useTokens } from "../../../theme/hooks";
import {
  getNextVisibleCount,
  getVisibleMessageStart,
  INITIAL_VISIBLE_MESSAGES,
} from "../chatListHelpers";
import { AssistantMessage } from "./AssistantMessage";
import { EmptyChatState } from "./EmptyChatState";
import { UserMessageBubble } from "./UserMessageBubble";

interface ChatMessageListProps {
  messages: ChatDisplayMessage[];
  messagesEndRef: RefObject<HTMLDivElement>;
  onPush: (messageId: string, content: string) => void;
  onRegenerate: () => void;
  onSelectPrompt: (prompt: string) => void;
  onResultAction: ChatResultActionHandler;
  onEditMessage?: (messageId: string, content: string) => void;
  isStreaming?: boolean;
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  messagesEndRef,
  onPush,
  onRegenerate,
  onSelectPrompt,
  onResultAction,
  onEditMessage,
  isStreaming,
}: ChatMessageListProps) {
  const c = useColors();
  const t = useTokens();
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [visibleCount, setVisibleCount] = useState(INITIAL_VISIBLE_MESSAGES);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const previousScrollHeightRef = useRef<number | null>(null);
  const visibleStart = getVisibleMessageStart(messages.length, visibleCount);
  const visibleMessages = messages.slice(visibleStart);
  const lastMessage = messages[messages.length - 1];
  const regeneratableMessageId = lastMessage?.role === "assistant" ? lastMessage.id : null;

  useLayoutEffect(() => {
    const previousScrollHeight = previousScrollHeightRef.current;
    const container = scrollContainerRef.current;
    if (previousScrollHeight === null || !container) return;
    container.scrollTop += container.scrollHeight - previousScrollHeight;
    previousScrollHeightRef.current = null;
  }, [visibleCount]);

  const handleLoadEarlier = () => {
    previousScrollHeightRef.current = scrollContainerRef.current?.scrollHeight ?? null;
    setVisibleCount((current) => getNextVisibleCount(current, messages.length));
  };

  return (
    <div
      style={{
        ...cardStyle,
        padding: 0,
        marginBottom: t.space[3],
        height: isNarrow ? "calc(100dvh - 220px)" : "calc(100vh - 260px)",
        minHeight: isNarrow ? 320 : 400,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div
        ref={scrollContainerRef}
        aria-live="polite"
        style={{
          flex: 1,
          overflowY: "auto",
          padding: isNarrow ? t.space[3] : `${t.space[4]} ${t.space[5]}`,
        }}
      >
        {messages.length === 0 && (
          <EmptyChatState onSelectPrompt={onSelectPrompt} />
        )}

        {visibleStart > 0 && (
          <div style={{ display: "flex", justifyContent: "center", marginBottom: t.space[4] }}>
            <Button size="small" onClick={handleLoadEarlier}>
              加载更早消息（剩余 {visibleStart} 条）
            </Button>
          </div>
        )}

        {visibleMessages.map((message) => (
          <div
            key={message.id}
            style={{
              display: "flex",
              justifyContent: message.role === "user" ? "flex-end" : "flex-start",
              gap: t.space[3],
              marginBottom: isNarrow ? t.space[4] : t.space[5],
              contentVisibility: "auto",
              containIntrinsicSize: "120px",
            }}
          >
            {message.role === "assistant" && (
              <div
                aria-hidden="true"
                style={{
                  display: "flex",
                  width: 28,
                  height: 28,
                  flex: "0 0 28px",
                  alignItems: "center",
                  justifyContent: "center",
                  marginTop: t.space[5],
                  borderRadius: t.radius.md,
                  background: c.primary,
                  color: c.onPrimary,
                  boxShadow: `0 4px 12px color-mix(in srgb, ${c.primary} 28%, transparent)`,
                }}
              >
                <RobotOutlined style={{ fontSize: 15 }} />
              </div>
            )}
            <div
              style={{
                width: message.role === "assistant" ? "min(900px, calc(100% - 38px))" : "auto",
                maxWidth: message.role === "user" ? (isNarrow ? "92%" : "72%") : undefined,
                minWidth: 0,
              }}
            >
              <div
                style={{
                  fontSize: t.font.xs,
                  color: c.textMuted,
                  marginBottom: t.space[1],
                  textAlign: message.role === "user" ? "right" : "left",
                }}
              >
                {message.role === "user" ? "你" : "AI 助手"}
              </div>

              {message.role === "user" && (
                <UserMessageBubble
                  content={message.content}
                  disabled={isStreaming}
                  onEdit={onEditMessage ? (content) => onEditMessage(message.id, content) : undefined}
                />
              )}

              {message.role === "assistant" && (
                <AssistantMessage
                  message={message}
                  onPush={onPush}
                  onRegenerate={message.id === regeneratableMessageId ? onRegenerate : undefined}
                  onResultAction={onResultAction}
                />
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
});
