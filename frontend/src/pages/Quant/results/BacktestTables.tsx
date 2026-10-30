import { useCallback, useMemo, useState } from "react";
import {
  DownloadOutlined,
  TableOutlined,
  UnorderedListOutlined,
} from "@ant-design/icons";
import {
  Button,
  Card,
  Col,
  Empty,
  message,
  Row,
  Segmented,
  Space,
  Table,
  Tag,
  Timeline,
  Typography,
} from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
import PreloadLink from "../../../components/PreloadLink";
import { useColors, useStyles, semanticTagStyle } from "../../../styles/ui";
import { exportTradesCsv } from "./exportTearsheet";
import { formatPercent } from "./formatters";
import MonthlyReturnsHeatmap from "./MonthlyReturnsHeatmap";

const { Text } = Typography;

interface BacktestTablesProps {
  monthlyReturns: QuantBacktestResult["monthly_returns"];
  trades: QuantBacktestResult["trades"];
  metrics?: QuantBacktestResult["metrics"];
  marketSnapshots?: QuantBacktestResult["market_snapshots"];
}

export default function BacktestTables({
  monthlyReturns,
  trades,
  metrics,
  marketSnapshots = [],
}: BacktestTablesProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [tradeViewMode, setTradeViewMode] = useState<"table" | "timeline">("table");

  // Build quick map for market snapshot bar by code + date
  const snapshotMap = useMemo(() => {
    const map = new Map<string, { turnover_pct?: number | null; change_pct?: number | null }>();
    for (const snap of marketSnapshots) {
      if (!snap.items) continue;
      for (const item of snap.items) {
        map.set(`${snap.code}_${item.date}`, {
          turnover_pct: item.turnover_pct,
          change_pct: item.change_pct,
        });
      }
    }
    return map;
  }, [marketSnapshots]);

  const handleExportCsv = useCallback(() => {
    if (trades.length === 0) return;
    exportTradesCsv(trades);
    message.success("成交记录已导出为 CSV");
  }, [trades]);

  return (
    <Row gutter={[16, 16]}>
      {metrics?.avg_holding_days != null && (
        <Col xs={24}>
          <Card
            title="交易特征与持仓周期诊断 (Trade Horizon & Payoff Diagnostics)"
            extra={<Tag color="purple">交易行为深度穿透</Tag>}
            size="small"
            style={cardStyle}
            className="quant-result-card"
          >
            <Row gutter={[16, 12]}>
              <Col xs={12} sm={6}>
                <div>
                  <div style={{ color: "var(--c-text-muted)", fontSize: 12 }}>平均持仓周期</div>
                  <strong style={{ fontSize: 16 }}>{metrics.avg_holding_days} 天</strong>
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div style={{ color: "var(--c-text-muted)", fontSize: 12 }}>盈/亏平均持仓</div>
                  <strong style={{ fontSize: 14 }}>
                    <span style={{ color: colors.up }}>{metrics.avg_win_holding_days ?? "-"}天</span> /{" "}
                    <span style={{ color: colors.down }}>{metrics.avg_loss_holding_days ?? "-"}天</span>
                  </strong>
                  {(metrics.avg_win_holding_days ?? 0) > (metrics.avg_loss_holding_days ?? 0) && (
                    <Tag color="success" style={{ marginLeft: 6, fontSize: 11 }}>
                      让利润奔跑
                    </Tag>
                  )}
                  {metrics.avg_loss_holding_days && metrics.avg_loss_holding_days > 0 && metrics.avg_win_holding_days ? (
                    <div style={{ fontSize: 11, color: "var(--c-text-muted)", marginTop: 2 }}>
                      盈利时长期望: {(metrics.avg_win_holding_days / metrics.avg_loss_holding_days).toFixed(1)}x
                    </div>
                  ) : null}
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div style={{ color: "var(--c-text-muted)", fontSize: 12 }}>平均单笔盈亏额</div>
                  <strong style={{ fontSize: 14 }}>
                    <span style={{ color: colors.up }}>
                      {metrics.avg_win_pnl != null ? `+${metrics.avg_win_pnl}元` : "-"}
                    </span>{" "}
                    /{" "}
                    <span style={{ color: colors.down }}>
                      {metrics.avg_loss_pnl != null ? `${metrics.avg_loss_pnl}元` : "-"}
                    </span>
                  </strong>
                  {metrics.avg_win_pnl && metrics.avg_loss_pnl && Math.abs(metrics.avg_loss_pnl) > 0 ? (
                    <div style={{ fontSize: 11, color: "var(--c-text-muted)", marginTop: 2 }}>
                      平均盈亏比: {(metrics.avg_win_pnl / Math.abs(metrics.avg_loss_pnl)).toFixed(2)}:1
                    </div>
                  ) : null}
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div style={{ color: "var(--c-text-muted)", fontSize: 12 }}>单笔极端盈亏率</div>
                  <strong style={{ fontSize: 14 }}>
                    <span style={{ color: colors.up }}>
                      {metrics.max_win_pct != null ? `+${metrics.max_win_pct}%` : "-"}
                    </span>{" "}
                    /{" "}
                    <span style={{ color: colors.down }}>
                      {metrics.max_loss_pct != null ? `${metrics.max_loss_pct}%` : "-"}
                    </span>
                  </strong>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      )}

      {/* Monthly Returns Heatmap & Details */}
      <Col xs={24}>
        <MonthlyReturnsHeatmap monthlyReturns={monthlyReturns} />
      </Col>

      {/* Trades Details (Table vs Timeline) */}
      <Col xs={24}>
        <Card
          title="成交记录"
          extra={(
            <Space size={8} wrap>
              <Tag>{trades.length} 笔</Tag>
              <Segmented
                size="small"
                options={[
                  { label: "表格", value: "table", icon: <TableOutlined /> },
                  { label: "时间轴", value: "timeline", icon: <UnorderedListOutlined /> },
                ]}
                value={tradeViewMode}
                onChange={(v) => setTradeViewMode(v as "table" | "timeline")}
                aria-label="成交记录视图切换"
              />
              {trades.length > 0 && (
                <Button
                  size="small"
                  icon={<DownloadOutlined />}
                  onClick={handleExportCsv}
                  aria-label="导出成交记录 CSV"
                >
                  导出 CSV
                </Button>
              )}
            </Space>
          )}
          size="small"
          style={cardStyle}
          className="quant-result-card quant-table-card"
        >
          {trades.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成交记录" />
          ) : tradeViewMode === "timeline" ? (
            <div style={{ maxHeight: 420, overflowY: "auto", padding: "12px 16px 0" }}>
              <Timeline
                mode="left"
                items={trades.map((trade) => {
                  const snap = snapshotMap.get(`${trade.code}_${trade.date}`);
                  const isBuy = trade.side === "buy";
                  return {
                    color: isBuy ? colors.up : colors.down,
                    children: (
                      <div
                        style={{
                          marginBottom: 10,
                          padding: "var(--c-pad-inset, 7px 12px)",
                          borderRadius: "var(--c-radius-sm)",
                          background: "var(--c-nested-bg)",
                          border: "1px solid var(--c-border)",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            flexWrap: "wrap",
                            gap: 6,
                          }}
                        >
                          <Space size={6}>
                            <Tag style={semanticTagStyle(isBuy ? "up" : "down")}>
                              {isBuy ? "买入" : "卖出"}
                            </Tag>
                            <PreloadLink
                              to={`/analysis?code=${trade.code}`}
                              aria-label={`查看${trade.code}研报`}
                              className="financial-num"
                              style={{ fontWeight: 600 }}
                            >
                              {trade.code}
                            </PreloadLink>
                            <span style={{ fontSize: 12, color: "var(--c-text-muted)" }}>{trade.date}</span>
                          </Space>
                          <div>
                            <span style={{ fontSize: 12, color: "var(--c-text-muted)" }}>价格: </span>
                            <strong className="financial-num">{trade.price.toFixed(2)}</strong>
                            <span style={{ fontSize: 12, color: "var(--c-text-muted)", marginLeft: 8 }}>股数: </span>
                            <span className="financial-num">{trade.shares.toLocaleString()}</span>
                          </div>
                        </div>
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            marginTop: 6,
                            fontSize: 12,
                            flexWrap: "wrap",
                            gap: 6,
                          }}
                        >
                          <Space size={8}>
                            {snap?.turnover_pct != null && (
                              <Tag color="default" style={{ margin: 0, fontSize: 11 }}>
                                当日换手: {snap.turnover_pct.toFixed(2)}%
                              </Tag>
                            )}
                            {snap?.change_pct != null && (
                              <span style={{ color: snap.change_pct >= 0 ? colors.up : colors.down }}>
                                当日涨跌: {formatPercent(snap.change_pct)}
                              </span>
                            )}
                            <span style={{ color: "var(--c-text-muted)" }}>费用: ¥{trade.fee.toFixed(2)}</span>
                          </Space>
                          {trade.realized_pnl != null && (
                            <div>
                              <span>平仓盈亏: </span>
                              <strong
                                className="financial-num"
                                style={{ color: trade.realized_pnl >= 0 ? colors.up : colors.down }}
                              >
                                {trade.realized_pnl > 0
                                  ? `+${trade.realized_pnl.toFixed(2)}`
                                  : trade.realized_pnl.toFixed(2)}
                              </strong>
                            </div>
                          )}
                        </div>
                      </div>
                    ),
                  };
                })}
              />
            </div>
          ) : (
            <Table
              size="small"
              rowKey={(trade) => `${trade.date}-${trade.code}-${trade.side}-${trade.shares}`}
              scroll={{ x: 860 }}
              pagination={trades.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
              dataSource={trades}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成交记录" /> }}
              columns={[
                { title: "日期", dataIndex: "date", width: 105 },
                {
                  title: "代码",
                  dataIndex: "code",
                  width: 95,
                  render: (code: string) => (
                    <PreloadLink
                      to={`/analysis?code=${code}`}
                      aria-label={`查看${code}研报`}
                      className="financial-num"
                    >
                      {code}
                    </PreloadLink>
                  ),
                },
                {
                  title: "方向",
                  dataIndex: "side",
                  width: 70,
                  render: (side: string) => (
                    <Tag style={semanticTagStyle(side === "buy" ? "up" : "down")}>
                      {side === "buy" ? "买入" : "卖出"}
                    </Tag>
                  ),
                },
                {
                  title: "价格",
                  dataIndex: "price",
                  align: "right",
                  className: "financial-num",
                  render: (value: number) => value.toFixed(2),
                },
                {
                  title: "股数",
                  dataIndex: "shares",
                  align: "right",
                  className: "financial-num",
                  render: (value: number) => value.toLocaleString(),
                },
                {
                  title: "当日换手 / 涨跌",
                  key: "factors",
                  width: 150,
                  render: (_: unknown, record) => {
                    const snap = snapshotMap.get(`${record.code}_${record.date}`);
                    if (!snap || (snap.turnover_pct == null && snap.change_pct == null)) {
                      return <span style={{ color: "var(--c-text-muted)" }}>-</span>;
                    }
                    return (
                      <Space orientation="horizontal" size={6}>
                        {snap.turnover_pct != null ? (
                          <span className="financial-num" style={{ fontSize: 12 }}>
                            {snap.turnover_pct.toFixed(2)}%
                          </span>
                        ) : null}
                        {snap.change_pct != null ? (
                          <Text
                            className="financial-num"
                            style={{
                              fontSize: 11,
                              color: snap.change_pct >= 0 ? colors.up : colors.down,
                            }}
                          >
                            ({snap.change_pct >= 0 ? `+${snap.change_pct.toFixed(1)}%` : `${snap.change_pct.toFixed(1)}%`})
                          </Text>
                        ) : null}
                      </Space>
                    );
                  },
                },
                {
                  title: "费用",
                  dataIndex: "fee",
                  align: "right",
                  className: "financial-num",
                  render: (value: number) => value.toFixed(2),
                },
                {
                  title: "实现盈亏",
                  dataIndex: "realized_pnl",
                  align: "right",
                  className: "financial-num",
                  render: (value?: number | null) => (
                    value == null ? "-" : (
                      <Text style={{ color: value >= 0 ? colors.up : colors.down }}>
                        {value > 0 ? `+${value.toFixed(2)}` : value.toFixed(2)}
                      </Text>
                    )
                  ),
                },
              ]}
            />
          )}
        </Card>
      </Col>
    </Row>
  );
}
