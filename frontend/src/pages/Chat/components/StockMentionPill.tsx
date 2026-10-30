import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  CheckOutlined,
  FileSearchOutlined,
  LineChartOutlined,
  MessageOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import { Button, Popover, Space, Tag, message } from "antd";
import { useAddWatchlistItem, useWatchlist } from "../../../api/queryHooks/watchlist";
import { useColors, useTokens } from "../../../styles/ui";
import { buildStockAnalysisUrl, isHkStockCode } from "../../../utils/stockLinks";

interface StockMentionPillProps {
  code: string;
  name?: string;
  onSelectPrompt?: (prompt: string) => void;
}

export const StockMentionPill = React.memo(function StockMentionPill({
  code,
  name,
  onSelectPrompt,
}: StockMentionPillProps) {
  const c = useColors();
  const t = useTokens();
  const navigate = useNavigate();
  const [popoverOpen, setPopoverOpen] = useState(false);

  const { data: watchlistData } = useWatchlist();
  const addWatchlistMutation = useAddWatchlistItem();

  const isHK = isHkStockCode(code);
  const isInWatchlist = (watchlistData?.items ?? []).some(
    (item) => item.stock_code === code,
  );

  const handleAddToWatchlist = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isInWatchlist) return;

    addWatchlistMutation.mutate(
      {
        stock_code: code,
        market: isHK ? "hk" : "cn",
        note: name ? `来自AI对话: ${name}` : "来自AI对话",
      },
      {
        onSuccess: () => {
          message.success(`已将 ${name || code} 加入自选股`);
        },
        onError: () => {
          message.error("加入自选失败，请稍后重试");
        },
      },
    );
  };

  const handleAskStock = (e: React.MouseEvent) => {
    e.stopPropagation();
    setPopoverOpen(false);
    if (onSelectPrompt) {
      onSelectPrompt(`分析 ${name || ""} (${code}) 的近期估值、机构预期与技术面走势`);
    }
  };

  const popoverContent = (
    <div style={{ width: 220, padding: 4 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div>
          <strong style={{ fontSize: 14, color: c.textPrimary, display: "block" }}>
            {name || "股票"}
          </strong>
          <span style={{ fontSize: 12, color: c.textMuted }}>
            {isHK ? "港股" : "A股"} · {code}
          </span>
        </div>
        <Tag color={isHK ? "purple" : "blue"}>{isHK ? "HK" : "CN"}</Tag>
      </div>

      <Space direction="vertical" style={{ width: "100%" }} size={6}>
        <Button
          size="small"
          block
          icon={<FileSearchOutlined />}
          onClick={() => {
            setPopoverOpen(false);
            navigate(buildStockAnalysisUrl(code));
          }}
        >
          查看个股研报
        </Button>

        <Button
          size="small"
          block
          icon={isInWatchlist ? <CheckOutlined /> : <PlusOutlined />}
          onClick={handleAddToWatchlist}
          disabled={isInWatchlist || addWatchlistMutation.isPending}
          loading={addWatchlistMutation.isPending}
        >
          {isInWatchlist ? "已在自选" : "加入自选"}
        </Button>

        {onSelectPrompt && (
          <Button
            size="small"
            type="dashed"
            block
            icon={<MessageOutlined />}
            onClick={handleAskStock}
          >
            深度提问此股
          </Button>
        )}
      </Space>
    </div>
  );

  return (
    <Popover
      content={popoverContent}
      trigger="hover"
      open={popoverOpen}
      onOpenChange={setPopoverOpen}
      placement="top"
    >
      <span
        role="button"
        tabIndex={0}
        onClick={() => navigate(buildStockAnalysisUrl(code))}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            navigate(buildStockAnalysisUrl(code));
          }
        }}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 4,
          padding: "1px 7px",
          margin: "0 2px",
          background: `color-mix(in srgb, ${c.primary} 12%, transparent)`,
          border: `1px solid color-mix(in srgb, ${c.primary} 32%, transparent)`,
          borderRadius: t.radius.sm,
          color: c.primary,
          fontSize: "0.92em",
          cursor: "pointer",
          verticalAlign: "baseline",
          transition: "all 0.15s ease",
          fontWeight: 500,
        }}
        className="u-card-interactive"
        title="点击查看个股分析"
      >
        <LineChartOutlined style={{ fontSize: 11 }} />
        <span>{name ? `${name} (${code})` : code}</span>
      </span>
    </Popover>
  );
});
