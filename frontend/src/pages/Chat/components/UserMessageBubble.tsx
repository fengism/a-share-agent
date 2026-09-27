import React, { useState } from "react";
import { Button, Input } from "antd";
import { CheckOutlined, EditOutlined } from "@ant-design/icons";
import { useColors, useTokens } from "../../../styles/ui";
import { hexToRgba } from "../../../charts/utils";

interface UserMessageBubbleProps {
  content: string;
  onEdit?: (content: string) => void;
  disabled?: boolean;
}

export const UserMessageBubble = React.memo(function UserMessageBubble(
  { content, onEdit, disabled }: UserMessageBubbleProps,
) {
  const c = useColors();
  const t = useTokens();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  const editable = Boolean(onEdit) && !disabled;

  const startEditing = () => {
    setDraft(content);
    setEditing(true);
  };

  const confirmEdit = () => {
    const trimmed = draft.trim();
    if (!trimmed || !onEdit) return;
    setEditing(false);
    onEdit(trimmed);
  };

  if (editing) {
    return (
      <div
        style={{
          padding: `${t.space[3]} ${t.space[4]}`,
          borderRadius: t.radius.lg,
          background: hexToRgba(c.primary, 0.08),
          border: `1px solid ${hexToRgba(c.primary, 0.4)}`,
          display: "flex",
          flexDirection: "column",
          gap: t.space[2],
        }}
      >
        <Input.TextArea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          autoSize={{ minRows: 2, maxRows: 10 }}
          maxLength={10000}
          autoFocus
          onPressEnter={(event) => {
            if (!event.shiftKey) {
              event.preventDefault();
              confirmEdit();
            }
          }}
        />
        <div style={{ display: "flex", justifyContent: "flex-end", gap: t.space[2] }}>
          <Button size="small" onClick={() => setEditing(false)}>
            取消
          </Button>
          <Button
            size="small"
            type="primary"
            icon={<CheckOutlined />}
            disabled={!draft.trim()}
            onClick={confirmEdit}
          >
            重新生成
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 2 }}>
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
      {editable && (
        <Button
          type="text"
          size="small"
          icon={<EditOutlined />}
          onClick={startEditing}
          style={{ color: c.textMuted, fontSize: t.font.xs, height: 20, paddingInline: 6 }}
        >
          编辑
        </Button>
      )}
    </div>
  );
});
