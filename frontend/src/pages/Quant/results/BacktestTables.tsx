import { useCallback } from "react";
import { Button, Card, Col, Empty, message, Row, Space, Table, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import type { QuantBacktestResult } from "../../../api/queries";
import PreloadLink from "../../../components/PreloadLink";
import { useColors, useStyles, semanticTagStyle } from "../../../styles/ui";
import { marketDateStamp } from "../../../utils/marketTime";
import { formatPercent } from "./formatters";

const { Text } = Typography;

interface BacktestTablesProps {
  monthlyReturns: QuantBacktestResult["monthly_returns"];
  trades: QuantBacktestResult["trades"];
  metrics?: QuantBacktestResult["metrics"];
}

export default function BacktestTables({ monthlyReturns, trades, metrics }: BacktestTablesProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();

  const handleExportCsv = useCallback(() => {
    if (trades.length === 0) return;
    const headers = ["成交日期", "股票代码", "交易方向", "成交价格", "成交股数", "手续费", "已实现盈亏"];
    const lines = trades.map((t) => [
      `"${t.date}"`,
      `\t${t.code}`,
      t.side === "buy" ? "买入" : "卖出",
      t.price.toFixed(2),
      t.shares,
      t.fee.toFixed(2),
      t.realized_pnl != null ? t.realized_pnl.toFixed(2) : "",
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `量化回测成交明细_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
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
                    <span style={{ color: colors.up }}>{metrics.avg_win_holding_days ?? "-"}天</span> / <span style={{ color: colors.down }}>{metrics.avg_loss_holding_days ?? "-"}天</span>
                  </strong>
                  {(metrics.avg_win_holding_days ?? 0) > (metrics.avg_loss_holding_days ?? 0) && (
                    <Tag color="success" style={{ marginLeft: 6, fontSize: 11 }}>让利润奔跑</Tag>
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
                    <span style={{ color: colors.up }}>{metrics.avg_win_pnl != null ? `+${metrics.avg_win_pnl}元` : "-"}</span> / <span style={{ color: colors.down }}>{metrics.avg_loss_pnl != null ? `${metrics.avg_loss_pnl}元` : "-"}</span>
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
                    <span style={{ color: colors.up }}>{metrics.max_win_pct != null ? `+${metrics.max_win_pct}%` : "-"}</span> / <span style={{ color: colors.down }}>{metrics.max_loss_pct != null ? `${metrics.max_loss_pct}%` : "-"}</span>
                  </strong>
                </div>
              </Col>
            </Row>
          </Card>
        </Col>
      )}
      <Col xs={24} lg={8}>
        <Card title="月度收益" size="small" style={cardStyle} className="quant-result-card quant-table-card">
          <Table
            size="small"
            rowKey="month"
            pagination={monthlyReturns.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
            dataSource={monthlyReturns}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无月度收益" /> }}
            columns={[
              { title: "月份", dataIndex: "month" },
              {
                title: "收益率",
                dataIndex: "return_pct",
                align: "right",
                className: "financial-num",
                render: (value: number) => (
                  <Text style={{ color: value >= 0 ? colors.up : colors.down }}>
                    {formatPercent(value)}
                  </Text>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} lg={16}>
        <Card
          title="成交记录"
          extra={(
            <Space size={8}>
              <Tag>{trades.length} 笔</Tag>
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
          <Table
            size="small"
            rowKey={(trade) => `${trade.date}-${trade.code}-${trade.side}-${trade.shares}`}
            scroll={{ x: 760 }}
            pagination={trades.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
            dataSource={trades}
            locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成交记录" /> }}
            columns={[
              { title: "日期", dataIndex: "date", width: 110 },
              {
                title: "代码",
                dataIndex: "code",
                width: 100,
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
        </Card>
      </Col>
    </Row>
  );
}
