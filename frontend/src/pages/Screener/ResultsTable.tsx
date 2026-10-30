import { useCallback, useEffect, useMemo, useState } from "react";
import { Table, Tag, Spin, Empty, Tooltip, Space, Button, message } from "antd";
import { PlusOutlined, RobotOutlined, LineChartOutlined, CheckOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import type { ColumnsType, TableProps } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import PreloadLink from "../../components/PreloadLink";
import { buildStockProfileUrl } from "../../utils/stockLinks";
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
  onAddWatchlist?: (stock: ScreenerItem) => Promise<void> | void;
  strategySignalDates?: ReadonlyMap<string, string>;
  strategySignalAges?: ReadonlyMap<string, number>;
  strategyReturnsSinceSignal?: ReadonlyMap<string, number | null>;
  strategyAverageAmounts?: ReadonlyMap<string, number | null>;
  strategyDataSources?: ReadonlyMap<string, string>;
  strategyFallbackCodes?: ReadonlySet<string>;
}

type SortableKey = "price" | "change_pct" | "pe" | "pb" | "market_cap" | "turnover_pct" | "volume" | "amplitude" | "volume_ratio" | "change_pct_60d" | "composite_score";
type LocalStrategySortKey = "strategy_signal_age" | "strategy_return_since_signal" | "strategy_average_amount_20d";

const SORT_FIELD_MAP: Record<string, SortableKey> = {
  price: "price",
  change_pct: "change_pct",
  pe_ttm: "pe",
  pb: "pb",
  market_cap: "market_cap",
  turnover_pct: "turnover_pct",
  volume: "volume",
  amplitude: "amplitude",
  volume_ratio: "volume_ratio",
  change_pct_60d: "change_pct_60d",
  composite_score: "composite_score",
};

const LOCAL_STRATEGY_SORT_KEYS = new Set<LocalStrategySortKey>([
  "strategy_signal_age",
  "strategy_return_since_signal",
  "strategy_average_amount_20d",
]);

function isLocalStrategySortKey(value: string): value is LocalStrategySortKey {
  return LOCAL_STRATEGY_SORT_KEYS.has(value as LocalStrategySortKey);
}

function compareOptionalNumbers(
  left: number | null | undefined,
  right: number | null | undefined,
  order: "ascend" | "descend",
) {
  if (left == null) return right == null ? 0 : 1;
  if (right == null) return -1;
  return order === "ascend" ? left - right : right - left;
}

