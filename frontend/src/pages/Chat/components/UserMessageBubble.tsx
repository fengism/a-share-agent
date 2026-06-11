import { useColors} from "../../../styles/ui";

export function UserMessageBubble({ content }: { content: string }) {
  const c = useColors();
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        background: "rgba(59,130,246,0.2)",
        border: "1px solid rgba(59,130,246,0.3)",
        fontSize: 14,
        lineHeight: 1.6,
        color: c.textPrimary,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {content}
    </div>
  );
}
