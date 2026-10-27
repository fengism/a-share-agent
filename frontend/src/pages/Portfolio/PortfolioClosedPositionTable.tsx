import { DownloadOutlined } from "@ant-design/icons";
import { Button, Empty, Table } from "antd";
import type { TableColumnsType } from "antd";
import { memo, useMemo } from "react";
import type { PortfolioClosedPosition } from "../../types/portfolio";
import { formatInteger, formatMoney, formatTime } from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import { marketDateStamp } from "../../utils/marketTime";
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

  const handleExportCsv = () => {
    const headers = [
      "股票代码",
      "股票名称",
      "交易笔数",
      "买入笔数",
      "卖出笔数",
      "累计卖出股数",
      "FIFO 成本",
      "已实现盈亏额",
      "已实现盈亏率(%)",
      "首次交易时间",
      "清仓时间",
      "持有天数",
    ];
    const lines = closedPositions.map((c) => [
      `\t${c.stock_code}`,
      `"${c.stock_name.replace(/"/g, '""')}"`,
      c.transaction_count,
      c.buy_count,
      c.sell_count,
      c.total_shares,
      c.matched_cost != null ? c.matched_cost.toFixed(2) : "",
      c.realized_profit_amount != null ? c.realized_profit_amount.toFixed(2) : "",
      c.realized_profit_pct != null ? c.realized_profit_pct.toFixed(2) : "",
      `"${c.first_trade_time}"`,
      `"${c.last_trade_time}"`,
      c.holding_days,
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `投资组合已清仓股票_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };

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
      className: "financial-num",
      render: (_, record) => (
        `${record.transaction_count}（买 ${record.buy_count} / 卖 ${record.sell_count}）`
      ),
    },
    {
      title: "累计卖出",
      dataIndex: "total_shares",
      width: 110,
      align: "right",
      className: "financial-num",
      render: formatInteger,
    },
    {
      title: "FIFO 成本",
      dataIndex: "matched_cost",
      width: 125,
      align: "right",
      className: "financial-num",
      render: formatMoney,
    },
    {
      title: "已实现盈亏",
      key: "realized_profit",
      width: 135,
      align: "right",
      className: "financial-num",
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
      className: "financial-num",
      render: (value: number) => `${value} 天`,
    },
  ], [isMobile, renderProfit, renderStock]);

  return (
    <PortfolioTableCard
      title="已清仓股票"
      stacked
      extra={
        closedPositions.length > 0 ? (
          <Button size="small" icon={<DownloadOutlined />} onClick={handleExportCsv}>
            导出 CSV
          </Button>
        ) : null
      }
    >
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
