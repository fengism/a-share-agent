import { DownloadOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Empty, Input, Space, Table } from "antd";
import type { TableColumnsType } from "antd";
import dayjs from "dayjs";
import { memo, useMemo, useState } from "react";
import type { PortfolioPosition } from "../../types/portfolio";
import {
  formatInteger,
  formatMoney,
  formatPrice,
  formatTime,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import { marketDateStamp } from "../../utils/marketTime";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioLotTableProps {
  positions: PortfolioPosition[];
  renderers: PortfolioTableRenderers;
  bare?: boolean;
}

function PortfolioLotTable({ positions, renderers, bare = false }: PortfolioLotTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const { isMobile, renderProfit, renderStock } = renderers;

  const handleExportCsv = () => {
    const headers = [
      "股票代码",
      "股票名称",
      "买入时间",
      "成交价",
      "剩余股数",
      "剩余成本(CNY)",
      "当前价",
      "浮动盈亏额",
      "浮动盈亏率(%)",
    ];
    const lines = positions.map((p) => [
      `\t${p.stock_code}`,
      `"${p.stock_name.replace(/"/g, '""')}"`,
      `"${p.buy_time}"`,
      p.buy_price != null ? p.buy_price.toFixed(2) : "",
      p.shares,
      p.cost_value != null ? p.cost_value.toFixed(2) : "",
      p.current_price != null ? p.current_price.toFixed(2) : "",
      p.profit_amount != null ? p.profit_amount.toFixed(2) : "",
      p.profit_pct != null ? p.profit_pct.toFixed(2) : "",
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `投资组合FIFO批次_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };

  const displayPositions = useMemo(() => {
    if (!searchQuery.trim()) return positions;
    const q = searchQuery.trim().toLowerCase();
    return positions.filter(
      (p) =>
        p.stock_code.toLowerCase().includes(q) ||
        p.stock_name.toLowerCase().includes(q),
    );
  }, [positions, searchQuery]);

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
      sorter: (a, b) => dayjs(a.buy_time).valueOf() - dayjs(b.buy_time).valueOf(),
      render: formatTime,
    },
    {
      title: "成交价",
      dataIndex: "buy_price",
      width: 105,
      align: "right",
      sorter: (a, b) => a.buy_price - b.buy_price,
      render: (value: number, record) => formatPrice(value, record.currency),
    },
    {
      title: "剩余股数",
      dataIndex: "shares",
      width: 110,
      align: "right",
      sorter: (a, b) => a.shares - b.shares,
      render: formatInteger,
    },
    {
      title: "剩余成本(CNY)",
      dataIndex: "cost_value",
      width: 125,
      align: "right",
      sorter: (a, b) => (a.cost_value ?? 0) - (b.cost_value ?? 0),
      render: (value) => formatMoney(value),
    },
    {
      title: "当前价",
      dataIndex: "current_price",
      width: 105,
      align: "right",
      render: (value: number | null | undefined, record) => formatPrice(value, record.currency),
    },
    {
      title: "浮动盈亏",
      key: "profit",
      width: 130,
      align: "right",
      sorter: (a, b) => (a.profit_amount ?? 0) - (b.profit_amount ?? 0),
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
  ], [isMobile, renderProfit, renderStock]);

  return (
    <PortfolioTableCard
      title="FIFO 剩余批次"
      stacked={!bare}
      bare={bare}
      extra={
        positions.length > 0 ? (
          <Space size={8}>
            <Input
              size="small"
              placeholder="搜索批次标的"
              prefix={<SearchOutlined />}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              allowClear
              style={{ width: 140 }}
            />
            <Button size="small" icon={<DownloadOutlined />} onClick={handleExportCsv}>
              导出 CSV
            </Button>
          </Space>
        ) : null
      }
    >
      <Table<PortfolioPosition>
        rowKey="id"
        columns={columns}
        dataSource={displayPositions}
        pagination={PORTFOLIO_TABLE_PAGINATION}
        size="middle"
        scroll={{ x: 875 }}
        locale={{ emptyText: <Empty description="暂无未卖完的买入批次" /> }}
      />
    </PortfolioTableCard>
  );
}

export default memo(PortfolioLotTable);
