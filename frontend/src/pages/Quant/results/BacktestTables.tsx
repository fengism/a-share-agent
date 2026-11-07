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
            className="quant-result-card u-card"
          >
            <Row gutter={[16, 12]}>
              <Col xs={12} sm={6}>
                <div>
                  <div className="quant-diag-label">平均持仓周期</div>
                  <strong className="quant-diag-val-lg">{metrics.avg_holding_days} 天</strong>
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div className="quant-diag-label">盈/亏平均持仓</div>
                  <strong className="quant-diag-val">
                    <span className="u-text-up">{metrics.avg_win_holding_days ?? "-"}天</span> /{" "}
                    <span className="u-text-down">{metrics.avg_loss_holding_days ?? "-"}天</span>
                  </strong>
                  {(metrics.avg_win_holding_days ?? 0) > (metrics.avg_loss_holding_days ?? 0) && (
                    <Tag color="blue" className="quant-diag-tag">
                      让利润奔跑
                    </Tag>
                  )}
                  {metrics.avg_loss_holding_days && metrics.avg_loss_holding_days > 0 && metrics.avg_win_holding_days ? (
                    <div className="quant-diag-sub">
                      盈利时长期望: {(metrics.avg_win_holding_days / metrics.avg_loss_holding_days).toFixed(1)}x
                    </div>
                  ) : null}
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div className="quant-diag-label">平均单笔盈亏额</div>
                  <strong className="quant-diag-val">
                    <span className="u-text-up">
                      {metrics.avg_win_pnl != null ? `+${metrics.avg_win_pnl}元` : "-"}
                    </span>{" "}
                    /{" "}
                    <span className="u-text-down">
                      {metrics.avg_loss_pnl != null ? `${metrics.avg_loss_pnl}元` : "-"}
                    </span>
                  </strong>
                  {metrics.avg_win_pnl && metrics.avg_loss_pnl && Math.abs(metrics.avg_loss_pnl) > 0 ? (
                    <div className="quant-diag-sub">
                      平均盈亏比: {(metrics.avg_win_pnl / Math.abs(metrics.avg_loss_pnl)).toFixed(2)}:1
                    </div>
                  ) : null}
                </div>
              </Col>
              <Col xs={12} sm={6}>
                <div>
                  <div className="quant-diag-label">单笔极端盈亏率</div>
                  <strong className="quant-diag-val">
                    <span className="u-text-up">
                      {metrics.max_win_pct != null ? `+${metrics.max_win_pct}%` : "-"}
                    </span>{" "}
                    /{" "}
                    <span className="u-text-down">
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
          className="quant-result-card quant-table-card u-card"
        >
          {trades.length === 0 ? (
            <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成交记录" />
          ) : tradeViewMode === "timeline" ? (
            <div className="quant-trade-timeline-wrap">
              <Timeline
                mode="left"
                items={trades.map((trade) => {
                  const snap = snapshotMap.get(`${trade.code}_${trade.date}`);
                  const isBuy = trade.side === "buy";
                  return {
                    color: isBuy ? "var(--c-up)" : "var(--c-down)",
                    children: (
                      <div className="quant-trade-timeline-card">
                        <div className="quant-trade-card-top">
                          <Space size={6}>
                            <Tag className={isBuy ? "quant-trade-tag--buy" : "quant-trade-tag--sell"}>
                              {isBuy ? "买入" : "卖出"}
                            </Tag>
                            <PreloadLink
                              to={`/analysis?code=${trade.code}`}
                              aria-label={`查看${trade.code}研报`}
                              className="financial-num quant-trade-code-link"
                            >
                              {trade.code}
                            </PreloadLink>
                            <span className="quant-trade-date">{trade.date}</span>
                          </Space>
                          <div>
                            <span className="quant-trade-label">价格: </span>
                            <strong className="financial-num">{trade.price.toFixed(2)}</strong>
                            <span className="quant-trade-label--ml">股数: </span>
                            <span className="financial-num">{trade.shares.toLocaleString()}</span>
                          </div>
                        </div>
                        <div className="quant-trade-card-bottom">
                          <Space size={8}>
                            {snap?.turnover_pct != null && (
                              <Tag color="default" className="quant-trade-snap-tag">
                                当日换手: {snap.turnover_pct.toFixed(2)}%
                              </Tag>
                            )}
                            {snap?.change_pct != null && (
                              <span className={snap.change_pct >= 0 ? "u-text-up" : "u-text-down"}>
                                当日涨跌: {formatPercent(snap.change_pct)}
                              </span>
                            )}
                            <span className="quant-trade-fee">费用: ¥{trade.fee.toFixed(2)}</span>
                          </Space>
                          {trade.realized_pnl != null && (
                            <div>
                              <span>平仓盈亏: </span>
                              <strong
                                className={`financial-num ${trade.realized_pnl >= 0 ? "u-text-up" : "u-text-down"}`}
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
                    <Tag className={side === "buy" ? "quant-trade-tag--buy" : "quant-trade-tag--sell"}>
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
                      return <span className="u-text-muted">-</span>;
                    }
                    return (
                      <Space orientation="horizontal" size={6}>
                        {snap.turnover_pct != null ? (
                          <span className="financial-num quant-trade-table-num">
                            {snap.turnover_pct.toFixed(2)}%
                          </span>
                        ) : null}
                        {snap.change_pct != null ? (
                          <Text
                            className={`financial-num quant-trade-table-change ${snap.change_pct >= 0 ? "u-text-up" : "u-text-down"}`}
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
                      <Text className={value >= 0 ? "u-text-up" : "u-text-down"}>
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
