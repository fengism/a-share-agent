import { RobotOutlined } from "@ant-design/icons";
import { Button } from "antd";
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
          <Button
            key={prompt}
            type="default"
            size="small"
            shape="round"
            style={{
              background: c.elevatedBg,
              border: `1px solid ${c.border}`,
              color: c.textSecondary,
            }}
            onClick={() => onSelectPrompt(prompt)}
          >
            {prompt}
          </Button>
        ))}
      </div>
    </div>
  );
}
