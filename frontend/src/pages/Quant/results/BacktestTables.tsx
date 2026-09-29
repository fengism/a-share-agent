import { useCallback } from "react";
import { Button, Card, Col, Empty, message, Row, Space, Table, Tag, Typography } from "antd";
import { DownloadOutlined } from "@ant-design/icons";
import type { QuantBacktestResult } from "../../../api/queries";
import PreloadLink from "../../../components/PreloadLink";
import { useColors, useStyles, semanticTagStyle } from "../../../styles/ui";
import { formatPercent } from "./formatters";

const { Text } = Typography;

interface BacktestTablesProps {
  monthlyReturns: QuantBacktestResult["monthly_returns"];
  trades: QuantBacktestResult["trades"];
}

export default function BacktestTables({ monthlyReturns, trades }: BacktestTablesProps) {
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
      a.download = `量化回测成交明细_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
    message.success("成交记录已导出为 CSV");
  }, [trades]);

  return (
    <Row gutter={[16, 16]}>
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
