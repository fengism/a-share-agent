import { DeleteOutlined } from "@ant-design/icons";
import { Button, Card, Empty, Popconfirm, Table, Typography, message } from "antd";
import type { TableColumnsType } from "antd";
import { useNavigate } from "react-router-dom";
import { useDeletePortfolioPosition } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import type { PortfolioPosition, PortfolioStockSummary } from "../../types/portfolio";
import { changeColor } from "../../utils/format";
import {
  errorMessage,
  formatInteger,
  formatMoney,
  formatPrice,
  formatTime,
} from "./portfolioFormatters";

const { Text } = Typography;

interface PortfolioTablesProps {
  positions: PortfolioPosition[];
  stocks: PortfolioStockSummary[];
}

export default function PortfolioTables({ positions, stocks }: PortfolioTablesProps) {
  const navigate = useNavigate();
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const deleteMutation = useDeletePortfolioPosition();

  const handleDelete = async (positionId: number) => {
    try {
      await deleteMutation.mutateAsync(positionId);
      message.success("买入记录已删除");
    } catch (mutationError) {
      message.error(`删除失败：${errorMessage(mutationError)}`);
    }
  };

  const renderStock = (name: string, code: string) => (
    <Button
      type="link"
      onClick={() => navigate(`/analysis/${code}`)}
      style={{ height: "auto", padding: 0, textAlign: "left" }}
    >
      <span style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
        <span style={{ color: colors.textPrimary, fontWeight: 600 }}>{name || code}</span>
        <span style={{ color: colors.textMuted, fontSize: 12 }}>{code}</span>
      </span>
    </Button>
  );

  const renderProfit = (amount: number | null, percent: number | null) => {
    if (amount == null) return <Text style={{ color: colors.textMuted }}>待获取行情</Text>;
    return (
      <div style={{ whiteSpace: "nowrap" }}>
        <div style={{ color: changeColor(amount, colors), fontWeight: 600 }}>{formatMoney(amount)}</div>
        <ChangeValue value={percent} style={{ fontSize: 12 }} />
      </div>
    );
  };

  const stockColumns: TableColumnsType<PortfolioStockSummary> = [
    {
      title: "股票",
      key: "stock",
      width: 150,
      fixed: isMobile ? undefined : "left",
      render: (_, record) => renderStock(record.stock_name, record.stock_code),
    },
    {
      title: "买入批次",
      dataIndex: "position_count",
      width: 90,
      align: "right",
    },
    {
      title: "总股数",
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
      title: "浮动盈亏",
      key: "profit",
      width: 130,
      align: "right",
      render: (_, record) => renderProfit(record.profit_amount, record.profit_pct),
    },
  ];

  const positionColumns: TableColumnsType<PortfolioPosition> = [
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
      title: "买入价",
      dataIndex: "buy_price",
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
      title: "买入成本",
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
    {
      title: "操作",
      key: "action",
      width: 80,
      fixed: isMobile ? undefined : "right",
      render: (_, record) => (
        <Popconfirm
          title="删除这笔买入记录？"
          description="删除后将重新计算持仓汇总。"
          okText="删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
          onConfirm={() => handleDelete(record.id)}
        >
          <Button
            danger
            type="text"
            aria-label={`删除 ${record.stock_name} ${formatTime(record.buy_time)} 的买入记录`}
            icon={<DeleteOutlined />}
            loading={deleteMutation.isPending && deleteMutation.variables === record.id}
          />
        </Popconfirm>
      ),
    },
  ];

  return (
    <>
      <Card
        title="按股票汇总"
        size="small"
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: { padding: 0 } }}
      >
        <Table<PortfolioStockSummary>
          rowKey="stock_code"
          columns={stockColumns}
          dataSource={stocks}
          pagination={false}
          size="middle"
          scroll={{ x: 1_065 }}
          locale={{ emptyText: <Empty description="暂无持仓，先添加一笔买入记录" /> }}
        />
      </Card>

      <Card
        title="买入批次明细"
        size="small"
        style={cardStyle}
        styles={{ body: { padding: 0 } }}
      >
        <Table<PortfolioPosition>
          rowKey="id"
          columns={positionColumns}
          dataSource={positions}
          pagination={{ pageSize: 20, hideOnSinglePage: true, showSizeChanger: false }}
          size="middle"
          scroll={{ x: 945 }}
          locale={{ emptyText: <Empty description="暂无买入批次" /> }}
        />
      </Card>
    </>
  );
}
