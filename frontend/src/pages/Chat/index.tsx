import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, message } from "antd";
import { ClearOutlined, RobotOutlined } from "@ant-design/icons";
import { streamChat } from "../../api/chat";
import { usePush } from "../../api/queries";
import PushModal from "../../components/PushModal";
import { useChatStore } from "../../store/chatStore";
import type { ChatStreamDelta } from "../../types/chat";
import type { PushRequest } from "../../types/stock";
import {
  useColors,
  useStyles,
} from "../../styles/ui";
import { ChatInput } from "./components/ChatInput";
import { ChatMessageList } from "./components/ChatMessageList";

export default function ChatPage() {
  const [inputValue, setInputValue] = useState("");
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [pushContent, setPushContent] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const pushMutation = usePush();

  const c = useColors();
  const { pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();

  const {
    messages,
    isStreaming,
    abortController,
    setStreaming,
    setAbortController,
    clearChat,
    finalizeMessage,
  } = useChatStore();

  const clearActiveRequest = useCallback(() => {
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    setAbortController(null);
    setStreaming(false);
  }, [setAbortController, setStreaming]);

  const scrollToBottom = useCallback((smooth = false) => {
    const sentinel = messagesEndRef.current;
    const container = sentinel?.parentElement;
    // 仅当用户已接近底部时才自动滚动，避免上翻查看历史时被强制拉回
    if (container) {
      const distanceFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      if (distanceFromBottom > 120) return;
    }
    sentinel?.scrollIntoView({ behavior: smooth ? "smooth" : "auto" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(
    () => () => {
      activeControllerRef.current?.abort();
      setAbortController(null);
      setStreaming(false);
    },
    [setAbortController, setStreaming],
  );

  const handleSend = useCallback(() => {
    const input = inputValue.trim();
    if (!input || isStreaming) return;

    const store = useChatStore.getState();

    setInputValue("");
    store.addUserMessage(input);

    const assistantId = `msg-${Date.now()}`;
    activeAssistantIdRef.current = assistantId;
    store.addAssistantMessage(assistantId);

    const controller = streamChat(input, store.history, {
      onDelta: (delta: ChatStreamDelta) => {
        const s = useChatStore.getState();
        switch (delta.type) {
          case "reasoning":
            s.appendToReasoning(assistantId, delta.content || "");
            break;
          case "text":
            s.appendToAssistant(assistantId, delta.content || "");
            break;
          case "tool_call":
            if (delta.tool_call) {
              s.addToolCall(assistantId, delta.tool_call);
            }
            break;
          case "tool_result":
            if (delta.tool_result) {
              s.updateToolResult(
                assistantId,
                delta.tool_result.tool_call_id,
                delta.tool_result.content || "",
                delta.tool_result.is_error,
              );
            }
            break;
          case "error":
            s.appendToAssistant(assistantId, `\n\n[错误] ${delta.error}`);
            break;
          case "done":
            if (delta.reasoning_content) {
              s.setReasoningContent(assistantId, delta.reasoning_content);
            }
            s.finalizeMessage(assistantId);
            break;
        }
      },
      onError: (err) => {
        const s = useChatStore.getState();
        s.appendToAssistant(assistantId, `\n\n[连接错误] ${err.message}`);
        s.finalizeMessage(assistantId);
        clearActiveRequest();
      },
      onDone: () => {
        useChatStore.getState().finalizeMessage(assistantId);
        clearActiveRequest();
      },
    });

    activeControllerRef.current = controller;
    store.setAbortController(controller);
    store.setStreaming(true);
  }, [
    inputValue,
    isStreaming,
    clearActiveRequest,
  ]);

  const handleClear = useCallback(() => {
    abortController?.abort();
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    clearChat();
  }, [abortController, clearChat]);

  const handleStop = useCallback(() => {
    abortController?.abort();
    if (activeAssistantIdRef.current) {
      finalizeMessage(activeAssistantIdRef.current);
    }
    clearActiveRequest();
  }, [abortController, clearActiveRequest, finalizeMessage]);

  const handleOpenPush = useCallback((_messageId: string, content: string) => {
    setPushContent(content);
    setPushModalOpen(true);
  }, []);

  const handlePushConfirm = async (req: PushRequest) => {
    const chatReq: PushRequest = {
      ...req,
      type: "chat",
      chat_content: pushContent,
    };
    try {
      const result = await pushMutation.mutateAsync(chatReq);
      if (result.success) {
        message.success(`推送成功${result.url ? `：${result.url}` : ""}`);
      }
      setPushModalOpen(false);
    } catch {
      message.error("推送失败");
    }
  };

  const chatMarkdownCss = useMemo(() => `
        @keyframes blink {
          50% { opacity: 0; }
        }
        .chat-markdown p { margin: 0 0 4px; }
        .chat-markdown p:last-child { margin-bottom: 0; }
        .chat-markdown p:empty { display: none; }
        .chat-markdown ul, .chat-markdown ol { margin: 4px 0; padding-left: 20px; }
        .chat-markdown li { margin-bottom: 2px; }
        .chat-markdown strong { color: ${c.textPrimary}; font-weight: 700; }
        .chat-markdown code {
          background: rgba(59,130,246,0.15);
          color: ${c.primary};
          padding: 1px 5px;
          border-radius: 4px;
          font-size: 13px;
          font-family: monospace;
        }
        .chat-markdown pre {
          background: ${c.nestedBg};
          border: 1px solid ${c.border};
          border-radius: 6px;
          padding: 10px 12px;
          overflow-x: auto;
          margin: 8px 0;
        }
        .chat-markdown pre code {
          background: none;
          padding: 0;
          color: ${c.textSecondary};
        }
        .chat-markdown blockquote {
          border-left: 3px solid ${c.primary};
          margin: 8px 0;
          padding: 4px 12px;
          color: ${c.textSecondary};
        }
        .chat-markdown h1, .chat-markdown h2, .chat-markdown h3 {
          color: ${c.textPrimary};
          margin: 8px 0 4px;
          font-weight: 700;
        }
        .chat-markdown h3 { font-size: 14px; }
        .chat-markdown h2 { font-size: 15px; }
        .chat-markdown h1 { font-size: 16px; }
        .chat-markdown hr {
          border: none;
          border-top: 1px solid ${c.border};
          margin: 10px 0;
        }
        .chat-markdown table {
          border-collapse: collapse;
          width: 100%;
          margin: 6px 0;
          font-size: 13px;
        }
        .chat-markdown th, .chat-markdown td {
          border: 1px solid ${c.border};
          padding: 6px 10px;
          text-align: left;
        }
        .chat-markdown th {
          background: ${c.elevatedBg};
          color: ${c.textSecondary};
          font-weight: 600;
        }
    `, [c.textPrimary, c.primary, c.nestedBg, c.border, c.textSecondary, c.textMuted, c.elevatedBg, c.pageBg]);

  return (
    <div style={pageContainerStyle}>
      <style>{chatMarkdownCss}</style>

      <div style={pageHeaderStyle}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h2 style={pageTitleStyle}>
              <RobotOutlined style={{ marginRight: 8 }} />
              AI 选股助手
            </h2>
            <p style={pageDescriptionStyle}>
              自由对话，智能选股。输入股票名称、筛选条件或市场问题，AI
              助手将调用工具获取实时数据并分析。
            </p>
          </div>
          <Button
            icon={<ClearOutlined />}
            onClick={handleClear}
            disabled={isStreaming || messages.length === 0}
            style={{ borderRadius: 8 }}
          >
            清空对话
          </Button>
        </div>
      </div>

      <ChatMessageList
        messages={messages}
        messagesEndRef={messagesEndRef}
        onPush={handleOpenPush}
        onSelectPrompt={setInputValue}
      />

      <ChatInput
        value={inputValue}
        isStreaming={isStreaming}
        onChange={setInputValue}
        onSend={handleSend}
        onStop={handleStop}
      />

      <PushModal
        open={pushModalOpen}
        type="chat"
        onConfirm={handlePushConfirm}
        onCancel={() => setPushModalOpen(false)}
        loading={pushMutation.isPending}
      />
    </div>
  );
}
