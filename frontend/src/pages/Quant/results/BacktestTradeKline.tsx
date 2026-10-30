import { useEffect, useMemo, useState } from "react";
import { Alert, Card, Empty, Select, Space, Spin, Tag } from "antd";
import { useKlineData } from "../../../api/queries";
import LazyKlineChart from "../../../charts/LazyKlineChart";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { semanticTagStyle, useStyles } from "../../../styles/ui";
import type { QuantBacktestResult } from "../../../api/queries";
import type { KlineItem } from "../../../types/stock";
import { buildBacktestTradeMarkers, resolveBacktestDateRange, resolveBacktestTradeCodes } from "./backtestTradeMarkers";

interface BacktestTradeKlineProps {
  codes: QuantBacktestResult["codes"];
  equityCurve: QuantBacktestResult["equity_curve"];
  trades: QuantBacktestResult["trades"];
  marketSnapshots?: QuantBacktestResult["market_snapshots"];
}

export default function BacktestTradeKline({ codes, equityCurve, trades, marketSnapshots = [] }: BacktestTradeKlineProps) {
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const tradeCodes = useMemo(() => resolveBacktestTradeCodes(codes, trades), [codes, trades]);
  const [selectedCode, setSelectedCode] = useState(tradeCodes[0] || "");

  useEffect(() => {
    if (!tradeCodes.includes(selectedCode)) setSelectedCode(tradeCodes[0] || "");
  }, [selectedCode, tradeCodes]);

  const dateRange = useMemo(
    () => resolveBacktestDateRange(equityCurve, trades),
    [equityCurve, trades],
  );
  const markers = useMemo(
    () => buildBacktestTradeMarkers(trades, selectedCode),
    [selectedCode, trades],
  );
  const selectedTrades = useMemo(
    () => trades.filter((t) => t.code === selectedCode),
    [selectedCode, trades],
  );
  const selectedPnl = useMemo(
    () => selectedTrades.reduce((sum, t) => sum + (t.realized_pnl ?? 0), 0),
    [selectedTrades],
  );
  const marketSnapshot = marketSnapshots.find((snapshot) => snapshot.code === selectedCode);
  const snapshotItems = useMemo<KlineItem[]>(
    () => (marketSnapshot?.items ?? [])
      .filter((item) => (
        (!dateRange?.startDate || item.date.replace(/-/g, "") >= dateRange.startDate)
        && (!dateRange?.endDate || item.date.replace(/-/g, "") <= dateRange.endDate)
      ))
      .map((item) => ({
        date: item.date,
        open: item.open,
        close: item.close,
        high: item.high,
        low: item.low,
        volume: item.volume,
        amount: item.amount,
        amplitude: item.amplitude ?? null,
        turnover_pct: item.turnover_pct ?? null,
        change_pct: item.change_pct ?? null,
      })),
    [dateRange, marketSnapshot?.items],
  );
  const kline = useKlineData(
    selectedCode,
    "daily",
    "qfq",
    Boolean(selectedCode && dateRange && !snapshotItems.length),
    dateRange,
  );
  const chartItems = snapshotItems.length ? snapshotItems : (kline.data?.items ?? []);
  const chartSource = snapshotItems.length
    ? `回测快照 · ${marketSnapshot?.source || "原始行情"}`
    : kline.data?.source;

  return (
    <Card
      title="个股 K 线与买卖点"
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      className="quant-result-card quant-chart-card"
      extra={tradeCodes.length ? (
        <Space size={8} wrap>
          <Select
            aria-label="交易点位股票"
            value={selectedCode}
            onChange={setSelectedCode}
            options={tradeCodes.map((code) => ({ label: code, value: code }))}
            style={{ minWidth: 116 }}
            size="small"
          />
          <Tag style={semanticTagStyle("up")}>↑ 买入</Tag>
          <Tag style={semanticTagStyle("down")}>↓ 卖出</Tag>
          {selectedTrades.length > 0 ? (
            <Tag color={selectedPnl > 0 ? "success" : selectedPnl < 0 ? "volcano" : "default"}>
              {selectedTrades.length}笔交易{selectedTrades.some((t) => t.realized_pnl != null) ? ` · 平仓盈亏 ${selectedPnl > 0 ? `+${selectedPnl.toFixed(2)}` : selectedPnl.toFixed(2)}元` : ""}
            </Tag>
          ) : null}
          {chartSource ? <Tag>{chartSource}</Tag> : null}
        </Space>
      ) : null}
    >
      {!tradeCodes.length ? (
        <Empty description="本次回测没有买卖成交点" />
      ) : !snapshotItems.length && kline.isLoading ? (
        <div className="quant-chart-empty"><Spin tip="加载回测区间 K 线" /></div>
      ) : !snapshotItems.length && kline.error ? (
        <Alert type="warning" showIcon title="K 线加载失败" description="成交记录仍可在下方表格中查看" />
      ) : !chartItems.length ? (
        <Empty description="暂无对应回测区间 K 线" />
      ) : (
        <LazyKlineChart
          data={chartItems}
          tradeMarkers={markers}
          height={isNarrow ? 320 : 440}
          viewKey={`backtest:${selectedCode}:${marketSnapshot?.data_hash || dateRange?.startDate}:${dateRange?.endDate}`}
        />
      )}
    </Card>
  );
}
