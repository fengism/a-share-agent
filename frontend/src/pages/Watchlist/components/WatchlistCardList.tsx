import React from "react";
import { useNavigate } from "react-router-dom";
import {
  BellOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Button, Checkbox, Space, Tag, Tooltip } from "antd";
import type { WatchlistItem } from "../../../types/watchlist";
import ChangeValue from "../../../components/ChangeValue";
import PreloadLink from "../../../components/PreloadLink";
import { PriceRangeBar } from "../../../components/PriceRangeBar";
import { buildWatchlistStockUrl } from "../../../utils/stockLinks";
import { buildStockAnalysisUrl } from "../../../utils/stockLinks";

interface WatchlistCardListProps {
  items: WatchlistItem[];
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  onSetAlert: (item: WatchlistItem) => void;
  onDelete: (item: WatchlistItem) => void;
  onSelectConcept: (conceptName: string) => void;
}

export const WatchlistCardList: React.FC<WatchlistCardListProps> = ({
  items,
  selectedIds,
  onToggleSelect,
  onSetAlert,
  onDelete,
  onSelectConcept,
}) => {
  const navigate = useNavigate();
  return (
    <div
      className="watchlist-mobile-cards"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 10,
        margin: "8px 0",
      }}
    >
      {items.map((item) => {
        const isSelected = selectedIds.includes(item.id);
        const isLimitUp = (item.change_pct ?? 0) >= 9.8;
        const isLimitDown = (item.change_pct ?? 0) <= -9.8;
        const isHighTurnover = (item.turnover_pct ?? 0) >= 10;

        return (
          <div
            key={item.id}
            className={`watchlist-mobile-card ${isSelected ? "is-selected" : ""}`}
            style={{
              display: "flex",
              flexDirection: "column",
              gap: 8,
              padding: "var(--c-pad-card, 16px 18px)",
              background: "var(--c-card-bg)",
              border: isSelected
                ? "1px solid var(--c-primary)"
                : "1px solid var(--c-border)",
              borderRadius: 8,
              transition: "border-color 0.2s, box-shadow 0.2s",
            }}
          >
            {/* 上半部分：左侧代码名称，右侧价格与涨跌幅 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <Checkbox
                  checked={isSelected}
                  onChange={() => onToggleSelect(item.id)}
                  aria-label={`选择${item.stock_name}`}
                />
                <PreloadLink
                  to={buildWatchlistStockUrl(item.stock_code, item.market)}
                  style={{ display: "flex", flexDirection: "column" }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <strong style={{ fontSize: 16, color: "var(--c-text-primary)" }}>
                      {item.stock_name}
                    </strong>
                    {item.market === "hk" && <Tag color="blue" style={{ margin: 0, fontSize: 10 }}>港股</Tag>}
                    {isLimitUp && <Tag color="red" style={{ margin: 0, fontSize: 10 }}>涨停</Tag>}
                    {isLimitDown && <Tag color="green" style={{ margin: 0, fontSize: 10 }}>跌停</Tag>}
                    {isHighTurnover && <Tag color="orange" style={{ margin: 0, fontSize: 10 }}>高换手</Tag>}
                  </div>
                  <span
                    style={{
                      fontSize: 12,
                      fontFamily: "var(--c-font-mono)",
                      color: "var(--c-text-muted)",
                    }}
                  >
                    {item.stock_code}
                  </span>
                </PreloadLink>
              </div>

              {/* 右侧价格 & 涨跌幅 */}
              <div style={{ textAlign: "right" }}>
                <div
                  style={{
                    fontSize: 16,
                    fontWeight: 700,
                    fontFamily: "var(--c-font-mono)",
                    color:
                      (item.change_pct ?? 0) > 0
                        ? "var(--c-up)"
                        : (item.change_pct ?? 0) < 0
                        ? "var(--c-down)"
                        : "var(--c-text-primary)",
                  }}
                >
                  {item.current_price != null ? item.current_price.toFixed(2) : "-"}
                </div>
                <div style={{ fontSize: 13, fontWeight: 600 }}>
                  <ChangeValue value={item.change_pct} />
                </div>
              </div>
            </div>

            {/* 中间指标栏：日内振幅、成交额、换手率 */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr 1fr",
                alignItems: "center",
                gap: 8,
                padding: "6px 8px",
                background: "color-mix(in srgb, var(--c-page-bg) 60%, transparent)",
                borderRadius: 6,
                fontSize: 11,
              }}
            >
              <div>
                <span style={{ color: "var(--c-text-muted)" }}>日内区间：</span>
                <PriceRangeBar
                  low={item.low_price}
                  high={item.high_price}
                  current={item.current_price}
                />
              </div>
              <div>
                <span style={{ color: "var(--c-text-muted)" }}>换手：</span>
                <span style={{ fontFamily: "var(--c-font-mono)" }}>
                  {item.turnover_pct != null ? `${item.turnover_pct.toFixed(2)}%` : "-"}
                </span>
              </div>
              <div>
                <span style={{ color: "var(--c-text-muted)" }}>成交额：</span>
                <span style={{ fontFamily: "var(--c-font-mono)" }}>
                  {item.amount != null
                    ? item.amount >= 100_000_000
                      ? `${(item.amount / 100_000_000).toFixed(1)}亿`
                      : `${(item.amount / 10_000).toFixed(0)}万`
                    : "-"}
                </span>
              </div>
            </div>

            {/* 底部概念与操作栏 */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexWrap: "wrap",
                gap: 6,
                paddingTop: 2,
              }}
            >
              <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                {(item.concepts || []).slice(0, 2).map((c) => (
                  <button
                    key={c.code || c.name}
                    type="button"
                    onClick={() => onSelectConcept(c.name)}
                    style={{
                      background: "var(--c-nested-bg)",
                      border: "1px solid var(--c-border)",
                      borderRadius: 3,
                      fontSize: 10,
                      padding: "1px 5px",
                      color: "var(--c-text-secondary)",
                      cursor: "pointer",
                    }}
                  >
                    {c.name}
                  </button>
                ))}
              </div>

              <Space size={2}>
                <Tooltip title="AI 深度体检">
                  <Button
                    type="text"
                    size="small"
                    icon={<RobotOutlined style={{ color: "var(--c-primary)" }} />}
                    aria-label={`AI体检${item.stock_name}`}
                    onClick={() =>
                      navigate(
                        `/chat?prompt=${encodeURIComponent(
                          `请全面深度诊断【${item.stock_name}(${item.stock_code})】的投资价值、核心驱动力、估值水平与主要风险点`,
                        )}`,
                      )
                    }
                  />
                </Tooltip>
                <Tooltip title="查看研报">
                  <Button
                    type="text"
                    size="small"
                    icon={<FileSearchOutlined />}
                    aria-label={`研报${item.stock_name}`}
                    onClick={() => navigate(buildStockAnalysisUrl(item.stock_code))}
                  />
                </Tooltip>
                <Tooltip title="设置提醒">
                  <Button
                    type="text"
                    size="small"
                    icon={<BellOutlined />}
                    onClick={() => onSetAlert(item)}
                    aria-label={`设置${item.stock_name}提醒`}
                  />
                </Tooltip>
                <Tooltip title="移除自选">
                  <Button
                    type="text"
                    danger
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => onDelete(item)}
                    aria-label={`移除${item.stock_name}`}
                  />
                </Tooltip>
              </Space>
            </div>
          </div>
        );
      })}
    </div>
  );
};
