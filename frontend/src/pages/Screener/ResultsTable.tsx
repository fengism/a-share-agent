import { useCallback, useMemo } from "react";
import { Table, Tag, Spin, Empty } from "antd";
import type { ColumnsType, TableProps } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import PreloadLink from "../../components/PreloadLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { ScreenerFilter, ScreenerItem, ScreenerResult } from "../../types/stock";
import { useColors } from "../../styles/ui";

interface Props {
  data: ScreenerResult | undefined;
  isLoading: boolean;
  percentileMap: Map<string, number | null>;
  showPercentile: boolean;
  onPageChange: (page: number, pageSize: number) => void;
  filters: ScreenerFilter;
  onSortChange: (sortBy: ScreenerFilter["sort_by"], sortOrder: ScreenerFilter["sort_order"]) => void;
  selectedCodes: string[];
  onSelectedCodesChange: (codes: string[]) => void;
  strategySignalDates?: ReadonlyMap<string, string>;
  strategyDataSources?: ReadonlyMap<string, string>;
  strategyFallbackCodes?: ReadonlySet<string>;
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
  data,
  isLoading,
  percentileMap,
  showPercentile,
  onPageChange,
  filters,
  onSortChange,
  selectedCodes,
  onSelectedCodesChange,
  strategySignalDates,
  strategyDataSources,
  strategyFallbackCodes,
}: Props) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const currentSortOrder = filters.sort_order === "asc" ? "ascend" : "descend";

  const handleTableChange = useCallback<NonNullable<TableProps<ScreenerItem>["onChange"]>>((pagination, _tableFilters, sorter) => {
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
  }, [data?.page, data?.page_size, onPageChange, onSortChange]);

  const columns: ColumnsType<ScreenerItem & { pe_percentile?: number | null; pb_percentile?: number | null }> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "股票",
          key: "stock",
          width: 132,
          render: (_: unknown, record: ScreenerItem) => (
            <PreloadLink to={`/analysis/${encodeURIComponent(record.code)}`} style={{ display: "block", color: c.primary }}>
              <span style={{ display: "block", color: c.textPrimary, fontWeight: 600 }}>{record.name}</span>
              <span style={{ display: "block", color: c.textMuted, fontSize: 11 }}>
                {record.code}{record.board || record.exchange ? ` · ${record.board || record.exchange}` : ""}
              </span>
            </PreloadLink>
          ),
        },
        {
          title: "价格",
          dataIndex: "price",
          width: 72,
          align: "right",
          sorter: true,
          sortOrder: filters.sort_by === "price" ? currentSortOrder : null,
          render: (value: number | null) => value?.toFixed(2) ?? "-",
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          sorter: true,
          sortOrder: filters.sort_by === "change_pct" ? currentSortOrder : null,
          render: (value: number | null) => <ChangeValue value={value} />,
        },
      ];
    }

    const nextColumns: ColumnsType<ScreenerItem & { pe_percentile?: number | null; pb_percentile?: number | null }> = [
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      render: (code: string) => (
        <PreloadLink to={`/analysis/${encodeURIComponent(code)}`} style={{ color: c.primary, fontWeight: 500 }}>{code}</PreloadLink>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      width: 100,
      ellipsis: true,
    },
    {
      title: "市场",
      key: "exchange_market",
      width: 90,
      ellipsis: true,
      render: (_: unknown, record: ScreenerItem) => record.board || record.exchange || "-",
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
      render: (value: number | null) => <ChangeValue value={value} fontWeight={500} />,
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
      title: "申万二级",
      dataIndex: "second_industry",
      width: 100,
      ellipsis: true,
      render: (value: ScreenerItem["second_industry"]) => value?.name || "-",
    },
    {
      title: "交易所行业",
      dataIndex: "exchange_industry",
      width: 120,
      ellipsis: true,
      render: (value: string | null | undefined) => value || "-",
    },
    ];

    if (strategySignalDates?.size) {
      nextColumns.splice(2, 0, {
        title: "信号日",
        key: "strategy_signal_date",
        width: 100,
        render: (_: unknown, record: ScreenerItem) => strategySignalDates.get(record.code) ?? "-",
      });
      nextColumns.splice(3, 0, {
        title: "K线源",
        key: "strategy_data_source",
        width: 150,
        render: (_: unknown, record: ScreenerItem) => {
          const source = strategyDataSources?.get(record.code) || "-";
          return <Tag color={strategyFallbackCodes?.has(record.code) ? "warning" : undefined}>{source}</Tag>;
        },
      });
    }

    if (showPercentile) {
      nextColumns.push(
        {
          title: "PE分位",
          key: "pe_percentile",
          width: 75,
          align: "right",
          render: (_: unknown, record: ScreenerItem) => {
            const p = percentileMap.get(record.code);
            if (p == null) return <Spin size="small" />;
            const color = p <= 30 ? c.down : p <= 70 ? c.warning : c.up;
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
            const color = p <= 30 ? c.down : p <= 70 ? c.warning : c.up;
            return <span style={{ color, fontWeight: 500 }}>{p.toFixed(0)}%</span>;
          },
        },
      );
    }
    return nextColumns;
  }, [c, currentSortOrder, filters.sort_by, isNarrow, percentileMap, showPercentile, strategyDataSources, strategyFallbackCodes, strategySignalDates]);

  const renderExpandedRow = useCallback((record: ScreenerItem) => {
    const pePercentile = percentileMap.get(record.code);
    const pbPercentile = percentileMap.get(`${record.code}_pb`);
    return (
      <ResponsiveMetricGrid
        items={[
          { key: "pe", label: "PE(TTM)", value: record.pe_ttm?.toFixed(1) ?? "-" },
          { key: "pb", label: "PB", value: record.pb?.toFixed(2) ?? "-" },
          {
            key: "market-cap",
            label: "市值(亿)",
            value: record.market_cap == null
              ? "-"
              : record.market_cap >= 10000
                ? `${(record.market_cap / 10000).toFixed(1)}万`
                : record.market_cap.toFixed(1),
          },
          { key: "turnover", label: "换手率", value: record.turnover_pct == null ? "-" : `${record.turnover_pct.toFixed(2)}%` },
          {
            key: "volume",
            label: "成交量",
            value: record.volume == null
              ? "-"
              : record.volume >= 1e8
                ? `${(record.volume / 1e8).toFixed(2)}亿`
                : record.volume >= 1e4
                  ? `${(record.volume / 1e4).toFixed(1)}万`
                  : record.volume.toFixed(0),
          },
          { key: "market", label: "所属市场", value: record.board || record.exchange || "-" },
          { key: "listing-date", label: "上市日期", value: record.listing_date ?? "-" },
          { key: "sw-industry", label: "申万二级", value: record.second_industry?.name ?? "-" },
          { key: "exchange-industry", label: "交易所行业", value: record.exchange_industry ?? "-" },
          ...(strategySignalDates?.size ? [{
            key: "strategy-signal-date",
            label: "策略信号日",
            value: strategySignalDates.get(record.code) ?? "-",
          }] : []),
          ...(strategyDataSources?.size ? [{
            key: "strategy-data-source",
            label: "K线源",
            value: `${strategyDataSources.get(record.code) ?? "-"}${strategyFallbackCodes?.has(record.code) ? "（fallback）" : ""}`,
          }] : []),
          ...(showPercentile ? [
            { key: "pe-percentile", label: "PE分位", value: pePercentile == null ? "计算中" : `${pePercentile.toFixed(0)}%` },
            { key: "pb-percentile", label: "PB分位", value: pbPercentile == null ? "计算中" : `${pbPercentile.toFixed(0)}%` },
          ] : []),
        ]}
      />
    );
  }, [percentileMap, showPercentile, strategyDataSources, strategyFallbackCodes, strategySignalDates]);

  return (
    <Table
      columns={columns}
      dataSource={data?.items || []}
      rowKey="code"
      rowSelection={{
        selectedRowKeys: selectedCodes,
        preserveSelectedRowKeys: true,
        onChange: (keys) => onSelectedCodesChange(keys.map(String).slice(0, 10)),
        getCheckboxProps: (record) => ({
          disabled: selectedCodes.length >= 10 && !selectedCodes.includes(record.code),
        }),
      }}
      loading={isLoading}
      size="small"
      pagination={{
        current: data?.page || 1,
        pageSize: data?.page_size || 50,
        total: data?.total || 0,
        showSizeChanger: !isNarrow,
        showLessItems: isNarrow,
        responsive: true,
        pageSizeOptions: ["20", "50", "100"],
        showTotal: (total) => `共 ${total} 只`,
        onChange: (page, pageSize) => onPageChange(page, pageSize),
      }}
      onChange={handleTableChange}
      expandable={isNarrow ? {
        expandedRowRender: renderExpandedRow,
        columnWidth: 38,
      } : undefined}
      locale={{ emptyText: <Empty description="无匹配股票，请调整筛选条件" /> }}
      scroll={isNarrow ? undefined : { x: "max-content" }}
    />
  );
}
