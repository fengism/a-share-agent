import { useMemo } from "react";
import {
  CrownOutlined,
  PieChartOutlined,
  ThunderboltOutlined,
  TrophyOutlined,
} from "@ant-design/icons";
import { Card, Col, Empty, Row, Space, Table, Tag, Typography } from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
import PreloadLink from "../../../components/PreloadLink";
import { useColors, useStyles } from "../../../styles/ui";
import { getStockName } from "../quantForm";

const { Text } = Typography;

interface ConstituentPerformanceMatrixProps {
  codes: QuantBacktestResult["codes"];
  trades: QuantBacktestResult["trades"];
  marketSnapshots?: QuantBacktestResult["market_snapshots"];
  onSelectCode?: (code: string) => void;
}

interface StockStat {
  code: string;
  name: string;
  tradeCount: number;
  buyCount: number;
  sellCount: number;
  closedCount: number;
  realizedPnl: number;
  totalFee: number;
  winCount: number;
  lossCount: number;
  winRate: number | null;
  avgTurnover: number | null;
}

export default function ConstituentPerformanceMatrix({
  codes,
  trades,
  marketSnapshots = [],
  onSelectCode,
}: ConstituentPerformanceMatrixProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();

  // Aggregate stats per stock code
  const { stockStats, topGainer, topWinRate, mostActive } = useMemo(() => {
    // Map snapshot turnover by code + date
    const turnoverMap = new Map<string, number>();
    for (const snap of marketSnapshots) {
      if (!snap.items) continue;
      for (const item of snap.items) {
        if (item.turnover_pct != null) {
          turnoverMap.set(`${snap.code}_${item.date}`, item.turnover_pct);
        }
      }
    }

    const map: Record<string, StockStat> = {};
    const turnoverSums: Record<string, { sum: number; count: number }> = {};

    // Initialize map with all codes in universe
    for (const code of codes) {
      map[code] = {
        code,
        name: getStockName(code) || code,
        tradeCount: 0,
        buyCount: 0,
        sellCount: 0,
        closedCount: 0,
        realizedPnl: 0,
        totalFee: 0,
        winCount: 0,
        lossCount: 0,
        winRate: null,
        avgTurnover: null,
      };
      turnoverSums[code] = { sum: 0, count: 0 };
    }

    // Process trades
    for (const t of trades) {
      if (!map[t.code]) {
        map[t.code] = {
          code: t.code,
          name: getStockName(t.code) || t.code,
          tradeCount: 0,
          buyCount: 0,
          sellCount: 0,
          closedCount: 0,
          realizedPnl: 0,
          totalFee: 0,
          winCount: 0,
          lossCount: 0,
          winRate: null,
          avgTurnover: null,
        };
        turnoverSums[t.code] = { sum: 0, count: 0 };
      }

      const stat = map[t.code];
      stat.tradeCount++;
      if (t.side === "buy") stat.buyCount++;
      else stat.sellCount++;

      stat.totalFee += t.fee;
      if (t.realized_pnl != null) {
        stat.closedCount++;
        stat.realizedPnl += t.realized_pnl;
        if (t.realized_pnl > 0) stat.winCount++;
        else if (t.realized_pnl < 0) stat.lossCount++;
      }

      // Track turnover on trade date
      const to = turnoverMap.get(`${t.code}_${t.date}`);
      if (to != null) {
        turnoverSums[t.code].sum += to;
        turnoverSums[t.code].count += 1;
      }
    }

    // Finalize rates
    const list: StockStat[] = Object.values(map).map((s) => {
      const winRate = s.closedCount > 0 ? (s.winCount / s.closedCount) * 100 : null;
      const tData = turnoverSums[s.code];
      const avgTurnover = tData && tData.count > 0 ? tData.sum / tData.count : null;
      return { ...s, winRate, avgTurnover };
    });

    // Sort by realized PnL descending
    list.sort((a, b) => b.realizedPnl - a.realizedPnl);

    const activeList = list.filter((s) => s.tradeCount > 0);
    const topGainer = activeList.length > 0 && activeList[0].realizedPnl > 0 ? activeList[0] : null;

    const winRateRanked = [...activeList].filter((s) => s.closedCount >= 2 && s.winRate != null);
    winRateRanked.sort((a, b) => (b.winRate ?? 0) - (a.winRate ?? 0));
    const topWinRate = winRateRanked.length > 0 ? winRateRanked[0] : null;

    const activityRanked = [...activeList].sort((a, b) => b.tradeCount - a.tradeCount);
    const mostActive = activityRanked.length > 0 ? activityRanked[0] : null;

    return { stockStats: list, topGainer, topWinRate, mostActive };
  }, [codes, trades, marketSnapshots]);

  if (codes.length <= 1) {
    return null;
  }

  return (
    <Card
      title={(
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <PieChartOutlined style={{ color: "var(--c-primary)", fontSize: 16 }} />
          <span>多标的盈亏贡献与胜负分析 (Constituent Stock Performance)</span>
          <Tag color="blue">{codes.length} 只标的</Tag>
        </span>
      )}
      size="small"
      style={{ ...cardStyle, marginBottom: 16 }}
      className="quant-result-card"
    >
      {/* Top Highlights */}
      {(topGainer || topWinRate || mostActive) && (
        <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
          {topGainer && (
            <Col xs={24} sm={8}>
              <div
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: "var(--c-radius-sm)",
                  background: "color-mix(in srgb, var(--c-up) 8%, var(--c-nested-bg))",
                  border: "1px solid color-mix(in srgb, var(--c-up) 22%, var(--c-border))",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--c-text-muted)" }}>
                  <TrophyOutlined style={{ color: colors.up }} />
                  <span>最佳盈利贡献标的 (Alpha King)</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
                  <strong style={{ fontSize: 14 }}>
                    {topGainer.name} ({topGainer.code})
                  </strong>
                  <span
                    className="financial-num"
                    style={{ fontSize: 15, fontWeight: 700, color: colors.up }}
                  >
                    +{topGainer.realizedPnl.toFixed(2)}元
                  </span>
                </div>
              </div>
            </Col>
          )}

          {topWinRate && (
            <Col xs={24} sm={8}>
              <div
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: "var(--c-radius-sm)",
                  background: "color-mix(in srgb, var(--c-primary) 8%, var(--c-nested-bg))",
                  border: "1px solid color-mix(in srgb, var(--c-primary) 22%, var(--c-border))",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--c-text-muted)" }}>
                  <CrownOutlined style={{ color: "var(--c-primary)" }} />
                  <span>最高胜率标的</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
                  <strong style={{ fontSize: 14 }}>
                    {topWinRate.name} ({topWinRate.code})
                  </strong>
                  <Tag color="cyan" style={{ margin: 0, fontWeight: 600 }}>
                    胜率 {topWinRate.winRate?.toFixed(1)}%
                  </Tag>
                </div>
              </div>
            </Col>
          )}

          {mostActive && (
            <Col xs={24} sm={8}>
              <div
                style={{
                  padding: "var(--c-pad-inset, 7px 12px)",
                  borderRadius: "var(--c-radius-sm)",
                  background: "var(--c-nested-bg)",
                  border: "1px solid var(--c-border)",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--c-text-muted)" }}>
                  <ThunderboltOutlined style={{ color: "#fa8c16" }} />
                  <span>调仓最活跃标的</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
                  <strong style={{ fontSize: 14 }}>
                    {mostActive.name} ({mostActive.code})
                  </strong>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{mostActive.tradeCount} 笔成交</span>
                </div>
              </div>
            </Col>
          )}
        </Row>
      )}

      {/* Breakdown Table */}
      <Table
        size="small"
        rowKey="code"
        scroll={{ x: 780 }}
        pagination={stockStats.length > 8 ? { pageSize: 8, size: "small" } : false}
        dataSource={stockStats}
        locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无标的统计数据" /> }}
        columns={[
          {
            title: "标的代码与名称",
            key: "code",
            width: 170,
            render: (_, record) => (
              <Space orientation="horizontal" size={6}>
                <PreloadLink
                  to={`/analysis?code=${record.code}`}
                  aria-label={`查看${record.code}研报`}
                  className="financial-num"
                  style={{ fontWeight: 600 }}
                >
                  {record.code}
                </PreloadLink>
                <span style={{ color: "var(--c-text-muted)", fontSize: 12 }}>
                  {record.name}
                </span>
              </Space>
            ),
          },
          {
            title: "累计已实现盈亏",
            dataIndex: "realizedPnl",
            align: "right",
            width: 140,
            sorter: (a, b) => a.realizedPnl - b.realizedPnl,
            render: (value: number, record) => {
              if (record.closedCount === 0) return <span style={{ color: "var(--c-text-muted)" }}>-</span>;
              const isProfit = value > 0;
              const isLoss = value < 0;
              return (
                <Text
                  className="financial-num"
                  style={{
                    fontWeight: 700,
                    color: isProfit ? colors.up : isLoss ? colors.down : colors.textPrimary,
                  }}
                >
                  {isProfit ? `+${value.toFixed(2)}` : value.toFixed(2)}
                </Text>
              );
            },
          },
          {
            title: "胜率",
            dataIndex: "winRate",
            align: "right",
            width: 110,
            sorter: (a, b) => (a.winRate ?? -1) - (b.winRate ?? -1),
            render: (value: number | null, record) => {
              if (value == null) return <span style={{ color: "var(--c-text-muted)" }}>-</span>;
              const color = value >= 60 ? "success" : value >= 45 ? "blue" : "default";
              return (
                <Tag color={color} style={{ margin: 0, fontVariantNumeric: "tabular-nums" }}>
                  {value.toFixed(1)}% ({record.winCount}/{record.closedCount})
                </Tag>
              );
            },
          },
          {
            title: "成交笔数",
            key: "trades",
            align: "center",
            width: 120,
            sorter: (a, b) => a.tradeCount - b.tradeCount,
            render: (_, record) => (
              <span className="financial-num" style={{ fontSize: 12 }}>
                {record.tradeCount} 笔
                <small style={{ color: "var(--c-text-muted)", marginLeft: 4 }}>
                  (买{record.buyCount}/卖{record.sellCount})
                </small>
              </span>
            ),
          },
          {
            title: "交易日平均换手",
            dataIndex: "avgTurnover",
            align: "right",
            width: 130,
            sorter: (a, b) => (a.avgTurnover ?? -1) - (b.avgTurnover ?? -1),
            render: (value: number | null) => (
              value != null ? (
                <span className="financial-num" style={{ fontSize: 12 }}>
                  {value.toFixed(2)}%
                </span>
              ) : <span style={{ color: "var(--c-text-muted)" }}>-</span>
            ),
          },
          {
            title: "累计手续费",
            dataIndex: "totalFee",
            align: "right",
            width: 110,
            render: (value: number) => (
              <span className="financial-num" style={{ fontSize: 12, color: "var(--c-text-muted)" }}>
                ¥{value.toFixed(2)}
              </span>
            ),
          },
          {
            title: "点位分析",
            key: "action",
            align: "center",
            width: 90,
            render: (_, record) => (
              <a
                href="#quant-result-trades-chart"
                onClick={(e) => {
                  if (onSelectCode) {
                    e.preventDefault();
                    onSelectCode(record.code);
                    document.getElementById("quant-result-trades-chart")?.scrollIntoView({ behavior: "smooth" });
                  }
                }}
                style={{ fontSize: 12 }}
              >
                看点位
              </a>
            ),
          },
        ]}
      />
    </Card>
  );
}
