import React, { useState } from "react";
import { CheckOutlined, CloseOutlined, EditOutlined } from "@ant-design/icons";
import { Button, Input, Popover, message } from "antd";
import type { WatchlistItem } from "../../../types/watchlist";

interface WatchlistNoteCellProps {
  item: WatchlistItem;
  onUpdateNote: (stockCode: string, note: string, market?: "cn" | "hk") => Promise<void>;
}

export const WatchlistNoteCell: React.FC<WatchlistNoteCellProps> = ({ item, onUpdateNote }) => {
  const [open, setOpen] = useState(false);
  const [noteText, setNoteText] = useState(item.note || "");
  const [loading, setLoading] = useState(false);

  const handleSave = async () => {
    try {
      setLoading(true);
      await onUpdateNote(item.stock_code, noteText.trim(), item.market);
      setOpen(false);
      message.success("备注已保存");
    } catch {
      message.error("保存备注失败");
    } finally {
      setLoading(false);
    }
  };

  const popoverContent = (
    <div style={{ width: 220 }} onClick={(e) => e.stopPropagation()}>
      <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 6, color: "var(--c-text-primary)" }}>
        编辑 {item.stock_name} 备注
      </div>
      <Input.TextArea
        value={noteText}
        onChange={(e) => setNoteText(e.target.value)}
        placeholder="输入跟踪逻辑、买入理由或止损位..."
        autoSize={{ minRows: 2, maxRows: 4 }}
        maxLength={80}
        showCount
        style={{ fontSize: 12, marginBottom: 8 }}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            void handleSave();
          }
        }}
      />
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 6 }}>
        <Button size="small" icon={<CloseOutlined />} onClick={() => setOpen(false)}>
          取消
        </Button>
        <Button
          type="primary"
          size="small"
          icon={<CheckOutlined />}
          loading={loading}
          onClick={() => void handleSave()}
        >
          保存
        </Button>
      </div>
    </div>
  );

  return (
    <Popover
      content={popoverContent}
      trigger="click"
      open={open}
      onOpenChange={(visible) => {
        setOpen(visible);
        if (visible) setNoteText(item.note || "");
      }}
    >
      <div
        className="watchlist-note-cell"
        style={{
          cursor: "pointer",
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          maxWidth: "100%",
          padding: "2px 4px",
          borderRadius: 4,
          transition: "background 0.2s",
        }}
        title="点击修改备注"
      >
        {item.note ? (
          <span
            style={{
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              borderBottom: "1px dashed var(--c-border)",
              fontSize: 12,
            }}
          >
            {item.note}
          </span>
        ) : (
          <span style={{ color: "var(--c-text-muted)", fontSize: 12, display: "inline-flex", alignItems: "center", gap: 2 }}>
            <EditOutlined style={{ fontSize: 11 }} />
            <span>添加</span>
          </span>
        )}
      </div>
    </Popover>
  );
};
