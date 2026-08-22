import { Empty, Table } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo } from "react";
import type { PortfolioClosedPosition } from "../../types/portfolio";
import { formatInteger, formatMoney, formatTime } from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioClosedPositionTableProps {
  closedPositions: PortfolioClosedPosition[];
  renderers: PortfolioTableRenderers;
}

function PortfolioClosedPositionTable({
  closedPositions,
  renderers,
}: PortfolioClosedPositionTableProps) {
  const { isMobile, renderProfit, renderStock } = renderers;
  const columns = useMemo<TableColumnsType<PortfolioClosedPosition>>(() => [
    {
      title: "股票",
      key: "stock",
      width: 150,
      fixed: isMobile ? undefined : "left",
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "交易笔数",
      key: "transaction_count",
      width: 120,
      align: "right",
      render: (_, record) => (
        `${record.transaction_count}（买 ${record.buy_count} / 卖 ${record.sell_count}）`
      ),
    },
    {
      title: "累计卖出",
      dataIndex: "total_shares",
      width: 110,
      align: "right",
      render: formatInteger,
    },
    {
      title: "FIFO 成本",
      dataIndex: "matched_cost",
      width: 125,
      align: "right",
      render: formatMoney,
    },
    {
      title: "已实现盈亏",
      key: "realized_profit",
      width: 135,
      align: "right",
      render: (_, record) => renderProfit(
        record.realized_profit_amount,
        record.realized_profit_pct,
      ),
    },
    {
      title: "首次交易",
      dataIndex: "first_trade_time",
      width: 150,
      render: formatTime,
    },
    {
      title: "清仓时间",
      dataIndex: "last_trade_time",
      width: 150,
      render: formatTime,
    },
    {
      title: "持有天数",
      dataIndex: "holding_days",
      width: 100,
      align: "right",
      render: (value: number) => `${value} 天`,
    },
  ], [isMobile, renderProfit, renderStock]);

  return (
    <PortfolioTableCard title="已清仓股票" stacked>
      <Table<PortfolioClosedPosition>
        rowKey="stock_code"
        columns={columns}
        dataSource={closedPositions}
        pagination={PORTFOLIO_TABLE_PAGINATION}
        size="middle"
        scroll={{ x: 1_040 }}
        locale={{ emptyText: <Empty description="暂无已清仓股票" /> }}
      />
    </PortfolioTableCard>
  );
}

export default memo(PortfolioClosedPositionTable);
