import { memo, useCallback, useEffect, useRef } from "react";
import { Button } from "antd";
import { ClearOutlined } from "@ant-design/icons";
import { useChatStore } from "../../../store/chatStore";
import { ChatMessageList } from "./ChatMessageList";

interface ChatConversationProps {
  onPush: (messageId: string, content: string) => void;
  onRegenerate: () => void;
  onSelectPrompt: (prompt: string) => void;
}

export const ChatConversation = memo(function ChatConversation({
  onPush,
  onRegenerate,
  onSelectPrompt,
}: ChatConversationProps) {
  const messages = useChatStore((state) => state.messages);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    const sentinel = messagesEndRef.current;
    const container = sentinel?.parentElement;
    if (container) {
      const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
      if (distanceFromBottom > 120) return;
    }
    sentinel?.scrollIntoView({ behavior: "auto" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  return (
    <ChatMessageList
      key={activeSessionId || "empty"}
      messages={messages}
      messagesEndRef={messagesEndRef}
      onPush={onPush}
      onRegenerate={onRegenerate}
      onSelectPrompt={onSelectPrompt}
    />
  );
});

export function ChatClearButton({ onClear }: { onClear: () => void }) {
  const hasMessages = useChatStore((state) => state.messages.length > 0);
  const isStreaming = useChatStore((state) => state.isStreaming);

  return (
    <Button
      icon={<ClearOutlined />}
      onClick={onClear}
      disabled={isStreaming || !hasMessages}
      style={{ borderRadius: 8 }}
    >
      清空对话
    </Button>
  );
}
