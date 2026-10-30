import { DeleteOutlined, DownloadOutlined, EditOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Empty, Input, Popconfirm, Space, Table, Tag, Tooltip, message } from "antd";
import type { TableColumnsType } from "antd";
import dayjs from "dayjs";
import { memo, useCallback, useMemo, useState } from "react";
import { useDeletePortfolioTransaction } from "../../api/queries";
import { semanticTagStyle } from "../../styles/ui";
import type { PortfolioLotMatch, PortfolioTransaction } from "../../types/portfolio";
import EditTransactionModal from "./EditTransactionModal";
import {
  errorMessage,
  formatInteger,
  formatMoney,
  formatPrice,
  formatTime,
} from "./portfolioFormatters";
import PortfolioTableCard from "./PortfolioTableCard";
import { PORTFOLIO_TABLE_PAGINATION } from "./portfolioTableConfig";
import { marketDateStamp } from "../../utils/marketTime";
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioTransactionTableProps {
  transactions: PortfolioTransaction[];
  renderers: PortfolioTableRenderers;
  bare?: boolean;
}

function PortfolioTransactionTable({
  transactions,
  renderers,
  bare = false,
}: PortfolioTransactionTableProps) {
  const [searchQuery, setSearchQuery] = useState("");
  const { isMobile, renderProfit, renderStock } = renderers;
  const {
    mutateAsync: deleteTransaction,
    isPending: isDeleting,
    variables: deletingTransactionId,
  } = useDeletePortfolioTransaction();
  const [editingTransaction, setEditingTransaction] = useState<PortfolioTransaction | null>(null);

  const displayTransactions = useMemo(() => {
    if (!searchQuery.trim()) return transactions;
    const q = searchQuery.trim().toLowerCase();
    return transactions.filter(
      (t) =>
        t.stock_code.toLowerCase().includes(q) ||
        t.stock_name.toLowerCase().includes(q) ||
        (t.note && t.note.toLowerCase().includes(q)),
    );
  }, [searchQuery, transactions]);

  const handleExportCsv = () => {
    const headers = [
      "流水ID",
      "交易方向",
      "股票代码",
      "股票名称",
      "币种",
      "汇率(CNY)",
      "成交价(原币)",
      "成交股数",
      "成交金额(CNY)",
      "成交金额(原币)",
      "手续费(CNY)",
      "FIFO成本",
      "已实现盈亏",
      "交易时间",
      "备注",
    ];
    const lines = transactions.map((t) => [
      t.id,
      t.side === "buy" ? "买入" : "卖出",
      `\t${t.stock_code}`,
      `"${t.stock_name.replace(/"/g, '""')}"`,
      t.currency,
      t.fx_rate_to_cny,
      t.trade_price.toFixed(2),
      t.shares,
      t.trade_amount.toFixed(2),
      t.trade_amount_native.toFixed(2),
      t.fee.toFixed(2),
      t.matched_cost != null ? t.matched_cost.toFixed(2) : "",
      t.realized_profit_amount != null ? t.realized_profit_amount.toFixed(2) : "",
      `"${t.trade_time}"`,
      `"${(t.note || "").replace(/"/g, '""')}"`,
    ].join(","));
    const blob = new Blob(["\uFEFF" + [headers.join(","), ...lines].join("\n")], { type: "text/csv;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `投资组合交易流水_${marketDateStamp()}.csv`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
  };
  const handleDelete = useCallback(async (transactionId: number) => {
    try {
      await deleteTransaction(transactionId);
      message.success("交易流水已删除");
    } catch (mutationError) {
      message.error(`删除失败：${errorMessage(mutationError)}`);
    }
  }, [deleteTransaction]);
  const closeEditor = useCallback(() => setEditingTransaction(null), []);
  const lotMatchColumns = useMemo<TableColumnsType<PortfolioLotMatch>>(() => [
    {
      title: "买入流水",
      dataIndex: "buy_transaction_id",
      width: 100,
      render: (value: number) => `#${value}`,
    },
    {
      title: "买入时间",
      dataIndex: "buy_time",
      width: 150,
      render: formatTime,
    },
    {
      title: "买入价",
      dataIndex: "buy_price",
      width: 105,
      align: "right",
      render: (value: number, record) => formatPrice(value, record.currency),
    },
    {
      title: "匹配股数",
      dataIndex: "shares",
      width: 105,
      align: "right",
      render: formatInteger,
    },
    {
      title: "含费单位成本",
      dataIndex: "unit_cost",
      width: 125,
      align: "right",
      render: (value: number, record) => formatPrice(value, record.currency),
    },
    {
      title: "匹配成本(CNY)",
      dataIndex: "matched_cost",
      width: 120,
      align: "right",
      render: (value) => formatMoney(value),
    },
  ], []);
  const columns = useMemo<TableColumnsType<PortfolioTransaction>>(() => [
    {
      title: "方向",
      dataIndex: "side",
      width: 75,
      fixed: isMobile ? undefined : "left",
      sorter: (a, b) => a.side.localeCompare(b.side),
      render: (side: PortfolioTransaction["side"]) => (
        <Tag style={semanticTagStyle(side === "buy" ? "up" : "down")}>
          {side === "buy" ? "买入" : "卖出"}
        </Tag>
      ),
    },
    {
      title: "股票",
      key: "stock",
      width: 150,
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "成交时间",
      dataIndex: "trade_time",
      width: 150,
      sorter: (a, b) => dayjs(a.trade_time).valueOf() - dayjs(b.trade_time).valueOf(),
      render: formatTime,
    },
    {
      title: <Tooltip title="按标的原币显示成交价">成交价</Tooltip>,
      dataIndex: "trade_price",
      width: 105,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.trade_price - b.trade_price,
      render: (value: number, record) => formatPrice(value, record.currency),
    },
    {
      title: "股数",
      dataIndex: "shares",
      width: 100,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.shares - b.shares,
      render: formatInteger,
    },
    {
      title: "成交额(CNY)",
      key: "turnover",
      width: 125,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.trade_amount - b.trade_amount,
      render: (_, record) => formatMoney(record.trade_amount),
    },
    {
      title: "手续费(CNY)",
      dataIndex: "fee",
      width: 105,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => a.fee - b.fee,
      render: (value) => formatMoney(value),
    },
    {
      title: "FIFO 成本",
      dataIndex: "matched_cost",
      width: 125,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.matched_cost ?? 0) - (b.matched_cost ?? 0),
      render: (value) => formatMoney(value),
    },
    {
      title: "已实现盈亏",
      dataIndex: "realized_profit_amount",
      width: 130,
      align: "right",
      className: "financial-num",
      sorter: (a, b) => (a.realized_profit_amount ?? 0) - (b.realized_profit_amount ?? 0),
      render: (value: number | null) => value == null ? "-" : renderProfit(value),
    },
    {
      title: "备注",
      dataIndex: "note",
      width: 180,
      ellipsis: true,
      render: (value: string) => value || "-",
    },
    {
      title: "操作",
      key: "action",
      width: 110,
      fixed: isMobile ? undefined : "right",
      render: (_, record) => (
        <Space size={0}>
          <Button
            type="text"
            aria-label={`编辑 ${record.stock_name} ${formatTime(record.trade_time)} 的${record.side === "buy" ? "买入" : "卖出"}流水`}
            icon={<EditOutlined />}
            onClick={() => setEditingTransaction(record)}
          />
          <Popconfirm
            title="删除这笔交易流水？"
            description="仅当删除后历史持仓仍然有效时才会成功。"
            okText="删除"
            cancelText="取消"
            okButtonProps={{ danger: true }}
            onConfirm={() => handleDelete(record.id)}
          >
            <Button
              danger
              type="text"
              aria-label={`删除 ${record.stock_name} ${formatTime(record.trade_time)} 的${record.side === "buy" ? "买入" : "卖出"}流水`}
              icon={<DeleteOutlined />}
              loading={isDeleting && deletingTransactionId === record.id}
            />
          </Popconfirm>
        </Space>
      ),
    },
  ], [deletingTransactionId, handleDelete, isDeleting, isMobile, renderProfit, renderStock]);
  const expandable = useMemo(() => ({
    expandedRowRender: (record: PortfolioTransaction) => (
      <Table<PortfolioLotMatch>
        rowKey={(match) => `${match.buy_transaction_id}-${match.buy_time}`}
        columns={lotMatchColumns}
        dataSource={record.matches ?? []}
        pagination={false}
        size="small"
        scroll={{ x: 705 }}
      />
    ),
    rowExpandable: (record: PortfolioTransaction) => (
      record.side === "sell" && (record.matches?.length ?? 0) > 0
    ),
  }), [lotMatchColumns]);

  return (
    <>
      <PortfolioTableCard
        title="交易流水"
        stacked={!bare}
        bare={bare}
        extra={
          transactions.length > 0 ? (
            <Space size={8}>
              <Input
                size="small"
                placeholder="搜索交易流水"
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
        <Table<PortfolioTransaction>
          rowKey="id"
          columns={columns}
          dataSource={displayTransactions}
          pagination={PORTFOLIO_TABLE_PAGINATION}
          size="middle"
          scroll={{ x: 1_355 }}
          expandable={expandable}
          locale={{ emptyText: <Empty description="暂无交易流水" /> }}
        />
      </PortfolioTableCard>
      <EditTransactionModal transaction={editingTransaction} onClose={closeEditor} />
    </>
  );
}

export default memo(PortfolioTransactionTable);
