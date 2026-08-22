import { DeleteOutlined, EditOutlined } from "@ant-design/icons";
import { Button, Empty, Popconfirm, Space, Table, Tag, message } from "antd";
import type { TableColumnsType } from "antd";
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
import type { PortfolioTableRenderers } from "./portfolioTableRenderers";

interface PortfolioTransactionTableProps {
  transactions: PortfolioTransaction[];
  renderers: PortfolioTableRenderers;
}

function PortfolioTransactionTable({ transactions, renderers }: PortfolioTransactionTableProps) {
  const { isMobile, renderProfit, renderStock } = renderers;
  const {
    mutateAsync: deleteTransaction,
    isPending: isDeleting,
    variables: deletingTransactionId,
  } = useDeletePortfolioTransaction();
  const [editingTransaction, setEditingTransaction] = useState<PortfolioTransaction | null>(null);
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
      render: formatPrice,
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
      render: formatPrice,
    },
    {
      title: "匹配成本",
      dataIndex: "matched_cost",
      width: 120,
      align: "right",
      render: formatMoney,
    },
  ], []);
  const columns = useMemo<TableColumnsType<PortfolioTransaction>>(() => [
    {
      title: "方向",
      dataIndex: "side",
      width: 75,
      fixed: isMobile ? undefined : "left",
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
      render: formatTime,
    },
    {
      title: "成交价",
      dataIndex: "trade_price",
      width: 105,
      align: "right",
      render: formatPrice,
    },
    {
      title: "股数",
      dataIndex: "shares",
      width: 100,
      align: "right",
      render: formatInteger,
    },
    {
      title: "成交额",
      key: "turnover",
      width: 125,
      align: "right",
      render: (_, record) => formatMoney(record.trade_price * record.shares),
    },
    {
      title: "手续费",
      dataIndex: "fee",
      width: 105,
      align: "right",
      render: formatMoney,
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
      dataIndex: "realized_profit_amount",
      width: 130,
      align: "right",
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
      <PortfolioTableCard title="交易流水">
        <Table<PortfolioTransaction>
          rowKey="id"
          columns={columns}
          dataSource={transactions}
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
