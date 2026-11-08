import React from "react";
import { useNavigate } from "react-router-dom";
import {
  BellOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  LineChartOutlined,
  RobotOutlined,
} from "@ant-design/icons";
import { Button, Checkbox, Space, Tag, Tooltip } from "antd";
import type { WatchlistItem } from "../../../types/watchlist";
import ChangeValue from "../../../components/ChangeValue";
import PreloadLink from "../../../components/PreloadLink";
import { PriceRangeBar } from "../../../components/PriceRangeBar";
import { usePriceFlash } from "../../../hooks/usePriceFlash";
import { triggerStockAiDiagnosis } from "../../../utils/copilotEvents";
import { buildWatchlistStockUrl, buildStockAnalysisUrl } from "../../../utils/stockLinks";

interface WatchlistCardItemProps {
  item: WatchlistItem;
  isSelected: boolean;
  onToggleSelect: (id: number) => void;
  onSetAlert: (item: WatchlistItem) => void;
  onDelete: (item: WatchlistItem) => void;
  onSelectConcept: (conceptName: string) => void;
  onQuickPreview?: (stock: { code: string; name: string }) => void;
}

const WatchlistCardItem: React.FC<WatchlistCardItemProps> = ({
  item,
  isSelected,
  onToggleSelect,
  onSetAlert,
  onDelete,
  onSelectConcept,
  onQuickPreview,
}) => {
  const navigate = useNavigate();
  const flashClass = usePriceFlash(item.current_price);
  const isLimitUp = (item.change_pct ?? 0) >= 9.8;
  const isLimitDown = (item.change_pct ?? 0) <= -9.8;
  const isHighTurnover = (item.turnover_pct ?? 0) >= 10;

  return (
    <div
      className={`watchlist-mobile-card ${isSelected ? "is-selected" : ""}`}
    >
      {/* 上半部分：左侧代码名称，右侧价格与涨跌幅 */}
      <div className="watchlist-mobile-card__top">
        <div className="watchlist-mobile-card__identity">
          <Checkbox
            checked={isSelected}
            onChange={() => onToggleSelect(item.id)}
            aria-label={`选择${item.stock_name}`}
          />
          <PreloadLink
            to={buildWatchlistStockUrl(item.stock_code, item.market)}
            className="watchlist-mobile-card__link"
          >
            <div className="watchlist-mobile-card__name-row">
              <strong className="watchlist-mobile-card__name">
                {item.stock_name}
              </strong>
              {item.market === "hk" && <Tag color="blue" className="watchlist-mobile-card__tag">港股</Tag>}
              {isLimitUp && <Tag color="red" className="watchlist-mobile-card__tag">涨停</Tag>}
              {isLimitDown && <Tag color="green" className="watchlist-mobile-card__tag">跌停</Tag>}
              {isHighTurnover && <Tag color="orange" className="watchlist-mobile-card__tag">高换手</Tag>}
            </div>
            <span className="watchlist-mobile-card__code">
              {item.stock_code}
            </span>
          </PreloadLink>
        </div>

        {/* 右侧价格 & 涨跌幅 */}
        <div className="watchlist-mobile-card__quote">
          <div
            className={[
              flashClass,
              "watchlist-mobile-card__price",
              (item.change_pct ?? 0) > 0 ? "is-up" : (item.change_pct ?? 0) < 0 ? "is-down" : "",
            ]
              .filter(Boolean)
              .join(" ")}
            data-testid="watchlist-card-price"
          >
            {item.current_price != null ? item.current_price.toFixed(2) : "-"}
          </div>
          <div className="watchlist-mobile-card__change">
            <ChangeValue value={item.change_pct} />
          </div>
        </div>
      </div>

      {/* 中间指标栏：日内振幅、成交额、换手率 */}
      <div className="watchlist-mobile-card__metrics">
        <div>
          <span className="u-text-muted">日内区间：</span>
          <PriceRangeBar
            low={item.low_price}
            high={item.high_price}
            current={item.current_price}
          />
        </div>
        <div>
          <span className="u-text-muted">换手：</span>
          <span className="watchlist-mobile-card__mono">
            {item.turnover_pct != null ? `${item.turnover_pct.toFixed(2)}%` : "-"}
          </span>
        </div>
        <div>
          <span className="u-text-muted">成交额：</span>
          <span className="watchlist-mobile-card__mono">
            {item.amount != null
              ? item.amount >= 100_000_000
                ? `${(item.amount / 100_000_000).toFixed(1)}亿`
                : `${(item.amount / 10_000).toFixed(0)}万`
              : "-"}
          </span>
        </div>
      </div>

      {/* 底部概念与操作栏 */}
      <div className="watchlist-mobile-card__footer">
        <div className="watchlist-mobile-card__concepts">
          {(item.concepts || []).slice(0, 2).map((c) => (
            <button
              key={c.code || c.name}
              type="button"
              onClick={() => onSelectConcept(c.name)}
              className="watchlist-mobile-card__concept"
            >
              {c.name}
            </button>
          ))}
        </div>

        <Space size={2}>
          {onQuickPreview ? (
            <Tooltip title="K线速查">
              <Button
                type="text"
                size="small"
                icon={<LineChartOutlined />}
                aria-label={`速查${item.stock_name}K线`}
                onClick={() => onQuickPreview({ code: item.stock_code, name: item.stock_name })}
              />
            </Tooltip>
          ) : null}
          <Tooltip title="AI 伴随体检">
            <Button
              type="text"
              size="small"
              icon={<RobotOutlined className="watchlist-mobile-card__icon-primary" />}
              aria-label={`AI体检${item.stock_name}`}
              onClick={() => triggerStockAiDiagnosis(item.stock_code, item.stock_name, navigate)}
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
};

interface WatchlistCardListProps {
  items: WatchlistItem[];
  selectedIds: number[];
  onToggleSelect: (id: number) => void;
  onSetAlert: (item: WatchlistItem) => void;
  onDelete: (item: WatchlistItem) => void;
  onSelectConcept: (conceptName: string) => void;
  onQuickPreview?: (stock: { code: string; name: string }) => void;
}

export const WatchlistCardList: React.FC<WatchlistCardListProps> = ({
  items,
  selectedIds,
  onToggleSelect,
  onSetAlert,
  onDelete,
  onSelectConcept,
  onQuickPreview,
}) => {
  return (
    <div className="watchlist-mobile-cards">
      {items.map((item) => (
        <WatchlistCardItem
          key={item.id}
          item={item}
          isSelected={selectedIds.includes(item.id)}
          onToggleSelect={onToggleSelect}
          onSetAlert={onSetAlert}
          onDelete={onDelete}
          onSelectConcept={onSelectConcept}
          onQuickPreview={onQuickPreview}
        />
      ))}
    </div>
  );
};
