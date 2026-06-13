import type { RefObject } from "react";
import type { ChatDisplayMessage } from "../../../types/chat";
import { useColors, useStyles } from "../../../theme/hooks";
import { AssistantMessage } from "./AssistantMessage";
import { EmptyChatState } from "./EmptyChatState";
import { UserMessageBubble } from "./UserMessageBubble";

interface ChatMessageListProps {
  messages: ChatDisplayMessage[];
  messagesEndRef: RefObject<HTMLDivElement>;
  onPush: (messageId: string, content: string) => void;
  onSelectPrompt: (prompt: string) => void;
}

export function ChatMessageList({
  messages,
  messagesEndRef,
  onPush,
  onSelectPrompt,
}: ChatMessageListProps) {
  const c = useColors();
  const { cardStyle } = useStyles();
  return (
    <div
      style={{
        ...cardStyle,
        padding: 0,
        marginBottom: 12,
        height: "calc(100vh - 260px)",
        minHeight: 400,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "16px 20px",
        }}
      >
        {messages.length === 0 && (
          <EmptyChatState onSelectPrompt={onSelectPrompt} />
        )}

        {messages.map((message) => (
          <div
            key={message.id}
            style={{
              display: "flex",
              justifyContent: message.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 12,
            }}
          >
            <div style={{ maxWidth: "80%" }}>
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
                <AssistantMessage message={message} onPush={onPush} />
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>
    </div>
  );
}
