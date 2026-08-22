import React from "react";
import { useColors, useTokens } from "../../../styles/ui";
import { hexToRgba } from "../../../charts/utils";

export const UserMessageBubble = React.memo(function UserMessageBubble({ content }: { content: string }) {
  const c = useColors();
  const t = useTokens();
  return (
    <div
      style={{
        padding: `${t.space[3]} ${t.space[4]}`,
        borderRadius: t.radius.lg,
        background: hexToRgba(c.primary, 0.2),
        border: `1px solid ${hexToRgba(c.primary, 0.3)}`,
        fontSize: t.font.base,
        lineHeight: t.leading.relaxed,
        color: c.textPrimary,
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {content}
    </div>
  );
});
