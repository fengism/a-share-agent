import { Alert, Button, Card, Empty, Modal, Select, Space, Spin, Tag, Typography } from "antd";
import { FullscreenOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useEffect, useMemo, useState } from "react";
import { useKlineData } from "../../api/queries";
import LazyKlineChart from "../../charts/LazyKlineChart";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { semanticTagStyle, useStyles } from "../../styles/ui";
import type { PortfolioStockSummary, PortfolioTransaction } from "../../types/portfolio";
import { formatInteger, formatMoney, formatPrice, formatTime } from "./portfolioFormatters";
import {
  buildPortfolioTradeMarkers,
  filterPortfolioTransactions,
  resolvePortfolioTradeDateRange,
} from "./portfolioTradeMarkers";

interface PortfolioTradeKlineProps {
  stocks: PortfolioStockSummary[];
  transactions: PortfolioTransaction[];
}

export default function PortfolioTradeKline({ stocks, transactions }: PortfolioTradeKlineProps) {
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const stockCodes = useMemo(() => stocks.map((stock) => stock.stock_code), [stocks]);
  const [selectedCode, setSelectedCode] = useState(stockCodes[0] ?? "");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (!stockCodes.includes(selectedCode)) setSelectedCode(stockCodes[0] ?? "");
  }, [selectedCode, stockCodes]);

  const currentStock = useMemo(
    () => stocks.find((stock) => stock.stock_code === selectedCode),
    [selectedCode, stocks],
  );

  const selectedTransactions = useMemo(
    () => filterPortfolioTransactions(transactions, selectedCode),
    [selectedCode, transactions],
  );
  const markers = useMemo(
    () => buildPortfolioTradeMarkers(transactions, selectedCode),
    [selectedCode, transactions],
  );
  const dateRange = useMemo(
    () => resolvePortfolioTradeDateRange(
      transactions,
      selectedCode,
      dayjs().format("YYYY-MM-DD"),
    ),
    [selectedCode, transactions],
  );
  const kline = useKlineData(
    selectedCode,
    "daily",
    "",
    Boolean(selectedCode && dateRange),
    dateRange,
  );
  const chartItems = useMemo(() => kline.data?.items ?? [], [kline.data?.items]);
  const availableDates = useMemo(
    () => new Set(chartItems.map((item) => item.date)),
    [chartItems],
  );
  const missingMarkerCount = useMemo(
    () => markers.filter((marker) => !availableDates.has(marker.date)).length,
    [availableDates, markers],
  );

  const extra = stockCodes.length && !isNarrow ? (
    <Space size={8} wrap>
      <Select
        aria-label="实际买卖点股票"
        value={selectedCode}
        onChange={setSelectedCode}
        options={stocks.map((stock) => ({
          label: `${stock.stock_name} (${stock.stock_code})`,
          value: stock.stock_code,
        }))}
        style={{ minWidth: 210 }}
        size="small"
      />
      <Tag style={semanticTagStyle("up")}>B 买入</Tag>
      <Tag style={semanticTagStyle("down")}>S 卖出</Tag>
      {kline.data?.source ? <Tag>{kline.data.source} · 不复权</Tag> : null}
      <Button
        size="small"
        icon={<FullscreenOutlined />}
        onClick={() => setExpanded(true)}
        disabled={!chartItems.length}
        title="放大查看实际买卖点大图模式"
      >
        放大
      </Button>
    </Space>
  ) : null;

  const cardTitle = isNarrow ? (
    <div className="portfolio-trade-kline__mobile-head">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontWeight: 600, fontSize: "14px" }}>持仓个股实际买卖点</span>
        {chartItems.length > 0 && (
          <Button
            size="small"
            type="primary"
            ghost
            icon={<FullscreenOutlined />}
            onClick={() => setExpanded(true)}
            style={{ padding: "0 8px", height: 24, fontSize: "12px" }}
          >
            放大
          </Button>
        )}
      </div>
      {stockCodes.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
          <Select
            aria-label="实际买卖点股票"
            value={selectedCode}
            onChange={setSelectedCode}
            options={stocks.map((stock) => ({
              label: `${stock.stock_name} (${stock.stock_code})`,
              value: stock.stock_code,
            }))}
            style={{ flex: "1 1 140px", minWidth: 130 }}
            size="small"
          />
          <Tag style={semanticTagStyle("up")}>B 买入</Tag>
          <Tag style={semanticTagStyle("down")}>S 卖出</Tag>
          {kline.data?.source ? <Tag>{kline.data.source} · 不复权</Tag> : null}
        </div>
      )}
    </div>
  ) : (
    "持仓个股实际买卖点"
  );

  return (
    <>
      <Card
        title={cardTitle}
        size="small"
        style={{ ...cardStyle, marginBottom: 16 }}
        extra={extra}
      >
        {!stockCodes.length ? (
          <Empty description="当前没有持仓，暂无实际买卖点" />
        ) : !selectedTransactions.length ? (
          <Empty description="该持仓暂无交易流水" />
        ) : kline.isLoading ? (
          <div style={{ minHeight: 280, display: "grid", placeItems: "center" }}>
            <Spin tip="加载实际成交区间 K 线" />
          </div>
        ) : kline.error ? (
          <Alert
            type="warning"
            showIcon
            title="K 线加载失败"
            description="真实成交记录仍保留在下方，暂时无法绘制 B/S 点。"
          />
        ) : !chartItems.length ? (
          <Empty description="暂无对应成交区间 K 线" />
        ) : (
          <>
            <LazyKlineChart
              data={chartItems}
              tradeMarkers={markers}
              height={isNarrow ? 360 : 420}
              viewKey={`portfolio-trades:${selectedCode}:${dateRange?.startDate}:${dateRange?.endDate}`}
            />
            {missingMarkerCount > 0 ? (
              <Alert
                type="warning"
                showIcon
                title={`${missingMarkerCount} 个成交日期没有对应 K 线，未绘制标记`}
                style={{ marginTop: 12 }}
              />
            ) : null}
          </>
        )}

        {selectedTransactions.length ? (
          <div style={{ marginTop: 14 }}>
            <Typography.Text type="secondary" style={{ fontSize: "12px" }}>实际成交明细（由新到旧）</Typography.Text>
            <div className="portfolio-trade-kline__tag-list" style={{ marginTop: 8 }}>
              <Space wrap size={[6, 6]}>
                {selectedTransactions.map((transaction) => (
                  <Tag
                    key={transaction.id}
                    style={{
                      ...semanticTagStyle(transaction.side === "buy" ? "up" : "down"),
                      marginInlineEnd: 0,
                      padding: "4px 8px",
                      whiteSpace: "normal",
                      fontSize: "12px",
                    }}
                  >
                    <strong>{transaction.side === "buy" ? "B" : "S"}</strong>
                    {` ${formatTime(transaction.trade_time)} · ${formatPrice(transaction.trade_price)} · ${formatInteger(transaction.shares)} 股 · 手续费 ${formatMoney(transaction.fee)}`}
                  </Tag>
                ))}
              </Space>
            </div>
          </div>
        ) : null}
      </Card>

      {/* 实际买卖点大图模式弹窗 */}
      <Modal
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
            <span style={{ fontWeight: 600 }}>
              {currentStock ? `${currentStock.stock_name} (${currentStock.stock_code})` : selectedCode} 实际买卖点（大图模式）
            </span>
            <Tag style={semanticTagStyle("up")}>B 买入</Tag>
            <Tag style={semanticTagStyle("down")}>S 卖出</Tag>
            {kline.data?.source ? <Tag>{kline.data.source} · 不复权</Tag> : null}
          </div>
        }
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width="min(1380px, 96vw)"
        style={{ top: 20 }}
        styles={{ body: { padding: "8px 4px 12px" } }}
        destroyOnHidden
      >
        {chartItems.length > 0 && (
          <LazyKlineChart
            data={chartItems}
            tradeMarkers={markers}
            height={isNarrow ? 480 : 580}
            viewKey={`portfolio-trades-modal:${selectedCode}:${dateRange?.startDate}:${dateRange?.endDate}`}
          />
        )}
        {selectedTransactions.length > 0 && (
          <div style={{ marginTop: 12, padding: "0 8px" }}>
            <Typography.Text type="secondary" style={{ display: "block", marginBottom: 6, fontSize: "12px" }}>
              成交流水明细（共 {selectedTransactions.length} 笔）
            </Typography.Text>
            <div style={{ maxHeight: 180, overflowY: "auto", display: "flex", flexWrap: "wrap", gap: "6px 8px" }}>
              {selectedTransactions.map((transaction) => (
                <Tag
                  key={transaction.id}
                  style={{
                    ...semanticTagStyle(transaction.side === "buy" ? "up" : "down"),
                    marginInlineEnd: 0,
                    padding: "3px 8px",
                    fontSize: "12px",
                  }}
                >
                  <strong>{transaction.side === "buy" ? "B" : "S"}</strong>
                  {` ${formatTime(transaction.trade_time)} · ${formatPrice(transaction.trade_price)} · ${formatInteger(transaction.shares)} 股 · 手续费 ${formatMoney(transaction.fee)}`}
                </Tag>
              ))}
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
