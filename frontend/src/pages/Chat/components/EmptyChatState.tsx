import { RobotOutlined } from "@ant-design/icons";
import { Tag } from "antd";
import { darkColors } from "../../../styles/ui";
import { SAMPLE_PROMPTS } from "../constants";

interface EmptyChatStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export function EmptyChatState({ onSelectPrompt }: EmptyChatStateProps) {
  return (
    <div
      style={{
        textAlign: "center",
        color: darkColors.textMuted,
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
              background: darkColors.elevatedBg,
              border: `1px solid ${darkColors.border}`,
              color: darkColors.textSecondary,
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
