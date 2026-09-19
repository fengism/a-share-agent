import { Alert, Card, Empty, Select, Space, Spin, Tag, Typography } from "antd";
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

  useEffect(() => {
    if (!stockCodes.includes(selectedCode)) setSelectedCode(stockCodes[0] ?? "");
  }, [selectedCode, stockCodes]);

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

  const extra = stockCodes.length ? (
    <Space size={8} wrap>
      <Select
        aria-label="实际买卖点股票"
        value={selectedCode}
        onChange={setSelectedCode}
        options={stocks.map((stock) => ({
          label: `${stock.stock_name} (${stock.stock_code})`,
          value: stock.stock_code,
        }))}
        style={{ minWidth: isNarrow ? 160 : 210 }}
        size="small"
      />
      <Tag style={semanticTagStyle("up")}>B 买入</Tag>
      <Tag style={semanticTagStyle("down")}>S 卖出</Tag>
      {kline.data?.source ? <Tag>{kline.data.source} · 不复权</Tag> : null}
    </Space>
  ) : null;

  return (
    <Card
      title="持仓个股实际买卖点"
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
            height={isNarrow ? 320 : 420}
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
          <Typography.Text type="secondary">实际成交明细（由新到旧）</Typography.Text>
          <Space wrap size={[8, 8]} style={{ display: "flex", marginTop: 8 }}>
            {selectedTransactions.map((transaction) => (
              <Tag
                key={transaction.id}
                style={{
                  ...semanticTagStyle(transaction.side === "buy" ? "up" : "down"),
                  marginInlineEnd: 0,
                  padding: "4px 8px",
                  whiteSpace: "normal",
                }}
              >
                <strong>{transaction.side === "buy" ? "B" : "S"}</strong>
                {` ${formatTime(transaction.trade_time)} · ${formatPrice(transaction.trade_price)} · ${formatInteger(transaction.shares)} 股 · 手续费 ${formatMoney(transaction.fee)}`}
              </Tag>
            ))}
          </Space>
        </div>
      ) : null}
    </Card>
  );
}