function renderStockBadges(record: ScreenerItem) {
  const badges = [];
  if (record.change_pct != null && record.change_pct >= 9.8) {
    badges.push(
      <span
        key="limit-up"
        style={{
          fontSize: 10,
          lineHeight: "14px",
          padding: "0 3px",
          borderRadius: 2,
          backgroundColor: "rgba(245, 34, 45, 0.15)",
          color: "#f5222d",
          fontWeight: 600,
        }}
      >
        涨停
      </span>,
    );
  } else if (record.change_pct != null && record.change_pct <= -9.8) {
    badges.push(
      <span
        key="limit-down"
        style={{
          fontSize: 10,
          lineHeight: "14px",
          padding: "0 3px",
          borderRadius: 2,
          backgroundColor: "rgba(82, 196, 26, 0.15)",
          color: "#52c41a",
          fontWeight: 600,
        }}
      >
        跌停
      </span>,
    );
  }

  if (record.turnover_pct != null && record.turnover_pct >= 8) {
    badges.push(
      <span
        key="high-turnover"
        style={{
          fontSize: 10,
          lineHeight: "14px",
          padding: "0 3px",
          borderRadius: 2,
          backgroundColor: "rgba(250, 140, 22, 0.15)",
          color: "#fa8c16",
          fontWeight: 600,
        }}
      >
        高换手
      </span>,
    );
  }

  if (record.volume_ratio != null && record.volume_ratio >= 2.0) {
    badges.push(
      <span
        key="high-vol-ratio"
        style={{
          fontSize: 10,
          lineHeight: "14px",
          padding: "0 3px",
          borderRadius: 2,
          backgroundColor: "rgba(114, 46, 209, 0.15)",
          color: "#722ed1",
          fontWeight: 600,
        }}
      >
        放量
      </span>,
    );
  }

  return badges.length > 0 ? (
    <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }}>
      {badges}
    </span>
  ) : null;
}

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
  onAddWatchlist,
  strategySignalDates,
  strategySignalAges,
  strategyReturnsSinceSignal,
  strategyAverageAmounts,
  strategyDataSources,
  strategyFallbackCodes,
}: Props) {
  const c = useColors();
  const navigate = useNavigate();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [addedCodes, setAddedCodes] = useState<Set<string>>(new Set());

  const handleAddWatchlist = useCallback(async (record: ScreenerItem) => {
    try {
      if (onAddWatchlist) {
        await onAddWatchlist(record);
      }
      setAddedCodes((prev) => new Set(prev).add(record.code));
    } catch {
      message.error(`添加 ${record.name} 到自选失败`);
    }
  }, [onAddWatchlist]);

  const handleAiDiagnose = useCallback((record: ScreenerItem) => {
    const prompt = `请对股票 ${record.name}（代码：${record.code}）进行深度量化与基本面体检，评估其估值水平（当前 PE: ${record.pe_ttm ?? "未知"}，PB: ${record.pb ?? "未知"}）、行业竞争壁垒、技术走势及潜在投资风险。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  }, [navigate]);
  const currentSortOrder = filters.sort_order === "asc" ? "ascend" : "descend";
  const [columnPerspective, setColumnPerspective] = useState<"all" | "valuation" | "momentum">("all");
  const [localSort, setLocalSort] = useState<{
    key: LocalStrategySortKey;
    order: "ascend" | "descend";
  }>();
  const serverSortOrder = localSort ? null : currentSortOrder;

  useEffect(() => {
    if (!strategySignalDates?.size) {
      setLocalSort(undefined);
    }
  }, [strategySignalDates]);

  const handleTableChange = useCallback<NonNullable<TableProps<ScreenerItem>["onChange"]>>((pagination, _tableFilters, sorter, extra) => {
    const sorterConfig = Array.isArray(sorter) ? sorter[0] : sorter;
    const columnKey = typeof sorterConfig?.columnKey === "string" ? sorterConfig.columnKey : undefined;
    const order = sorterConfig?.order;
    if (extra.action === "sort" && columnKey && isLocalStrategySortKey(columnKey)) {
      setLocalSort(order ? { key: columnKey, order } : undefined);
      return;
    }

    const field = typeof sorterConfig?.field === "string" ? SORT_FIELD_MAP[sorterConfig.field] : undefined;

    if (field && order) {
      setLocalSort(undefined);
      onSortChange(field, order === "ascend" ? "asc" : "desc");
      return;
    }

    const page = pagination.current ?? data?.page ?? 1;
    const pageSize = pagination.pageSize ?? data?.page_size ?? 50;
    onPageChange(page, pageSize);
  }, [data?.page, data?.page_size, onPageChange, onSortChange]);

  const columns: ColumnsType<ScreenerItem & { pe_percentile?: number | null; pb_percentile?: number | null }> = useMemo(() => {
    if (isNarrow) {
      const hasStrategyResult = Boolean(strategySignalDates?.size);
      return [
        {
          title: "股票",
          key: "stock",
          width: 140,
          render: (_: unknown, record: ScreenerItem) => (
            <PreloadLink to={buildStockProfileUrl(record.code)} style={{ display: "block", color: c.primary }}>
              <span style={{ display: "block", color: c.textPrimary, fontWeight: "var(--c-weight-semibold)" }}>{record.name}</span>
              <span style={{ display: "flex", alignItems: "center", gap: 4, color: c.textMuted, fontSize: "var(--c-font-xs)", flexWrap: "wrap", marginTop: 2 }}>
                <span>{record.code}{record.board || record.exchange ? ` · ${record.board || record.exchange}` : ""}</span>
                {renderStockBadges(record)}
                {record.composite_score != null ? (
                  <Tag
                    color={record.composite_score >= 80 ? "gold" : record.composite_score >= 65 ? "blue" : undefined}
                    style={{ fontSize: 10, lineHeight: "14px", padding: "0 3px", margin: 0, fontWeight: 600 }}
                  >
                    {record.composite_score.toFixed(0)}分
                  </Tag>
                ) : null}
                {record.is_broken_net ? (
                  <span
                    style={{
                      fontSize: "var(--c-font-xs, 11px)",
                      lineHeight: "14px",
                      padding: "0 3px",
                      borderRadius: 2,
                      backgroundColor: "rgba(24, 144, 255, 0.12)",
                      color: "#1890ff",
                      fontWeight: 600,
                    }}
                  >
                    破净
                  </span>
                ) : null}
              </span>
            </PreloadLink>
          ),
        },
        hasStrategyResult
          ? {
              title: "信号年龄",
              key: "strategy_signal_age",
              width: 82,
              align: "right",
              sorter: true,
              sortOrder: localSort?.key === "strategy_signal_age" ? localSort.order : null,
              render: (_: unknown, record: ScreenerItem) => {
                const age = strategySignalAges?.get(record.code);
                return age == null ? "-" : `${age} 根`;
              },
            }
          : {
              title: "价格",
              dataIndex: "price",
              width: 72,
              align: "right",
              sorter: true,
              sortOrder: filters.sort_by === "price" ? serverSortOrder : null,
              render: (value: number | null) => value?.toFixed(2) ?? "-",
            },
        hasStrategyResult
          ? {
              title: "信号收益",
              key: "strategy_return_since_signal",
              width: 88,
              align: "right",
              sorter: true,
              sortOrder: localSort?.key === "strategy_return_since_signal" ? localSort.order : null,
              render: (_: unknown, record: ScreenerItem) => (
                <ChangeValue value={strategyReturnsSinceSignal?.get(record.code)} />
              ),
            }
          : {
              title: "涨跌幅",
              dataIndex: "change_pct",
              width: 82,
              align: "right",
              sorter: true,
              sortOrder: filters.sort_by === "change_pct" ? serverSortOrder : null,
              render: (value: number | null) => <ChangeValue value={value} />,
            },
      ];
    }

    const nextColumns: ColumnsType<ScreenerItem & { pe_percentile?: number | null; pb_percentile?: number | null }> = [
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      fixed: "left",
      render: (code: string) => (
        <PreloadLink className="financial-num" to={buildStockProfileUrl(code)} style={{ color: c.primary, fontWeight: "var(--c-weight-medium)" }}>{code}</PreloadLink>
      ),
    },
    {
      title: "名称",
      dataIndex: "name",
      width: 120,
      ellipsis: true,
      fixed: "left",
      render: (name: string, record: ScreenerItem) => (
        <span style={{ display: "inline-flex", flexDirection: "column", gap: 2 }}>
          <span>{name}</span>
          {renderStockBadges(record)}
        </span>
      ),
    },
    {
      title: "市场",
      key: "exchange_market",
      width: 90,
      ellipsis: true,
      render: (_: unknown, record: ScreenerItem) => record.board || record.exchange || "-",
    },
    {
      title: "综合评分",
      dataIndex: "composite_score",
      width: 88,
      align: "center",
      sorter: true,
      sortOrder: filters.sort_by === "composite_score" ? serverSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        const color = v >= 80 ? "gold" : v >= 65 ? "blue" : undefined;
        return (
          <Tag color={color} style={{ fontWeight: 600, minWidth: 42, textAlign: "center", margin: 0 }}>
            {v.toFixed(1)}
          </Tag>
        );
      },
    },
    {
      title: "价格",
      dataIndex: "price",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "price" ? serverSortOrder : null,
      render: (v: number | null) => <span className="financial-num">{v?.toFixed(2) ?? "-"}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "change_pct" ? serverSortOrder : null,
      render: (value: number | null) => <ChangeValue value={value} fontWeight={500} />,
    },
    {
      title: "PE(TTM)",
      dataIndex: "pe_ttm",
      width: 80,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "pe" ? serverSortOrder : null,
      render: (v: number | null) => <span className="financial-num">{v?.toFixed(1) ?? "-"}</span>,
    },
    {
      title: "PB",
      dataIndex: "pb",
      width: 78,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "pb" ? serverSortOrder : null,
      render: (v: number | null, record: ScreenerItem) => (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 3, justifyContent: "flex-end", width: "100%" }}>
          {record.is_broken_net && (
            <span
              style={{
                fontSize: "var(--c-font-xs, 11px)",
                lineHeight: "14px",
                padding: "0 3px",
                borderRadius: 2,
                backgroundColor: "rgba(24, 144, 255, 0.12)",
                color: "#1890ff",
                fontWeight: 600,
              }}
              title="破净标的 (PB <= 1.0)"
            >
              破净
            </span>
          )}
          <span className="financial-num">{v?.toFixed(2) ?? "-"}</span>
        </span>
      ),
    },
    {
      title: "振幅",
      dataIndex: "amplitude",
      width: 75,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "amplitude" ? serverSortOrder : null,
      render: (v: number | null) => (v != null ? <span className="financial-num">{v.toFixed(2)}%</span> : "-"),
    },
    {
      title: "市值(亿)",
      dataIndex: "market_cap",
      width: 90,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "market_cap" ? serverSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        if (v >= 10000) return <span className="financial-num">{(v / 10000).toFixed(1)}万</span>;
        return <span className="financial-num">{v.toFixed(1)}</span>;
      },
    },
    {
      title: "换手率",
      dataIndex: "turnover_pct",
      width: 70,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "turnover_pct" ? serverSortOrder : null,
      render: (v: number | null) => v != null ? <span className="financial-num">{v.toFixed(2)}%</span> : "-",
    },
    {
      title: "量比",
      dataIndex: "volume_ratio",
      width: 75,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "volume_ratio" ? serverSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        const isHighlight = v >= 1.8;
        return (
          <span
            className="financial-num"
            style={isHighlight ? { color: c.up, fontWeight: "var(--c-weight-semibold)" } : undefined}
          >
            {v.toFixed(2)}
          </span>
        );
      },
    },
    {
      title: "60日涨幅",
      dataIndex: "change_pct_60d",
      width: 85,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "change_pct_60d" ? serverSortOrder : null,
      render: (value: number | null) => (value != null ? <ChangeValue value={value} fontWeight={500} /> : "-"),
    },
    {
      title: "成交量",
      dataIndex: "volume",
      width: 90,
      align: "right",
      sorter: true,
      sortOrder: filters.sort_by === "volume" ? serverSortOrder : null,
      render: (v: number | null) => {
        if (v == null) return "-";
        if (v >= 1e8) return <span className="financial-num">{(v / 1e8).toFixed(2)}亿</span>;
        if (v >= 1e4) return <span className="financial-num">{(v / 1e4).toFixed(1)}万</span>;
        return <span className="financial-num">{v.toFixed(0)}</span>;
      },
    },
    {
      title: "申万二级",
      dataIndex: "second_industry",
      width: 100,
      ellipsis: true,
      render: (value: ScreenerItem["second_industry"], record: ScreenerItem) => {
        const fullHierarchy = [
          record.first_industry?.name,
          record.second_industry?.name,
          record.third_industry?.name,
        ].filter(Boolean).join(" / ");
        const display = value?.name || record.first_industry?.name || "-";
        return fullHierarchy ? (
          <Tooltip title={`申万行业: ${fullHierarchy}`}>
            <span>{display}</span>
          </Tooltip>
        ) : (
          display
        );
      },
    },
    {
      title: "概念题材",
      dataIndex: "concepts",
      width: 160,
      ellipsis: true,
      render: (concepts: string[] | undefined) => {
        if (!concepts || concepts.length === 0) return "-";
        return (
          <Tooltip title={concepts.join(" · ")}>
            <span>
              {concepts.slice(0, 2).map((c) => (
                <Tag key={c} style={{ marginRight: 4, marginBottom: 2 }}>{c}</Tag>
              ))}
              {concepts.length > 2 && <Tag>+{concepts.length - 2}</Tag>}
            </span>
          </Tooltip>
        );
      },
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
        render: (_: unknown, record: ScreenerItem) => (
          <span className="financial-num">{strategySignalDates.get(record.code) ?? "-"}</span>
        ),
      });
      nextColumns.splice(3, 0, {
        title: "信号年龄",
        key: "strategy_signal_age",
        width: 90,
        align: "right",
        sorter: true,
        sortOrder: localSort?.key === "strategy_signal_age" ? localSort.order : null,
        render: (_: unknown, record: ScreenerItem) => {
          const age = strategySignalAges?.get(record.code);
          return age == null ? "-" : <span className="financial-num">{`${age} 根`}</span>;
        },
      });
      nextColumns.splice(4, 0, {
        title: "信号后收益",
        key: "strategy_return_since_signal",
        width: 110,
        align: "right",
        sorter: true,
        sortOrder: localSort?.key === "strategy_return_since_signal" ? localSort.order : null,
        render: (_: unknown, record: ScreenerItem) => (
          <ChangeValue value={strategyReturnsSinceSignal?.get(record.code)} fontWeight={500} />
        ),
      });
      nextColumns.splice(5, 0, {
        title: "20日均成交额（亿）",
        key: "strategy_average_amount_20d",
        width: 110,
        align: "right",
        sorter: true,
        sortOrder: localSort?.key === "strategy_average_amount_20d" ? localSort.order : null,
        render: (_: unknown, record: ScreenerItem) => {
          const val = strategyAverageAmounts?.get(record.code);
          return val == null ? "-" : <span className="financial-num">{val.toFixed(2)}</span>;
        },
      });
      nextColumns.splice(6, 0, {
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
            return <span style={{ color, fontWeight: "var(--c-weight-medium)" }}>{p.toFixed(0)}%</span>;
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
            return <span style={{ color, fontWeight: "var(--c-weight-medium)" }}>{p.toFixed(0)}%</span>;
          },
        },
      );
    }

    nextColumns.push({
      title: "操作",
      key: "actions",
      width: 110,
      fixed: "right",
      render: (_: unknown, record: ScreenerItem) => {
        const isAdded = addedCodes.has(record.code);
        return (
          <Space size={2}>
            <Tooltip title={isAdded ? "已加自选" : "加入自选"}>
              <Button
                type="text"
                size="small"
                aria-label={`加自选-${record.code}`}
                icon={isAdded ? <CheckOutlined style={{ color: "#52c41a" }} /> : <PlusOutlined />}
                disabled={isAdded}
                onClick={() => void handleAddWatchlist(record)}
              />
            </Tooltip>
            <Tooltip title="AI 深度体检">
              <Button
                type="text"
                size="small"
                aria-label={`AI体检-${record.code}`}
                icon={<RobotOutlined style={{ color: c.primary }} />}
                onClick={() => handleAiDiagnose(record)}
              />
            </Tooltip>
            <Tooltip title="详情分析">
              <Button
                type="text"
                size="small"
                aria-label={`详情-${record.code}`}
                icon={<LineChartOutlined />}
                onClick={() => navigate(buildStockProfileUrl(record.code))}
              />
            </Tooltip>
          </Space>
        );
      },
    });

    if (columnPerspective === "valuation") {
      const allowed = new Set([
        "code", "name", "composite_score", "price", "change_pct", "pe_ttm", "pb", "market_cap",
        "second_industry", "concepts", "actions", "strategy_signal_date", "strategy_signal_age",
        "strategy_return_since_signal", "strategy_average_amount_20d", "strategy_data_source",
        "pe_percentile", "pb_percentile",
      ]);
      return nextColumns.filter((col) => {
        const key = (col.key || (col as { dataIndex?: string }).dataIndex) as string;
        return !key || allowed.has(key);
      });
    }

    if (columnPerspective === "momentum") {
      const allowed = new Set([
        "code", "name", "price", "change_pct", "amplitude", "market_cap", "turnover_pct", "volume_ratio",
        "change_pct_60d", "volume", "actions", "strategy_signal_date", "strategy_signal_age",
        "strategy_return_since_signal", "strategy_average_amount_20d", "strategy_data_source",
      ]);
      return nextColumns.filter((col) => {
        const key = (col.key || (col as { dataIndex?: string }).dataIndex) as string;
        return !key || allowed.has(key);
      });
    }

    return nextColumns;
  }, [addedCodes, c, columnPerspective, filters.sort_by, handleAddWatchlist, handleAiDiagnose, isNarrow, localSort, navigate, percentileMap, serverSortOrder, showPercentile, strategyAverageAmounts, strategyDataSources, strategyFallbackCodes, strategyReturnsSinceSignal, strategySignalAges, strategySignalDates]);

  const displayedItems = useMemo(() => {
    const items = data?.items ?? [];
    if (!localSort) return items;
    const values = localSort.key === "strategy_signal_age"
      ? strategySignalAges
      : localSort.key === "strategy_return_since_signal"
        ? strategyReturnsSinceSignal
        : strategyAverageAmounts;
    return [...items].sort((left, right) => compareOptionalNumbers(
      values?.get(left.code),
      values?.get(right.code),
      localSort.order,
    ));
  }, [data?.items, localSort, strategyAverageAmounts, strategyReturnsSinceSignal, strategySignalAges]);

  const renderExpandedRow = useCallback((record: ScreenerItem) => {
    const pePercentile = percentileMap.get(record.code);
    const pbPercentile = percentileMap.get(`${record.code}_pb`);
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        <ResponsiveMetricGrid
          items={[
          ...(record.composite_score != null ? [{ key: "composite-score", label: "综合评分", value: `${record.composite_score.toFixed(1)} 分` }] : []),
          { key: "pe", label: "PE(TTM)", value: record.pe_ttm?.toFixed(1) ?? "-" },
          { key: "pb", label: "PB", value: record.pb?.toFixed(2) ?? "-" },
          { key: "amplitude", label: "日内振幅", value: record.amplitude != null ? `${record.amplitude.toFixed(2)}%` : "-" },
          { key: "volume-ratio", label: "量比", value: record.volume_ratio != null ? record.volume_ratio.toFixed(2) : "-" },
          { key: "change-60d", label: "60日涨幅", value: record.change_pct_60d != null ? <ChangeValue value={record.change_pct_60d} fontWeight={500} /> : "-" },
          ...(record.is_broken_net ? [{ key: "broken-net", label: "破净状态", value: "破净标的 (PB ≤ 1.0)" }] : []),
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
          { key: "sw-industry", label: "申万二级", value: [record.first_industry?.name, record.second_industry?.name, record.third_industry?.name].filter(Boolean).join(" / ") || (record.second_industry?.name ?? record.first_industry?.name ?? "-") },
          ...(record.concepts && record.concepts.length > 0 ? [{
            key: "concepts",
            label: "概念题材",
            value: record.concepts.slice(0, 4).join(" · ") + (record.concepts.length > 4 ? ` (+${record.concepts.length - 4})` : ""),
          }] : []),
          { key: "exchange-industry", label: "交易所行业", value: record.exchange_industry ?? "-" },
          ...(strategySignalDates?.size ? [{
            key: "strategy-signal-date",
            label: "策略信号日",
            value: strategySignalDates.get(record.code) ?? "-",
          }] : []),
          ...(strategySignalAges?.size ? [{
            key: "strategy-signal-age",
            label: "信号年龄",
            value: strategySignalAges.get(record.code) == null
              ? "-"
              : `${strategySignalAges.get(record.code)} 根`,
          }] : []),
          ...(strategyReturnsSinceSignal?.size ? [{
            key: "strategy-return-since-signal",
            label: "信号后收益",
            value: <ChangeValue value={strategyReturnsSinceSignal.get(record.code)} fontWeight={500} />,
          }] : []),
          ...(strategyAverageAmounts?.size ? [{
            key: "strategy-average-amount-20d",
            label: "20日均成交额（亿）",
            value: strategyAverageAmounts.get(record.code)?.toFixed(2) ?? "-",
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
      <div style={{ marginTop: 8, display: "flex", gap: 8, flexWrap: "wrap", borderTop: "1px dashed var(--c-border)", paddingTop: 8 }}>
        <Button
          size="small"
          icon={addedCodes.has(record.code) ? <CheckOutlined style={{ color: "#52c41a" }} /> : <PlusOutlined />}
          disabled={addedCodes.has(record.code)}
          onClick={() => void handleAddWatchlist(record)}
        >
          {addedCodes.has(record.code) ? "已加自选" : "加自选"}
        </Button>
        <Button
          size="small"
          type="primary"
          ghost
          icon={<RobotOutlined />}
          onClick={() => handleAiDiagnose(record)}
        >
          AI 深度体检
        </Button>
        <Button
          size="small"
          icon={<LineChartOutlined />}
          onClick={() => navigate(buildStockProfileUrl(record.code))}
        >
          详情分析
        </Button>
      </div>
    </div>
  );
}, [addedCodes, handleAddWatchlist, handleAiDiagnose, navigate, percentileMap, showPercentile, strategyAverageAmounts, strategyDataSources, strategyFallbackCodes, strategyReturnsSinceSignal, strategySignalAges, strategySignalDates]);

  return (
    <div>
      {!isNarrow && (
        <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 8, alignItems: "center", gap: 6 }}>
          <span style={{ fontSize: 12, color: c.textMuted }}>指标视角:</span>
          <Space size={4}>
            <Button
              size="small"
              type={columnPerspective === "all" ? "primary" : "text"}
              onClick={() => setColumnPerspective("all")}
              style={{ fontSize: 12, padding: "0 8px" }}
            >
              全部指标
            </Button>
            <Button
              size="small"
              type={columnPerspective === "valuation" ? "primary" : "text"}
              onClick={() => setColumnPerspective("valuation")}
              style={{ fontSize: 12, padding: "0 8px" }}
            >
              估值核心
            </Button>
            <Button
              size="small"
              type={columnPerspective === "momentum" ? "primary" : "text"}
              onClick={() => setColumnPerspective("momentum")}
              style={{ fontSize: 12, padding: "0 8px" }}
            >
              量价动量
            </Button>
          </Space>
        </div>
      )}
      <Table
        columns={columns}
        dataSource={displayedItems}
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
          showTotal: isNarrow ? undefined : (total) => `共 ${total} 只`,
          onChange: (page, pageSize) => onPageChange(page, pageSize),
        }}
        onChange={handleTableChange}
        expandable={isNarrow ? {
          expandedRowRender: renderExpandedRow,
          columnWidth: 38,
        } : undefined}
        locale={{ emptyText: <Empty description="无匹配股票，请调整筛选条件" /> }}
        scroll={isNarrow ? { x: 380 } : { x: "max-content" }}
      />
    </div>
  );
}
