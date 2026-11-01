import React from "react";
import {
  ArrowUpOutlined,
  FileSearchOutlined,
  RobotOutlined,
  StarFilled,
  StarOutlined,
} from "@ant-design/icons";
import { Button, Space, Tag, Tooltip } from "antd";
import { useNavigate } from "react-router-dom";
import ChangeValue from "../../components/ChangeValue";
import { usePriceFlash } from "../../hooks/usePriceFlash";
import { triggerStockAiDiagnosis } from "../../utils/copilotEvents";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";

export interface StockStickyBarProps {
  code: string;
  name?: string;
  currentPrice?: number | null;
  changePct?: number | null;
  market?: "cn" | "hk";
  isWatched: boolean;
  isWatchlistPending: boolean;
  onToggleWatchlist: () => void;
  visible: boolean;
}

export const StockStickyBar: React.FC<StockStickyBarProps> = ({
  code,
  name,
  currentPrice,
  changePct,
  market = "cn",
  isWatched,
  isWatchlistPending,
  onToggleWatchlist,
  visible,
}) => {
  const navigate = useNavigate();
  const flashClass = usePriceFlash(currentPrice);
  const isHK = market === "hk";

  if (!visible) return null;

  const handleScrollToTop = () => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const priceColor =
    (changePct ?? 0) > 0
      ? "var(--c-up)"
      : (changePct ?? 0) < 0
      ? "var(--c-down)"
      : "var(--c-text-primary)";

  return (
    <aside
      className={`stock-sticky-bar ${visible ? "is-visible" : ""}`}
      aria-label="股票快速行情与导航条"
      aria-hidden={!visible}
    >
      <div className="stock-sticky-bar__container">
        {/* 左侧：股票名称与代码（点击平滑回顶） */}
        <Tooltip title="点击平滑返回页面顶部">
          <button
            type="button"
            className="stock-sticky-bar__stock-info"
            onClick={handleScrollToTop}
            aria-label={`返回顶部：${name || code}`}
          >
            <ArrowUpOutlined className="stock-sticky-bar__top-icon" />
            <strong className="stock-sticky-bar__name">{name || code}</strong>
            <span className="stock-sticky-bar__code">{code}</span>
            {isHK && <Tag color="blue" className="stock-sticky-bar__hk-tag">港股</Tag>}
          </button>
        </Tooltip>

        {/* 中间：最新价与涨跌幅 */}
        <div className="stock-sticky-bar__quote">
          <span
            className={`stock-sticky-bar__price financial-num ${flashClass}`}
            data-testid="sticky-bar-price"
            style={{ color: priceColor }}
          >
            {currentPrice != null ? currentPrice.toFixed(2) : "-"}
          </span>
          <div className="stock-sticky-bar__change">
            <ChangeValue value={changePct} />
          </div>
        </div>

        {/* 右侧：加自选、AI 诊断、研报 */}
        <Space size={6} className="stock-sticky-bar__actions">
          <Tooltip title={isWatched ? "移出自选" : "加入自选"}>
            <Button
              type={isWatched ? "default" : "primary"}
              ghost={!isWatched}
              size="small"
              icon={isWatched ? <StarFilled style={{ color: "#faad14" }} /> : <StarOutlined />}
              loading={isWatchlistPending}
              onClick={onToggleWatchlist}
              aria-label={isWatched ? "移出自选" : "加入自选"}
            />
          </Tooltip>
          <Tooltip title="AI 伴随诊断">
            <Button
              type="text"
              size="small"
              icon={<RobotOutlined style={{ color: "var(--c-primary)" }} />}
              aria-label="AI伴随诊断"
              onClick={() => triggerStockAiDiagnosis(code, name || code, navigate)}
            />
          </Tooltip>
          <Tooltip title="查看深度研报">
            <Button
              type="text"
              size="small"
              className="stock-sticky-bar__report-btn"
              icon={<FileSearchOutlined />}
              aria-label="查看深度研报"
              onClick={() => navigate(buildStockAnalysisUrl(code))}
            />
          </Tooltip>
        </Space>
      </div>
    </aside>
  );
};

export default StockStickyBar;
