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
        paddingTop: "var(--c-space-8)",
        fontSize: "var(--c-font-base)",
      }}
    >
      <RobotOutlined
        style={{ fontSize: 40, marginBottom: "var(--c-space-3)", display: "block" }}
      />
      输入问题开始对话，例如：
      <div
        style={{
          marginTop: "var(--c-space-3)",
          display: "flex",
          gap: "var(--c-space-2)",
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
              background: c.hoverBg,
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
