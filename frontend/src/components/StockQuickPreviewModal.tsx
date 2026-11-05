import { useMemo, useState } from "react";
import { Button, Modal, Segmented, Skeleton, Space, Tag, Typography } from "antd";
import { ArrowRightOutlined, LineChartOutlined, StarOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { useKlineData, useStockInfo, useStockIntraday } from "../api/queryHooks/stock";
import { useAddWatchlistItem, useWatchlist } from "../api/queryHooks/watchlist";
import LazyKlineChart from "../charts/LazyKlineChart";
import IntradayChart from "../charts/IntradayChart";
import ChangeValue from "./ChangeValue";
import { useColors } from "../styles/ui";
import "./stock-quick-preview.css";

const { Text } = Typography;

export interface StockQuickPreviewModalProps {
  open: boolean;
  code: string | null;
  name?: string;
  onClose: () => void;
}

export default function StockQuickPreviewModal({
  open,
  code,
  name,
  onClose,
}: StockQuickPreviewModalProps) {
  const navigate = useNavigate();
  const c = useColors();
  const validCode = code ? code.trim() : "";
  const [chartType, setChartType] = useState<"kline" | "intraday">("kline");

  const { data: stockInfo } = useStockInfo(validCode, {
    enabled: open && Boolean(validCode),
  });

  const { data: klineData, isLoading: isKlineLoading } = useKlineData(
    validCode,
    "daily",
    "qfq",
    open && Boolean(validCode) && chartType === "kline",
  );

  const { data: intradayData, isLoading: isIntradayLoading } = useStockIntraday(
    validCode,
    undefined,
    { enabled: open && Boolean(validCode) && chartType === "intraday" },
  );

  const { data: watchlist } = useWatchlist();
  const addToWatchlistMutation = useAddWatchlistItem();

  const isFavorited = useMemo(() => {
    return Boolean(watchlist?.items?.some((item) => item.stock_code === validCode));
  }, [watchlist, validCode]);

  const candleItems = useMemo(() => {
    return klineData?.items ?? [];
  }, [klineData]);

  const intradayItems = useMemo(() => {
    return intradayData?.items ?? [];
  }, [intradayData]);

  const latestCandle = candleItems.length > 0 ? candleItems[candleItems.length - 1] : null;

  const displayName = name || stockInfo?.name || validCode;
  const price = stockInfo?.current_price ?? latestCandle?.close ?? null;
  const changePct = latestCandle?.change_pct ?? null;
  const high = latestCandle?.high ?? null;
  const low = latestCandle?.low ?? null;
  const turnover = stockInfo?.turnover_pct ?? latestCandle?.turnover_pct ?? null;
  const industry = stockInfo?.first_industry?.name || stockInfo?.exchange_industry || null;

  const handleGoToAnalysis = () => {
    if (!validCode) return;
    onClose();
    navigate(`/analysis/${validCode}`);
  };

  const handleToggleWatchlist = () => {
    if (!validCode || isFavorited) return;
    addToWatchlistMutation.mutate({ stock_code: validCode, note: displayName });
  };

  return (
    <Modal
      open={open}
      onCancel={onClose}
      footer={null}
      width={860}
      destroyOnHidden
      centered
      className="stock-quick-preview-modal"
      title={(
        <div className="stock-quick-preview__title-row">
          <div className="stock-quick-preview__title-left">
            <span className="stock-quick-preview__name">{displayName}</span>
            <Tag className="financial-num stock-quick-preview__code-tag">{validCode}</Tag>
            {industry ? (
              <Tag color="cyan">{industry}</Tag>
            ) : null}
          </div>

          <Space size={8}>
            <Button
              size="small"
              icon={<StarOutlined />}
              disabled={isFavorited || addToWatchlistMutation.isPending}
              onClick={handleToggleWatchlist}
            >
              {isFavorited ? "已在自选" : "加自选"}
            </Button>
            <Button
              size="small"
              type="primary"
              icon={<ArrowRightOutlined />}
              onClick={handleGoToAnalysis}
            >
              深度研报
            </Button>
          </Space>
        </div>
      )}
    >
      <div className="stock-quick-preview__body">
        {/* 顶部行情数据横条 */}
        <div className="stock-quick-preview__stats-strip">
          <div className="stock-quick-preview__price-box">
            <span className="stock-quick-preview__price financial-num">
              {price !== null ? price.toFixed(2) : "--"}
            </span>
            <ChangeValue value={changePct} showIcon />
          </div>

          <div className="stock-quick-preview__metrics">
            <div className="metric-cell">
              <span className="metric-label">最高</span>
              <span className="metric-val financial-num">{high !== null ? high.toFixed(2) : "--"}</span>
            </div>
            <div className="metric-cell">
              <span className="metric-label">最低</span>
              <span className="metric-val financial-num">{low !== null ? low.toFixed(2) : "--"}</span>
            </div>
            <div className="metric-cell">
              <span className="metric-label">换手率</span>
              <span className="metric-val financial-num">
                {turnover !== null ? `${turnover.toFixed(2)}%` : "--"}
              </span>
            </div>
          </div>

          <div style={{ marginLeft: "auto" }}>
            <Segmented
              size="small"
              value={chartType}
              onChange={(val) => setChartType(val as "kline" | "intraday")}
              options={[
                { label: "日K", value: "kline" },
                { label: "当日分时", value: "intraday" },
              ]}
            />
          </div>
        </div>

        {/* 图表展示区域 */}
        <div className="stock-quick-preview__chart-container">
          {chartType === "kline" ? (
            isKlineLoading ? (
              <div className="stock-quick-preview__skeleton">
                <Skeleton active paragraph={{ rows: 8 }} />
              </div>
            ) : candleItems.length > 0 ? (
              <LazyKlineChart
                data={candleItems}
                height={380}
                forceRender
              />
            ) : (
              <div className="stock-quick-preview__empty">
                <LineChartOutlined style={{ fontSize: 32, color: c.textMuted }} />
                <Text type="secondary" style={{ marginTop: 8 }}>暂无 K 线历史数据</Text>
              </div>
            )
          ) : (
            isIntradayLoading ? (
              <div className="stock-quick-preview__skeleton">
                <Skeleton active paragraph={{ rows: 8 }} />
              </div>
            ) : intradayItems.length > 0 ? (
              <IntradayChart
                data={intradayItems}
                prevClose={intradayData?.prev_close ?? null}
                height={380}
              />
            ) : (
              <div className="stock-quick-preview__empty">
                <LineChartOutlined style={{ fontSize: 32, color: c.textMuted }} />
                <Text type="secondary" style={{ marginTop: 8 }}>暂无当日分时数据</Text>
              </div>
            )
          )}
        </div>
      </div>
    </Modal>
  );
}
