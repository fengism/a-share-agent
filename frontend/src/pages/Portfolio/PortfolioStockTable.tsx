import { MinusCircleOutlined } from "@ant-design/icons";
import { Button, Empty, Table, Tooltip } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo } from "react";
import ChangeValue from "../../components/ChangeValue";
import type { PortfolioStockSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import {
  formatInteger,
  formatMoney,
  formatPrice,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioStockTableProps {
  stocks: PortfolioStockSummary[];
  renderers: PortfolioTableRenderers;
  onSell: (stock: PortfolioStockSummary) => void;
}

function PortfolioStockTable({ stocks, renderers, onSell }: PortfolioStockTableProps) {
  const { colors, isMobile, renderProfit, renderStock } = renderers;
  const columns = useMemo<TableColumnsType<PortfolioStockSummary>>(() => [
    {
      title: "股票",
      key: "stock",
      width: 150,
      fixed: isMobile ? undefined : "left",
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "剩余批次",
      dataIndex: "position_count",
      width: 95,
      align: "right",
    },
    {
      title: "持仓股数",
      dataIndex: "total_shares",
      width: 110,
      align: "right",
      render: formatInteger,
    },
    {
      title: "平均成本",
      dataIndex: "average_cost",
      width: 110,
      align: "right",
      render: formatPrice,
    },
    {
      title: "当前价",
      dataIndex: "current_price",
      width: 105,
      align: "right",
      render: formatPrice,
    },
    {
      title: "当日涨跌",
      dataIndex: "change_pct",
      width: 110,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "持仓成本",
      dataIndex: "cost_value",
      width: 130,
      align: "right",
      render: formatMoney,
    },
    {
      title: "最新市值",
      dataIndex: "market_value",
      width: 130,
      align: "right",
      render: formatMoney,
    },
    {
      title: <Tooltip title="按已成功定价股票的最新市值计算">仓位占比</Tooltip>,
      dataIndex: "allocation_pct",
      width: 110,
      align: "right",
      render: (value: number | null) => value == null ? "-" : `${value.toFixed(2)}%`,
    },
    {
      title: "浮动盈亏",
      key: "profit",
      width: 130,
      align: "right",
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
    {
      title: <Tooltip title="单股浮动盈亏占全部股票绝对浮动盈亏的比例">盈亏贡献</Tooltip>,
      dataIndex: "profit_contribution_pct",
      width: 110,
      align: "right",
      render: (value: number | null) => (
        value == null
          ? "-"
          : <span style={{ color: changeColor(value, colors) }}>{value.toFixed(2)}%</span>
      ),
    },
    {
      title: "已实现盈亏",
      dataIndex: "realized_profit_amount",
      width: 130,
      align: "right",
      render: (value: number) => renderProfit(value),
    },
    {
      title: "综合盈亏",
      dataIndex: "total_profit_amount",
      width: 130,
      align: "right",
      render: (value: number | null) => renderProfit(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 88,
      fixed: isMobile ? undefined : "right",
      render: (_, record) => (
        <Button
          type="link"
          size="small"
          icon={<MinusCircleOutlined />}
          aria-label={`卖出 ${record.stock_name}`}
          onClick={() => onSell(record)}
        >
          卖出
        </Button>
      ),
    },
  ], [colors, isMobile, onSell, renderProfit, renderStock]);

  return (
    <PortfolioTableCard title="当前持仓汇总" stacked>
      <Table<PortfolioStockSummary>
        rowKey="stock_code"
        columns={columns}
        dataSource={stocks}
        pagination={PORTFOLIO_TABLE_PAGINATION}
        size="middle"
        scroll={{ x: 1_438 }}
        locale={{ emptyText: <Empty description="当前没有持仓" /> }}
      />
    </PortfolioTableCard>
  );
}

export default memo(PortfolioStockTable);
