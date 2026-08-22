import { Card, Col, Empty, Row, Table, Tag, Typography } from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
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
                render: (value: number) => (
                  <Text style={{ color: value >= 0 ? colors.up : colors.down }}>{formatPercent(value)}</Text>
                ),
              },
            ]}
          />
        </Card>
      </Col>
      <Col xs={24} lg={16}>
        <Card
          title="成交记录"
          extra={<Tag>{trades.length} 笔</Tag>}
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
              { title: "代码", dataIndex: "code", width: 90 },
              {
                title: "方向",
                dataIndex: "side",
                width: 70,
                render: (side: string) => <Tag style={semanticTagStyle(side === "buy" ? "up" : "down")}>{side === "buy" ? "买入" : "卖出"}</Tag>,
              },
              { title: "价格", dataIndex: "price", align: "right", render: (value: number) => value.toFixed(2) },
              { title: "股数", dataIndex: "shares", align: "right" },
              { title: "费用", dataIndex: "fee", align: "right", render: (value: number) => value.toFixed(2) },
              {
                title: "实现盈亏",
                dataIndex: "realized_pnl",
                align: "right",
                render: (value?: number | null) => value == null ? "-" : (
                  <Text style={{ color: value >= 0 ? colors.up : colors.down }}>{value.toFixed(2)}</Text>
                ),
              },
            ]}
          />
        </Card>
      </Col>
    </Row>
  );
}
