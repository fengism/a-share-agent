import type { KeyboardEvent } from "react";
import { SendOutlined } from "@ant-design/icons";
import { Button, Input } from "antd";
import { useColors} from "../../../styles/ui";

interface ChatInputProps {
  value: string;
  isStreaming: boolean;
  onChange: (value: string) => void;
  onSend: () => void;
  onStop: () => void;
}

export function ChatInput({
  value,
  isStreaming,
  onChange,
  onSend,
  onStop,
}: ChatInputProps) {
  const c = useColors();
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSend();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        gap: 8,
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
          borderRadius: 10,
          background: c.elevatedBg,
        }}
      />
      {isStreaming ? (
        <Button
          onClick={onStop}
          danger
          style={{ borderRadius: 10, minWidth: 80, height: 40 }}
        >
          停止
        </Button>
      ) : (
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={onSend}
          disabled={!value.trim()}
          style={{ borderRadius: 10, minWidth: 80, height: 40 }}
        >
          发送
        </Button>
      )}
    </div>
  );
}
