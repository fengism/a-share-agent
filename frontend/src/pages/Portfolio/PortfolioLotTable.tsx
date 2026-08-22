import { Empty, Table } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo } from "react";
import type { PortfolioPosition } from "../../types/portfolio";
import {
  formatInteger,
  formatMoney,
  formatPrice,
  formatTime,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioLotTableProps {
  positions: PortfolioPosition[];
  renderers: PortfolioTableRenderers;
}

function PortfolioLotTable({ positions, renderers }: PortfolioLotTableProps) {
  const { isMobile, renderProfit, renderStock } = renderers;
  const columns = useMemo<TableColumnsType<PortfolioPosition>>(() => [
    {
      title: "股票",
      key: "stock",
      width: 150,
      fixed: isMobile ? undefined : "left",
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "买入时间",
      dataIndex: "buy_time",
      width: 150,
      render: formatTime,
    },
    {
      title: "成交价",
      dataIndex: "buy_price",
      width: 105,
      align: "right",
      render: formatPrice,
    },
    {
      title: "剩余股数",
      dataIndex: "shares",
      width: 110,
      align: "right",
      render: formatInteger,
    },
    {
      title: "剩余成本",
      dataIndex: "cost_value",
      width: 125,
      align: "right",
      render: formatMoney,
    },
    {
      title: "当前价",
      dataIndex: "current_price",
      width: 105,
      align: "right",
      render: formatPrice,
    },
    {
      title: "浮动盈亏",
      key: "profit",
      width: 130,
      align: "right",
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
  ], [isMobile, renderProfit, renderStock]);

  return (
    <PortfolioTableCard title="FIFO 剩余批次" stacked>
      <Table<PortfolioPosition>
        rowKey="id"
        columns={columns}
        dataSource={positions}
        pagination={PORTFOLIO_TABLE_PAGINATION}
        size="middle"
        scroll={{ x: 875 }}
        locale={{ emptyText: <Empty description="暂无未卖完的买入批次" /> }}
      />
    </PortfolioTableCard>
  );
}

export default memo(PortfolioLotTable);
