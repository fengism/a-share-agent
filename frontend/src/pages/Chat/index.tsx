import { useCallback, useEffect, useRef, useState } from "react";
import { Button, message } from "antd";
import { ClearOutlined, DeleteOutlined, MessageOutlined, PlusOutlined, RobotOutlined } from "@ant-design/icons";
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
  const [hoveredSessionId, setHoveredSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const pushMutation = usePush();

  const c = useColors();
  const { pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();

  const {
    messages,
    isStreaming,
    abortController,
    sessions,
    activeSessionId,
    setStreaming,
    setAbortController,
    clearChat,
    finalizeMessage,
    createSession,
    setActiveSession,
    deleteSession,
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

  const handleNewSession = useCallback(() => {
    abortController?.abort();
    createSession();
  }, [abortController, createSession]);

  const handleSessionClick = useCallback((sessionId: string) => {
    if (!isStreaming) {
      setActiveSession(sessionId);
      setHoveredSessionId(null);
    }
  }, [isStreaming, setActiveSession]);

  const handleDeleteSession = useCallback((e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    deleteSession(sessionId);
  }, [deleteSession]);

  const handleSend = useCallback(() => {
    const input = inputValue.trim();
    if (!input || isStreaming) return;

    const store = useChatStore.getState();

    setInputValue("");
   store.addUserMessage(input);
    // 自动将首条消息设为会话标题
    store.syncSessionTitle();

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

  return (
    <>
      <div
        style={{
          display: "flex",
          gap: 16,
          alignItems: "flex-start",
          maxWidth: 1400,
          margin: "0 auto",
          padding: "0 0 24px",
          "--theme-text-primary": c.textPrimary,
          "--theme-primary": c.primary,
          "--theme-nested-bg": c.nestedBg,
          "--theme-border": c.border,
          "--theme-text-secondary": c.textSecondary,
          "--theme-elevated-bg": c.elevatedBg,
        } as React.CSSProperties}
      >
        {/* ── Session Sidebar ── */}
        <div
          style={{
            width: 220,
            flexShrink: 0,
            position: "sticky",
            top: 0,
            background: c.nestedBg,
            border: `1px solid ${c.border}`,
            borderRadius: 12,
            padding: 12,
            maxHeight: "calc(100vh - 120px)",
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 8,
          }}
        >
          <Button
            type="primary"
            block
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            style={{ borderRadius: 8 }}
          >
            新对话
          </Button>
          <div
            style={{
              flex: 1,
              overflowY: "auto",
              display: "flex",
              flexDirection: "column",
              gap: 2,
            }}
          >
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              return (
                <div
                  key={session.id}
                  onClick={() => handleSessionClick(session.id)}
                  onMouseEnter={() => setHoveredSessionId(session.id)}
                  onMouseLeave={() => setHoveredSessionId(null)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                    padding: "8px 10px",
                    borderRadius: 8,
                    cursor: isStreaming ? "not-allowed" : "pointer",
                    background:
                      hoveredSessionId === session.id && !isActive
                        ? c.elevatedBg
                        : isActive
                          ? `${c.primary}20`
                          : "transparent",
                    border: isActive
                      ? `1px solid ${c.primary}40`
                      : "1px solid transparent",
                    transition: "all 0.15s ease",
                    color: isActive ? c.primary : c.textSecondary,
                    fontSize: 13,
                  }}
                >
                  <MessageOutlined style={{ fontSize: 14, flexShrink: 0 }} />
                  <span
                    style={{
                      flex: 1,
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {session.title}
                  </span>
                  {hoveredSessionId === session.id && sessions.length > 1 && (
                    <DeleteOutlined
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      style={{
                        fontSize: 12,
                        color: c.textMuted,
                        cursor: "pointer",
                        flexShrink: 0,
                      }}
                    />
                  )}
                </div>
              );
            })}
          </div>
        </div>
        {/* ── Main Chat Area ── */}
        <div style={{ flex: 1, minWidth: 0 }}>
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
        </div>
      </div>
      <PushModal
        open={pushModalOpen}
        type="chat"
        onConfirm={handlePushConfirm}
        onCancel={() => setPushModalOpen(false)}
        loading={pushMutation.isPending}
      />
    </>
  );
}
