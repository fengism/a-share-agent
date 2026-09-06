import type { KeyboardEvent } from "react";
import { SendOutlined } from "@ant-design/icons";
import { Button, Input } from "antd";
import { useColors, useTokens } from "../../../styles/ui";

interface ChatInputProps {
  value: string;
  isStreaming: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
}

function getSessionPromptSuggestions(): string[] {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();
  if (minutes < 9 * 60 + 30) {
    return ["早盘集合竞价异动板块", "今日主线题材与风向标", "北向资金近期增持标的"];
  }
  if (minutes < 15 * 60) {
    return ["盘中主力净流入前三行业", "当前涨停连板天梯与龙头股", "分析当前市场量能与情绪"];
  }
  return ["今日 A 股收盘复盘与主线总结", "龙虎榜机构与知名游资买入标的", "挖掘高股息低估值潜力股"];
}

export function ChatInput({
  value,
  isStreaming,
  onChange,
  onSend,
  onStop,
}: ChatInputProps) {
  const c = useColors();
  const t = useTokens();
  const suggestions = getSessionPromptSuggestions();

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: t.space[2] }}>
      {!isStreaming && !value && (
        <div style={{ display: "flex", gap: t.space[1], flexWrap: "wrap", alignItems: "center" }}>
          <span style={{ fontSize: t.font.xs, color: c.textMuted }}>💡 快捷探索：</span>
          {suggestions.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => onChange(prompt)}
              style={{
                fontSize: t.font.xs,
                color: c.textSecondary,
                background: c.nestedBg,
                border: `1px solid ${c.border}`,
                borderRadius: t.radius.pill,
                padding: "2px 8px",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = c.primary;
                e.currentTarget.style.color = c.primary;
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = c.border;
                e.currentTarget.style.color = c.textSecondary;
              }}
            >
              {prompt}
            </button>
          ))}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: t.space[2],
          alignItems: "flex-end",
        }}
      >
        <Input.TextArea
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入问题，如：贵州茅台怎么样、帮我找PE小于20的白酒股..."
          autoSize={{ minRows: 1, maxRows: 4 }}
          disabled={isStreaming}
          style={{
            flex: 1,
            borderRadius: t.radius.lg,
            background: c.hoverBg,
          }}
        />
        {isStreaming ? (
          <Button
            onClick={onStop}
            danger
            style={{ borderRadius: t.radius.lg, minWidth: 80, height: 40 }}
          >
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={onSend}
            disabled={!value.trim()}
            style={{ borderRadius: t.radius.lg, minWidth: 80, height: 40 }}
          >
            发送
          </Button>
        )}
      </div>
    </div>
  );
}
