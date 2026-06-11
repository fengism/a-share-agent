import { RobotOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import { useColors} from "../../../styles/ui";
import { SAMPLE_PROMPTS } from "../constants";

interface EmptyChatStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function EmptyChatState({ onSelectPrompt }: EmptyChatStateProps) {
  const c = useColors();
  return (
    <div
      style={{
        textAlign: "center",
        color: c.textMuted,
        paddingTop: 80,
        fontSize: 14,
      }}
    >
      <RobotOutlined
        style={{ fontSize: 40, marginBottom: 12, display: "block" }}
      />
      输入问题开始对话，例如：
      <div
        style={{
          marginTop: 12,
          display: "flex",
          gap: 8,
          justifyContent: "center",
          flexWrap: "wrap",
        }}
      >
        {SAMPLE_PROMPTS.map((prompt) => (
          <Tag
            key={prompt}
            style={{
              cursor: "pointer",
              borderRadius: 16,
              padding: "4px 12px",
              background: c.elevatedBg,
              border: `1px solid ${c.border}`,
              color: c.textSecondary,
            }}
            onClick={() => onSelectPrompt(prompt)}
          >
            {prompt}
          </Tag>
        ))}
      </div>
    </div>
  );
}
