import { DownloadOutlined, MinusCircleOutlined } from "@ant-design/icons";
import { Button, Empty, Space, Table, Tooltip } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo } from "react";
import ChangeValue from "../../components/ChangeValue";
import PreloadLink from "../../components/PreloadLink";
import type { PortfolioStockSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import {
  formatInteger,
  formatMoney,
  formatPrice,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import { marketDateStamp } from "../../utils/marketTime";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioStockTableProps {
  stocks: PortfolioStockSummary[];
  renderers: PortfolioTableRenderers;
  onSell: (stock: PortfolioStockSummary) => void;
}

function PortfolioStockTable({ stocks, renderers, onSell }: PortfolioStockTableProps) {
  const { colors, isMobile, renderProfit, renderStock } = renderers;

  const handleExportCsv = () => {
    const headers = [
      "股票代码",
      "股票名称",
      "剩余批次",
      "持仓股数",
      "平均成本",
      "当前价",
      "当日涨跌(%)",
      "持仓成本",
      "最新市值",
      "仓位占比(%)",
      "浮动盈亏额",
      "浮动盈亏率(%)",
      "已实现盈亏",
      "综合盈亏",
    ];
    const lines = stocks.map((s) => [
      `\t${s.stock_code}`,
      `"${s.stock_name.replace(/"/g, '""')}"`,
      s.position_count,
      s.total_shares,
      s.average_cost != null ? s.average_cost.toFixed(2) : "",
      s.current_price != null ? s.current_price.toFixed(2) : "",
      s.change_pct != null ? s.change_pct.toFixed(2) : "",
      s.cost_value != null ? s.cost_value.toFixed(2) : "",
      s.market_value != null ? s.market_value.toFixed(2) : "",
      s.allocation_pct != null ? s.allocation_pct.toFixed(2) : "",
      s.profit_amount != null ? s.profit_amount.toFixed(2) : "",
      s.profit_pct != null ? s.profit_pct.toFixed(2) : "",
      s.realized_profit_amount != null ? s.realized_profit_amount.toFixed(2) : "",
      s.total_profit_amount != null ? s.total_profit_amount.toFixed(2) : "",
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `投资组合当前持仓_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };

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
      className: "financial-num",
    },
    {
      title: "持仓股数",
      dataIndex: "total_shares",
      width: 110,
      align: "right",
      className: "financial-num",
      render: formatInteger,
    },
    {
      title: "平均成本",
      dataIndex: "average_cost",
      width: 110,
      align: "right",
      className: "financial-num",
      render: formatPrice,
    },
    {
      title: "当前价",
      dataIndex: "current_price",
      width: 105,
      align: "right",
      className: "financial-num",
      render: formatPrice,
    },
    {
      title: "当日涨跌",
      dataIndex: "change_pct",
      width: 110,
      align: "right",
      className: "financial-num",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "持仓成本",
      dataIndex: "cost_value",
      width: 130,
      align: "right",
      className: "financial-num",
      render: formatMoney,
    },
    {
      title: "最新市值",
      dataIndex: "market_value",
      width: 130,
      align: "right",
      className: "financial-num",
      render: formatMoney,
    },
    {
      title: <Tooltip title="按已成功定价股票的最新市值计算">仓位占比</Tooltip>,
      dataIndex: "allocation_pct",
      width: 110,
      align: "right",
      className: "financial-num",
      render: (value: number | null) => value == null ? "-" : `${value.toFixed(2)}%`,
    },
    {
      title: "浮动盈亏",
      key: "profit",
      width: 130,
      align: "right",
      className: "financial-num",
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
    {
      title: <Tooltip title="单股浮动盈亏占全部股票绝对浮动盈亏的比例">盈亏贡献</Tooltip>,
      dataIndex: "profit_contribution_pct",
      width: 110,
      align: "right",
      className: "financial-num",
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
      className: "financial-num",
      render: (value: number) => renderProfit(value),
    },
    {
      title: "综合盈亏",
      dataIndex: "total_profit_amount",
      width: 130,
      align: "right",
      className: "financial-num",
      render: (value: number | null) => renderProfit(value),
    },
    {
      title: "操作",
      key: "actions",
      width: 128,
      fixed: isMobile ? undefined : "right",
      render: (_, record) => (
        <Space size={4}>
          <PreloadLink
            to={`/analysis?code=${record.stock_code}`}
            aria-label={`查看${record.stock_name}研报`}
          >
            <Button
              type="link"
              size="small"
              style={{ padding: "0 2px" }}
            >
              研报
            </Button>
          </PreloadLink>
          <Button
            type="link"
            size="small"
            icon={<MinusCircleOutlined />}
            aria-label={`卖出 ${record.stock_name}`}
            onClick={() => onSell(record)}
            style={{ padding: "0 2px" }}
          >
            卖出
          </Button>
        </Space>
      ),
    },
  ], [colors, isMobile, onSell, renderProfit, renderStock]);

  return (
    <PortfolioTableCard
      title="当前持仓汇总"
      stacked
      extra={
        stocks.length > 0 ? (
          <Button size="small" icon={<DownloadOutlined />} onClick={handleExportCsv}>
            导出 CSV
          </Button>
        ) : null
      }
    >
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
