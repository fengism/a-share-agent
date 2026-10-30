import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  ClearOutlined,
  FullscreenOutlined,
  PlusOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Button, Drawer, FloatButton, Space, Tooltip } from "antd";
import { useMediaQuery } from "../hooks/useMediaQuery";
import { ChatActionDialogs } from "../pages/Chat/components/ChatActionDialogs";
import { ChatConversation } from "../pages/Chat/components/ChatConversation";
import { ChatInput } from "../pages/Chat/components/ChatInput";
import { useChatController } from "../pages/Chat/useChatController";
import { useChatResultActionController } from "../pages/Chat/useChatResultActionController";
import { useChatStore } from "../store/chatStore";
import { useColors, useTokens } from "../styles/ui";

export default function GlobalChatCopilot() {
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const c = useColors();
  const t = useTokens();

  const isStreaming = useChatStore((state) => state.isStreaming);
  const resultActions = useChatResultActionController();
  const chat = useChatController({ inputValue, setInputValue });

  const handleOpenFullscreen = useCallback(() => {
    setOpen(false);
    navigate("/chat");
  }, [navigate]);

  // 全局快捷键 Cmd+J / Ctrl+J 切换伴随式 Copilot 抽屉
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "j") {
        const activeEl = document.activeElement;
        const isInput =
          activeEl instanceof HTMLInputElement ||
          activeEl instanceof HTMLTextAreaElement ||
          (activeEl as HTMLElement)?.isContentEditable;
        if (!isInput) {
          e.preventDefault();
          setOpen((prev) => !prev);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  // 如果已经在 /chat 对话主页面，不渲染悬浮球和抽屉
  if (location.pathname.startsWith("/chat")) {
    return null;
  }

  return (
    <>
      <FloatButton
        icon={<RobotOutlined style={{ color: isStreaming ? c.primary : undefined }} />}
        type={isStreaming ? "primary" : "default"}
        style={{
          right: 24,
          bottom: 24,
          width: 48,
          height: 48,
          boxShadow: `0 6px 20px color-mix(in srgb, ${c.primary} 35%, transparent)`,
        }}
        tooltip="AI 投研伴随助手 (点击随时边看盘边提问)"
        onClick={() => setOpen(true)}
      />

      <Drawer
        title={
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%", paddingRight: 8 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <RobotOutlined style={{ color: c.primary, fontSize: 18 }} />
              <span style={{ fontWeight: 600 }}>AI 投研伴随助手</span>
            </div>
            <Space size={4}>
              <Tooltip title="新开会话">
                <Button
                  type="text"
                  size="small"
                  icon={<PlusOutlined />}
                  onClick={chat.handleNewSession}
                  disabled={chat.isStreaming}
                />
              </Tooltip>
              <Tooltip title="清空对话">
                <Button
                  type="text"
                  size="small"
                  icon={<ClearOutlined />}
                  onClick={chat.handleClear}
                  disabled={chat.isStreaming}
                />
              </Tooltip>
              <Tooltip title="前往沉浸式投研工作台">
                <Button
                  type="text"
                  size="small"
                  icon={<FullscreenOutlined />}
                  onClick={handleOpenFullscreen}
                />
              </Tooltip>
            </Space>
          </div>
        }
        placement="right"
        width={isNarrow ? "100%" : 460}
        open={open}
        onClose={() => setOpen(false)}
        styles={{
          body: {
            display: "flex",
            flexDirection: "column",
            padding: t.space[3],
            overflow: "hidden",
            height: "100%",
          },
        }}
      >
        <div style={{ flex: 1, minHeight: 0, overflowY: "auto", marginBottom: t.space[3] }}>
          <ChatConversation
            onPush={resultActions.handleOpenPush}
            onRegenerate={chat.handleRegenerate}
            onSelectPrompt={setInputValue}
            onResultAction={resultActions.handleResultAction}
            onEditMessage={chat.handleEditUserMessage}
          />
        </div>

        <div style={{ flexShrink: 0 }}>
          <ChatInput
            value={inputValue}
            isStreaming={chat.isStreaming}
            onChange={setInputValue}
            onSend={chat.handleSend}
            onStop={chat.handleStop}
          />
        </div>

        <ChatActionDialogs controller={resultActions} />
      </Drawer>
    </>
  );
}
