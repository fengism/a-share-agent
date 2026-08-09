import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { RobotOutlined } from "@ant-design/icons";
import { streamChat } from "../../api/chat";
import {
  useChatCapabilities,
  useChatCapabilityAvailability,
  useConfig,
  usePush,
} from "../../api/queries";
import PushModal from "../../components/PushModal";
import { useChatStore } from "../../store/chatStore";
import type { ChatStreamDelta } from "../../types/chat";
import type { PushRequest } from "../../types/stock";
import {
  useColors,
  useStyles,
} from "../../styles/ui";
import { ChatInput } from "./components/ChatInput";
import { ChatAgentSelector } from "./components/ChatAgentSelector";
import { ChatCapabilityPresetBar } from "./components/ChatCapabilityPresetBar";
import { ChatSkillSelector } from "./components/ChatSkillSelector";
import { ChatClearButton, ChatConversation } from "./components/ChatConversation";
import { ChatSessionSidebar } from "./components/ChatSessionSidebar";
import { createStreamDeltaBatcher, type StreamDeltaBatcher } from "./streamDeltaBatcher";
import "./chat.css";

export default function ChatPage() {
  const [inputValue, setInputValue] = useState("");
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [pushContent, setPushContent] = useState("");
  // session-row hover (bg + delete-button reveal) is handled purely in CSS
  const activeAssistantIdRef = useRef<string | null>(null);
  const activeControllerRef = useRef<AbortController | null>(null);
  const streamBatcherRef = useRef<StreamDeltaBatcher | null>(null);
  if (!streamBatcherRef.current) {
    streamBatcherRef.current = createStreamDeltaBatcher(({ text, reasoning }) => {
      const assistantId = activeAssistantIdRef.current;
      if (!assistantId) return;
      const store = useChatStore.getState();
      if (reasoning) store.appendToReasoning(assistantId, reasoning);
      if (text) store.appendToAssistant(assistantId, text);
    });
  }
  const streamBatcher = streamBatcherRef.current;
  const pushMutation = usePush();
  const { data: config } = useConfig();
  const { data: chatCapabilities } = useChatCapabilities();
  const { data: chatCapabilityAvailability } = useChatCapabilityAvailability();

  const c = useColors();
  const { pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();

  const isStreaming = useChatStore((state) => state.isStreaming);
  const agentNames = useChatStore((state) => state.agentNames);
  const skillNames = useChatStore((state) => state.skillNames);
  const abortController = useChatStore((state) => state.abortController);
  const setStreaming = useChatStore((state) => state.setStreaming);
  const setAbortController = useChatStore((state) => state.setAbortController);
  const clearChat = useChatStore((state) => state.clearChat);
  const finalizeMessage = useChatStore((state) => state.finalizeMessage);
  const createSession = useChatStore((state) => state.createSession);
  const setActiveSession = useChatStore((state) => state.setActiveSession);
  const deleteSession = useChatStore((state) => state.deleteSession);
  const setAgentNames = useChatStore((state) => state.setAgentNames);
  const setSkillNames = useChatStore((state) => state.setSkillNames);

  useEffect(() => {
    if (agentNames === null || !chatCapabilities || !config) return;
    const enabledNames = new Set(
      chatCapabilities.agents
        .filter((agent) => {
          const status = chatCapabilityAvailability?.agents[agent.name]?.status;
          return (
            !config.disabled_chat_agents.includes(agent.name)
            && status !== "unavailable"
            && status !== "disabled"
          );
        })
        .map((agent) => agent.name),
    );
    const filteredNames = agentNames.filter((name) => enabledNames.has(name));
    if (
      filteredNames.length !== agentNames.length
      || filteredNames.some((name, index) => name !== agentNames[index])
    ) {
      setAgentNames(filteredNames);
    }
  }, [
    agentNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setAgentNames,
  ]);

  useEffect(() => {
    if (skillNames === null || !chatCapabilities || !config) return;
    const enabledNames = new Set(
      chatCapabilities.skills
        .filter((skill) => {
          const status = chatCapabilityAvailability?.skills[skill.name]?.status;
          return (
            !config.disabled_chat_skills.includes(skill.name)
            && status !== "unavailable"
            && status !== "disabled"
          );
        })
        .map((skill) => skill.name),
    );
    const filteredNames = skillNames.filter((name) => enabledNames.has(name));
    if (
      filteredNames.length !== skillNames.length
      || filteredNames.some((name, index) => name !== skillNames[index])
    ) {
      setSkillNames(filteredNames);
    }
  }, [
    skillNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setSkillNames,
  ]);

  const clearActiveRequest = useCallback(() => {
    streamBatcher.flush();
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    setAbortController(null);
    setStreaming(false);
  }, [setAbortController, setStreaming, streamBatcher]);

  useEffect(
    () => () => {
      streamBatcher.flush();
      activeControllerRef.current?.abort();
      activeAssistantIdRef.current = null;
      setAbortController(null);
      setStreaming(false);
    },
    [setAbortController, setStreaming, streamBatcher],
 );

  const handleNewSession = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    if (activeAssistantIdRef.current) {
      finalizeMessage(activeAssistantIdRef.current);
    }
    clearActiveRequest();
    createSession();
  }, [abortController, clearActiveRequest, createSession, finalizeMessage, streamBatcher]);

  const handleSessionClick = useCallback((sessionId: string) => {
    if (!isStreaming) {
      setActiveSession(sessionId);
    }
  }, [isStreaming, setActiveSession]);

  const handleDeleteSession = useCallback((sessionId: string) => {
    if (isStreaming) return;
    deleteSession(sessionId);
  }, [deleteSession, isStreaming]);

  const startAssistantStream = useCallback((input: string, history: ReturnType<typeof useChatStore.getState>["history"]) => {
    const store = useChatStore.getState();
    streamBatcher.flush();
    const assistantId = `msg-${Date.now()}`;
    activeAssistantIdRef.current = assistantId;
    store.addAssistantMessage(assistantId);

    const controller = streamChat(input, history, {
      onDelta: (delta: ChatStreamDelta) => {
        const s = useChatStore.getState();
        switch (delta.type) {
          case "status":
            streamBatcher.flush();
            s.setAssistantStatus(assistantId, delta.content || "");
            break;
          case "plan":
            streamBatcher.flush();
            if (delta.plan) {
              s.setAssistantPlan(assistantId, delta.plan);
            }
            break;
          case "plan_step":
            streamBatcher.flush();
            if (delta.plan_step) {
              s.updateAssistantPlanStep(assistantId, delta.plan_step);
            }
            break;
          case "reasoning":
            streamBatcher.enqueueReasoning(delta.content || "");
            break;
          case "text":
            streamBatcher.enqueueText(delta.content || "");
            break;
          case "tool_call":
            streamBatcher.flush();
            if (delta.tool_call) {
              s.addToolCall(assistantId, delta.tool_call);
            }
            break;
          case "tool_result":
            streamBatcher.flush();
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
            streamBatcher.flush();
            s.appendToAssistant(assistantId, `\n\n[错误] ${delta.error}`);
            break;
          case "done":
            streamBatcher.flush();
            if (delta.reasoning_content) {
              s.setReasoningContent(assistantId, delta.reasoning_content);
            }
            s.finalizeMessage(assistantId);
            break;
        }
      },
      onError: (err) => {
        streamBatcher.flush();
        const s = useChatStore.getState();
        s.appendToAssistant(assistantId, `\n\n[连接错误] ${err.message}`);
        s.finalizeMessage(assistantId);
        clearActiveRequest();
      },
      onDone: () => {
        useChatStore.getState().finalizeMessage(assistantId);
        clearActiveRequest();
      },
    }, {
      agentNames: store.agentNames === null ? undefined : store.agentNames,
      skillNames: store.skillNames === null ? undefined : store.skillNames,
    });

    activeControllerRef.current = controller;
    store.setAbortController(controller);
    store.setStreaming(true);
  }, [
    clearActiveRequest,
    streamBatcher,
  ]);

  const handleSend = useCallback(() => {
    const input = inputValue.trim();
    if (!input || isStreaming) return;

    const store = useChatStore.getState();
    const history = store.history;
    setInputValue("");
    store.addUserMessage(input);
    store.syncSessionTitle();
    startAssistantStream(input, history);
  }, [inputValue, isStreaming, startAssistantStream]);

  const handleRegenerate = useCallback(() => {
    if (isStreaming) return;
    streamBatcher.flush();
    const request = useChatStore.getState().regenerateLastAssistant();
    if (!request) return;
    startAssistantStream(request.message, request.history);
  }, [isStreaming, startAssistantStream, streamBatcher]);

  const handleClear = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    activeControllerRef.current = null;
    activeAssistantIdRef.current = null;
    clearChat();
  }, [abortController, clearChat, streamBatcher]);

  const handleApplyCapabilityPreset = useCallback((
    nextSkillNames: string[],
    nextAgentNames: string[],
  ) => {
    setSkillNames(nextSkillNames);
    setAgentNames(nextAgentNames);
  }, [setAgentNames, setSkillNames]);

  const handleStop = useCallback(() => {
    streamBatcher.flush();
    abortController?.abort();
    if (activeAssistantIdRef.current) {
      finalizeMessage(activeAssistantIdRef.current);
    }
    clearActiveRequest();
  }, [abortController, clearActiveRequest, finalizeMessage, streamBatcher]);

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
          "--theme-text-muted": c.textMuted,
          "--theme-primary": c.primary,
          "--theme-accent": c.accent,
          "--theme-card-bg": c.cardBg,
          "--theme-nested-bg": c.nestedBg,
          "--theme-border": c.border,
          "--theme-text-secondary": c.textSecondary,
          "--theme-elevated-bg": c.elevatedBg,
        } as React.CSSProperties}
      >
        <ChatSessionSidebar
          onNewSession={handleNewSession}
          onSelectSession={handleSessionClick}
          onDeleteSession={handleDeleteSession}
        />
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
              <ChatClearButton onClear={handleClear} />
            </div>
          </div>
          <ChatCapabilityPresetBar
            capabilities={chatCapabilities}
            availability={chatCapabilityAvailability}
            disabledSkillNames={config?.disabled_chat_skills ?? []}
            disabledAgentNames={config?.disabled_chat_agents ?? []}
            skillNames={skillNames}
            agentNames={agentNames}
            onApply={handleApplyCapabilityPreset}
            disabled={isStreaming}
          />
          <ChatSkillSelector
            skills={chatCapabilities?.skills ?? []}
            disabledSkillNames={config?.disabled_chat_skills ?? []}
            availability={chatCapabilityAvailability}
            skillNames={skillNames}
            onChange={setSkillNames}
            disabled={isStreaming}
          />
          <ChatAgentSelector
            agents={chatCapabilities?.agents ?? []}
            disabledAgentNames={config?.disabled_chat_agents ?? []}
            availability={chatCapabilityAvailability}
            agentNames={agentNames}
            onChange={setAgentNames}
            disabled={isStreaming}
          />
          <ChatConversation
            onPush={handleOpenPush}
            onRegenerate={handleRegenerate}
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
