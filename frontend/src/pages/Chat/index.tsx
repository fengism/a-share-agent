import { useCallback, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RobotOutlined } from "@ant-design/icons";
import { semanticTagStyle, useStyles } from "../../styles/ui";
import { Tag } from "antd";
import { ChatActionDialogs } from "./components/ChatActionDialogs";
import { ChatAgentSelector } from "./components/ChatAgentSelector";
import { ChatCapabilityPresetBar } from "./components/ChatCapabilityPresetBar";
import { ChatClearButton, ChatConversation } from "./components/ChatConversation";
import { useChatStore } from "../../store/chatStore";
import { ChatInput } from "./components/ChatInput";
import { ChatSessionSidebar } from "./components/ChatSessionSidebar";
import { ChatSkillSelector } from "./components/ChatSkillSelector";
import { useChatCapabilitySelection } from "./useChatCapabilitySelection";
import { useChatController } from "./useChatController";
import { useChatResultActionController } from "./useChatResultActionController";
import "./chat.css";

export default function ChatPage() {
  const [searchParams] = useSearchParams();
  const [inputValue, setInputValue] = useState(() => searchParams.get("prompt")?.trim() || "");
  const resultActions = useChatResultActionController();
  const chat = useChatController({ inputValue, setInputValue });
  const syncStatus = useChatStore((state) => state.syncStatus);
  const {
    agentNames,
    chatCapabilities,
    chatCapabilityAvailability,
    config,
    setAgentNames,
    setSkillNames,
    skillNames,
  } = useChatCapabilitySelection();
  const [isCustomOpen, setIsCustomOpen] = useState(false);
  const { pageDescriptionStyle, pageHeaderStyle, pageTitleStyle } = useStyles();
  const syncTag = syncStatus === "synced"
    ? <Tag style={semanticTagStyle("down")}>会话已同步</Tag>
    : syncStatus === "loading"
      ? <Tag style={semanticTagStyle("primary")}>会话同步中</Tag>
      : <Tag style={semanticTagStyle("warning")}>本地缓存模式</Tag>;

  const handleApplyCapabilityPreset = useCallback((
    nextSkillNames: string[],
    nextAgentNames: string[],
  ) => {
    setSkillNames(nextSkillNames);
    setAgentNames(nextAgentNames);
  }, [setAgentNames, setSkillNames]);

  return (
    <>
      <div className="chat-page-layout">
        <ChatSessionSidebar
          onNewSession={chat.handleNewSession}
          onSelectSession={chat.handleSessionClick}
          onDeleteSession={chat.handleDeleteSession}
        />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={pageHeaderStyle}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div>
                <h2 style={pageTitleStyle}>
                  <RobotOutlined style={{ marginRight: 8 }} />
                  AI 选股助手 {syncTag}
                </h2>
                <p style={pageDescriptionStyle}>
                  自由对话，智能选股。输入股票名称、筛选条件或市场问题，AI
                  助手将调用工具获取实时数据并分析。
                </p>
              </div>
              <ChatClearButton onClear={chat.handleClear} />
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
            disabled={chat.isStreaming}
            isCustomOpen={isCustomOpen}
            onToggleCustom={() => setIsCustomOpen((open) => !open)}
          />
          {isCustomOpen ? (
            <div className="chat-custom-config-pane">
              <ChatSkillSelector
                skills={chatCapabilities?.skills ?? []}
                disabledSkillNames={config?.disabled_chat_skills ?? []}
                availability={chatCapabilityAvailability}
                skillNames={skillNames}
                onChange={setSkillNames}
                disabled={chat.isStreaming}
              />
              <ChatAgentSelector
                agents={chatCapabilities?.agents ?? []}
                disabledAgentNames={config?.disabled_chat_agents ?? []}
                availability={chatCapabilityAvailability}
                agentNames={agentNames}
                onChange={setAgentNames}
                disabled={chat.isStreaming}
              />
            </div>
          ) : null}
          <ChatConversation
            onPush={resultActions.handleOpenPush}
            onRegenerate={chat.handleRegenerate}
            onSelectPrompt={setInputValue}
            onResultAction={resultActions.handleResultAction}
          />
          <ChatInput
            value={inputValue}
            isStreaming={chat.isStreaming}
            onChange={setInputValue}
            onSend={chat.handleSend}
            onStop={chat.handleStop}
          />
        </div>
      </div>
      <ChatActionDialogs controller={resultActions} />
    </>
  );
}
