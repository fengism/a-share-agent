import { Button } from "antd";
import { DeleteOutlined, MessageOutlined, PlusOutlined } from "@ant-design/icons";
import { useChatStore } from "../../../store/chatStore";
import { useColors } from "../../../styles/ui";

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

  return (
    <div
      style={{
        width: 220,
        flexShrink: 0,
        position: "sticky",
        top: 0,
        background: colors.nestedBg,
        border: `1px solid ${colors.border}`,
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
        onClick={onNewSession}
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
              className={isActive ? "chat-session active" : "chat-session"}
              style={{
                display: "flex",
                alignItems: "center",
                borderRadius: 8,
                background: isActive ? `${colors.primary}20` : "transparent",
                border: isActive
                  ? `1px solid ${colors.primary}40`
                  : "1px solid transparent",
                transition: "all 0.15s ease",
                color: isActive ? colors.primary : colors.textSecondary,
                fontSize: 13,
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
                  gap: 8,
                  padding: "8px 10px",
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
                    marginRight: 8,
                    padding: 4,
                    border: 0,
                    background: "transparent",
                    fontSize: 12,
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
