import { Button } from "antd";
import { DeleteOutlined, MessageOutlined, PlusOutlined } from "@ant-design/icons";
import { useChatStore } from "../../../store/chatStore";
import { useColors, useTokens } from "../../../styles/ui";

interface ChatSessionSidebarProps {
  onNewSession: () => void;
  onSelectSession: (sessionId: string) => void;
  onDeleteSession: (sessionId: string) => void;
}

export function ChatSessionSidebar({
  onNewSession,
  onSelectSession,
  onDeleteSession,
}: ChatSessionSidebarProps) {
  const sessions = useChatStore((state) => state.sessions);
  const activeSessionId = useChatStore((state) => state.activeSessionId);
  const isStreaming = useChatStore((state) => state.isStreaming);
  const colors = useColors();
  const t = useTokens();

  return (
    <div
      className="chat-session-sidebar"
      style={{
        width: 220,
        flexShrink: 0,
        position: "sticky",
        top: 0,
        background: colors.nestedBg,
        border: `1px solid ${colors.border}`,
        borderRadius: t.radius.lg,
        padding: t.space[3],
        maxHeight: "calc(100vh - 120px)",
        overflowY: "auto",
        display: "flex",
        flexDirection: "column",
        gap: t.space[2],
      }}
    >
      <Button
        type="primary"
        block
        icon={<PlusOutlined />}
        onClick={onNewSession}
        style={{ borderRadius: t.radius.md }}
      >
        新对话
      </Button>
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          display: "flex",
          flexDirection: "column",
          gap: t.space[1],
        }}
      >
        {sessions.map((session) => {
          const isActive = session.id === activeSessionId;
          return (
            <div
              key={session.id}
              className={isActive ? "chat-session active" : "chat-session"}
              style={{
                display: "flex",
                alignItems: "center",
                borderRadius: t.radius.md,
                background: isActive ? `${colors.primary}20` : "transparent",
                border: isActive
                  ? `1px solid ${colors.primary}40`
                  : "1px solid transparent",
                transition: "all 0.15s ease",
                color: isActive ? colors.primary : colors.textSecondary,
                fontSize: t.font.md,
              }}
            >
              <button
                type="button"
                disabled={isStreaming}
                aria-pressed={isActive}
                onClick={() => onSelectSession(session.id)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: t.space[2],
                  padding: `${t.space[2]} ${t.space[3]}`,
                  minWidth: 0,
                  flex: 1,
                  border: 0,
                  background: "transparent",
                  color: "inherit",
                  cursor: isStreaming ? "not-allowed" : "pointer",
                  textAlign: "left",
                  font: "inherit",
                }}
              >
                <MessageOutlined style={{ fontSize: t.font.base, flexShrink: 0 }} />
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
              </button>
              {sessions.length > 1 && (
                <button
                  type="button"
                  aria-label={`删除会话：${session.title}`}
                  className="chat-del"
                  disabled={isStreaming}
                  onClick={() => onDeleteSession(session.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginRight: t.space[2],
                    padding: t.space[1],
                    border: 0,
                    background: "transparent",
                    fontSize: t.font.sm,
                    color: colors.textMuted,
                    cursor: isStreaming ? "not-allowed" : "pointer",
                    flexShrink: 0,
                  }}
                >
                  <DeleteOutlined />
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
