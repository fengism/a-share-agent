import { Table, Tag, Spin, Empty } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import { useNavigate } from "react-router-dom";
import type { ScreenerFilter, ScreenerItem, ScreenerResult } from "../../types/stock";
import { useStyles } from "../../styles/ui";;

interface Props {
  data: ScreenerResult | undefined;
  isLoading: boolean;
  percentileMap: Map<string, number | null>;
  showPercentile: boolean;
  onPageChange: (page: number, pageSize: number) => void;
  filters: ScreenerFilter;
  onSortChange: (sortBy: ScreenerFilter["sort_by"], sortOrder: ScreenerFilter["sort_order"]) => void;
}

type SortableKey = "price" | "change_pct" | "pe" | "pb" | "market_cap" | "turnover_pct" | "volume";

const SORT_FIELD_MAP: Record<string, SortableKey> = {
  price: "price",
  change_pct: "change_pct",
  pe_ttm: "pe",
  pb: "pb",
  market_cap: "market_cap",
  turnover_pct: "turnover_pct",
  volume: "volume",
};

export default function ResultsTable({
  data, isLoading, percentileMap, showPercentile, onPageChange, filters, onSortChange,
}: Props) {
  const { tagStyle } = useStyles();
  const navigate = useNavigate();
  const currentSortOrder = filters.sort_order === "asc" ? "ascend" : "descend";

  const handleTableChange: TableProps<ScreenerItem>["onChange"] = (pagination, _tableFilters, sorter) => {
    const sorterConfig = Array.isArray(sorter) ? sorter[0] : sorter;
    const field = typeof sorterConfig?.field === "string" ? SORT_FIELD_MAP[sorterConfig.field] : undefined;
    const order = sorterConfig?.order;

    if (field && order) {
      onSortChange(field, order === "ascend" ? "asc" : "desc");
      return;
    }

    const page = pagination.current ?? data?.page ?? 1;
    const pageSize = pagination.pageSize ?? data?.page_size ?? 50;
    onPageChange(page, pageSize);
  };

  const columns: ColumnsType<ScreenerItem & { pe_percentile?: number | null; pb_percentile?: number | null }> = [
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      render: (code: string) => (
        <a onClick={() => navigate(`/analysis/${code}`)} style={{ color: "#3b82f6", fontWeight: 500 }}>{code}</a>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      width: 100,
      ellipsis: true,
    },
    {
      title: "价格",
      dataIndex: "price",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "price" ? currentSortOrder : null,
      render: (v: number | null) => v?.toFixed(2) ?? "-",
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "change_pct" ? currentSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        const color = v > 0 ? "#ef4444" : v < 0 ? "#22c55e" : "#9ca3af";
        return <span style={{ color, fontWeight: 500 }}>{v > 0 ? "+" : ""}{v.toFixed(2)}%</span>;
      },
    },
    {
      title: "PE(TTM)",
      dataIndex: "pe_ttm",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "pe" ? currentSortOrder : null,
      render: (v: number | null) => v?.toFixed(1) ?? "-",
    },
    {
      title: "PB",
      dataIndex: "pb",
      width: 70,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "pb" ? currentSortOrder : null,
      render: (v: number | null) => v?.toFixed(2) ?? "-",
    },
    {
      title: "市值(亿)",
      dataIndex: "market_cap",
      width: 90,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "market_cap" ? currentSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        if (v >= 10000) return `${(v / 10000).toFixed(1)}万`;
        return v.toFixed(1);
      },
    },
    {
      title: "换手率",
      dataIndex: "turnover_pct",
      width: 70,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "turnover_pct" ? currentSortOrder : null,
      render: (v: number | null) => v != null ? `${v.toFixed(2)}%` : "-",
    },
    {
      title: "成交量",
      dataIndex: "volume",
      width: 90,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "volume" ? currentSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        if (v >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
        if (v >= 1e4) return `${(v / 1e4).toFixed(1)}万`;
        return v.toFixed(0);
      },
    },
    {
      title: "二级行业",
      dataIndex: "second_industry",
      width: 100,
      ellipsis: true,
      render: (v: ScreenerItem["second_industry"]) => v?.name ? <Tag style={{ ...tagStyle, fontSize: 11 }}>{v.name}</Tag> : "-",
    },
  ];

  if (showPercentile) {
    columns.push(
      {
        title: "PE分位",
        key: "pe_percentile",
        width: 75,
        align: "right",
        render: (_: unknown, record: ScreenerItem) => {
          const p = percentileMap.get(record.code);
          if (p == null) return <Spin size="small" />;
          const color = p <= 30 ? "#22c55e" : p <= 70 ? "#eab308" : "#ef4444";
          return <span style={{ color, fontWeight: 500 }}>{p.toFixed(0)}%</span>;
        },
      },
      {
        title: "PB分位",
        key: "pb_percentile",
        width: 75,
        align: "right",
        render: (_: unknown, record: ScreenerItem) => {
          const p = percentileMap.get(record.code + "_pb");
          if (p == null) return <Spin size="small" />;
          const color = p <= 30 ? "#22c55e" : p <= 70 ? "#eab308" : "#ef4444";
          return <span style={{ color, fontWeight: 500 }}>{p.toFixed(0)}%</span>;
        },
      },
    );
  }

  return (
    <Table
      columns={columns}
      dataSource={data?.items || []}
      rowKey={(record) => `${record.code}-${record.name}`}
      loading={isLoading}
      size="small"
      pagination={{
        current: data?.page || 1,
        pageSize: data?.page_size || 50,
        total: data?.total || 0,
        showSizeChanger: true,
        pageSizeOptions: ["20", "50", "100"],
        showTotal: (total) => `共 ${total} 只`,
        onChange: (page, pageSize) => onPageChange(page, pageSize),
      }}
      onChange={handleTableChange}
      locale={{ emptyText: <Empty description="无匹配股票，请调整筛选条件" /> }}
      scroll={{ x: "max-content" }}
    />
  );
}
