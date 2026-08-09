import React, { useLayoutEffect, useRef, useState, type RefObject } from "react";
import { RobotOutlined } from "@ant-design/icons";
import { Button } from "antd";
import type { ChatDisplayMessage } from "../../../types/chat";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../../theme/hooks";
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
}

export const ChatMessageList = React.memo(function ChatMessageList({
  messages,
  messagesEndRef,
  onPush,
  onRegenerate,
  onSelectPrompt,
}: ChatMessageListProps) {
  const c = useColors();
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
        marginBottom: 12,
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
          padding: isNarrow ? "12px" : "16px 20px",
        }}
      >
        {messages.length === 0 && (
          <EmptyChatState onSelectPrompt={onSelectPrompt} />
        )}

        {visibleStart > 0 && (
          <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
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
              gap: 10,
              marginBottom: isNarrow ? 16 : 20,
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
                  marginTop: 18,
                  borderRadius: 9,
                  background: c.primary,
                  color: "#fff",
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
                  fontSize: 11,
                  color: c.textMuted,
                  marginBottom: 4,
                  textAlign: message.role === "user" ? "right" : "left",
                }}
              >
                {message.role === "user" ? "你" : "AI 助手"}
              </div>

              {message.role === "user" && (
                <UserMessageBubble content={message.content} />
              )}

              {message.role === "assistant" && (
                <AssistantMessage
                  message={message}
                  onPush={onPush}
                  onRegenerate={message.id === regeneratableMessageId ? onRegenerate : undefined}
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
