import React from "react";
import { useColors } from "../../../styles/ui";
import { hexToRgba } from "../../../charts/utils";

export const UserMessageBubble = React.memo(function UserMessageBubble({ content }: { content: string }) {
  const c = useColors();
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 12,
        background: hexToRgba(c.primary, 0.2),
        border: `1px solid ${hexToRgba(c.primary, 0.3)}`,
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
});
