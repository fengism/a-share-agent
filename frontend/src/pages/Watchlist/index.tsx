import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AppstoreOutlined,
  BellOutlined,
  CaretDownOutlined,
  CaretRightOutlined,
  DeleteOutlined,
  DownloadOutlined,
  ExperimentOutlined,
  FallOutlined,
  FileSearchOutlined,
  ImportOutlined,
  MinusCircleOutlined,
  PlusOutlined,
  ReloadOutlined,
  RiseOutlined,
  RobotOutlined,
  SearchOutlined,
  SlidersOutlined,
  SortAscendingOutlined,
  SortDescendingOutlined,
  StarOutlined,
  TableOutlined,
  TagsOutlined,
} from "@ant-design/icons";
import {
  AutoComplete,
  Button,
  Card,
  Input,
  InputNumber,
  Modal,
  Segmented,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from "antd";
import type { TableColumnsType } from "antd";
import {
  useAddWatchlistAlert,
  useAddWatchlistItem,
  useDeleteWatchlistAlert,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import PreloadLink from "../../components/PreloadLink";
import SectionDataState from "../../components/SectionDataState";
import { useStockSearchController } from "../../hooks/useStockSearchController";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStyles } from "../../styles/ui";
import type {
  WatchlistAlertCondition,
  WatchlistConcept,
  WatchlistItem,
} from "../../types/watchlist";
import { buildWatchlistStockUrl, buildStockAnalysisUrl } from "../../utils/stockLinks";
import { formatMarketDate, formatMarketMonthDayClock, marketDateStamp } from "../../utils/marketTime";
import { PriceRangeBar } from "../../components/PriceRangeBar";
import { WatchlistAllocationBar } from "./components/WatchlistAllocationBar";
import { WatchlistCardList } from "./components/WatchlistCardList";
import { WatchlistNoteCell } from "./components/WatchlistNoteCell";
import { WatchlistQuickImportModal } from "./components/WatchlistQuickImportModal";
import "./watchlist.css";

const { Paragraph, Text, Title } = Typography;

type WatchlistViewMode = "all" | "concept";

interface ConceptGroup {
  key: string;
  name: string;
  items: WatchlistItem[];
}

type MarketDirection = "up" | "down" | "flat" | "unavailable";
type MarketFilter = "all" | MarketDirection;
type WatchlistSortKey = "default" | "change_pct" | "current_price" | "amount" | "market_cap";
type SortDirection = "ascend" | "descend";

interface MarketBreadthSummary {
  total: number;
  quoted: number;
  up: number;
  down: number;
  flat: number;
}

const CONDITION_LABELS: Record<WatchlistAlertCondition, string> = {
  price_above: "价格高于",
  price_below: "价格低于",
  change_pct_above: "涨跌幅高于",
  change_pct_below: "涨跌幅低于",
};

const MARKET_FILTER_OPTIONS: Array<{ label: string; value: MarketFilter }> = [
  { label: "全部", value: "all" },
  { label: "上涨", value: "up" },
  { label: "平盘", value: "flat" },
  { label: "下跌", value: "down" },
  { label: "暂无行情", value: "unavailable" },
];

const SORT_OPTIONS: Array<{ label: string; value: WatchlistSortKey }> = [
  { label: "加入时间", value: "default" },
  { label: "涨跌幅", value: "change_pct" },
  { label: "最新价", value: "current_price" },
  { label: "成交额", value: "amount" },
  { label: "总市值", value: "market_cap" },
];

const SOURCE_LABELS: Record<string, string> = {
  tencent: "腾讯行情",
  sina: "新浪行情",
  sina_direct: "新浪行情",
  eastmoney: "东方财富",
  eastmoney_direct: "东方财富",
  mixed: "多市场行情",
};

function sourceLabel(value: string | undefined): string {
  if (!value) return "等待行情";
  return SOURCE_LABELS[value] || value;
}

function formatQuotedTime(value: string | undefined): string {
  return formatMarketMonthDayClock(value, "尚未更新");
}

function formatPrice(value: number | null): string {
  return value == null ? "-" : value.toFixed(2);
}

function formatCompactNumber(value: number | null): string {
  if (value == null) return "-";
  const absolute = Math.abs(value);
  if (absolute >= 100_000_000) return `${(value / 100_000_000).toFixed(2)}亿`;
  if (absolute >= 10_000) return `${(value / 10_000).toFixed(2)}万`;
  return value.toFixed(0);
}

function formatPercent(value: number | null): string {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

function downloadWatchlistCsv(items: WatchlistItem[]) {
  const headers = [
    "代码",
    "市场",
    "名称",
    "最新价",
    "涨跌幅(%)",
    "今开",
    "最高",
    "最低",
    "成交额",
    "换手率(%)",
    "市盈率(TTM)",
    "总市值",
    "所属概念",
    "备注",
    "加入时间",
  ];

  const escapeCell = (val: unknown) => {
    if (val == null) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = items.map((item) => [
    item.stock_code,
    item.market === "hk" ? "港股" : "A股",
    item.stock_name,
    item.current_price != null ? item.current_price.toFixed(2) : "",
    item.change_pct != null ? item.change_pct.toFixed(2) : "",
    item.open_price != null ? item.open_price.toFixed(2) : "",
    item.high_price != null ? item.high_price.toFixed(2) : "",
    item.low_price != null ? item.low_price.toFixed(2) : "",
    item.amount != null ? item.amount : "",
    item.turnover_pct != null ? item.turnover_pct.toFixed(2) : "",
    item.pe_ttm != null ? item.pe_ttm.toFixed(2) : "",
    item.market_cap != null ? item.market_cap : "",
    (item.concepts || []).map((c) => c.name || c.code).join(";"),
    item.note || "",
    item.created_at || "",
  ].map(escapeCell).join(","));

  const csvContent = "\uFEFF" + [headers.map(escapeCell).join(","), ...rows].join("\r\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `我的自选股_${marketDateStamp()}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatDate(value: string): string {
  return formatMarketDate(value, value || "-");
}

function marketDirection(value: number | null): MarketDirection {
  if (value == null) return "unavailable";
  if (value > 0) return "up";
  if (value < 0) return "down";
  return "flat";
}

function summarizeMarketBreadth(items: WatchlistItem[]): MarketBreadthSummary {
  return items.reduce<MarketBreadthSummary>((summary, item) => {
    const direction = marketDirection(item.change_pct);
    summary.total += 1;
    if (direction !== "unavailable") summary.quoted += 1;
    if (direction === "up") summary.up += 1;
    if (direction === "down") summary.down += 1;
    if (direction === "flat") summary.flat += 1;
    return summary;
  }, { total: 0, quoted: 0, up: 0, down: 0, flat: 0 });
}

function sortWatchlistItems(
  items: WatchlistItem[],
  sortKey: WatchlistSortKey,
  sortDirection: SortDirection,
): WatchlistItem[] {
  if (sortKey === "default") {
    return sortDirection === "descend" ? [...items] : [...items].reverse();
  }

  const direction = sortDirection === "ascend" ? 1 : -1;
  return [...items].sort((left, right) => {
    const leftValue = left[sortKey];
    const rightValue = right[sortKey];
    if (leftValue == null && rightValue == null) return 0;
    if (leftValue == null) return 1;
    if (rightValue == null) return -1;
    return (leftValue - rightValue) * direction;
  });
}

function formatShare(count: number, total: number): string {
  if (total === 0) return "暂无行情";
  return `占有效行情 ${((count / total) * 100).toFixed(0)}%`;
}

function conceptIdentity(concept: WatchlistConcept): string {
  return concept.name.trim() || concept.code.trim();
}

function groupWatchlistByConcept(items: WatchlistItem[]): ConceptGroup[] {
  const groups = new Map<string, Map<number, WatchlistItem>>();
  const groupKeys = new Map<string, string>();

  for (const item of items) {
    const concepts = item.concepts
      .map((concept) => ({ ...concept, name: conceptIdentity(concept) }))
      .filter((concept) => concept.name);
    const itemGroups = concepts.length > 0 ? concepts : [{ code: "other", name: "其他" }];

    for (const concept of itemGroups) {
      const name = concept.name;
      if (!groups.has(name)) groups.set(name, new Map());
      groups.get(name)?.set(item.id, item);
      if (!groupKeys.has(name)) groupKeys.set(name, concept.code || name);
    }
  }

  return Array.from(groups, ([name, groupedItems]) => ({
    key: groupKeys.get(name) ?? name,
    name,
    items: Array.from(groupedItems.values()),
  })).sort((left, right) => {
    if (left.name === "其他") return 1;
    if (right.name === "其他") return -1;
    return right.items.length - left.items.length || left.name.localeCompare(right.name, "zh-CN");
  });
}

function WatchlistMetric({
  icon,
  label,
  value,
  detail,
  tone = "default",
}: {
  icon?: React.ReactNode;
  label: string;
  value: number;
  detail: string;
  tone?: MarketDirection | "default";
}) {
  return (
    <div className={`watchlist-page__metric is-${tone}`} aria-label={`${label} ${value}，${detail}`}>
      <span>
        {icon && <span style={{ marginRight: 6 }}>{icon}</span>}
        {label}
      </span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function ConceptTags({
  concepts,
  onSelect,
}: {
  concepts: WatchlistConcept[];
  onSelect: (conceptName: string) => void;
}) {
  const normalizedConcepts = concepts
    .map((concept) => ({ ...concept, name: conceptIdentity(concept) }))
    .filter((concept) => concept.name);
  const visible = normalizedConcepts.length > 0
    ? normalizedConcepts.slice(0, 3)
    : [{ code: "other", name: "其他" }];
  return (
    <div className="watchlist-page__concept-tags">
      {visible.map((concept) => (
        <button
          className="watchlist-page__concept-tag"
          key={`${concept.code}-${concept.name}`}
          type="button"
          aria-label={`查看${concept.name}分组`}
          onClick={() => onSelect(concept.name)}
        >
          {concept.name}
        </button>
      ))}
      {normalizedConcepts.length > visible.length ? <Tag>+{normalizedConcepts.length - visible.length}</Tag> : null}
    </div>
  );
}

export default function WatchlistPage() {
  const { cardStyle, pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
  const isMobile = useMediaQuery("(max-width: 640px)");
  const watchlist = useWatchlist();
  const addItem = useAddWatchlistItem();
  const deleteItem = useDeleteWatchlistItem();
  const addAlert = useAddWatchlistAlert();
  const deleteAlert = useDeleteWatchlistAlert();
  const stockSearch = useStockSearchController();
  const [filterText, setFilterText] = useState("");
  const [marketFilter, setMarketFilter] = useState<MarketFilter>("all");
  const navigate = useNavigate();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [sortKey, setSortKey] = useState<WatchlistSortKey>("default");
  const [sortDirection, setSortDirection] = useState<SortDirection>("descend");
  const [viewMode, setViewMode] = useState<WatchlistViewMode>("all");
  const [activeConcept, setActiveConcept] = useState("all");
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(() => new Set());
  const [alertStock, setAlertStock] = useState<WatchlistItem | null>(null);
  const [condition, setCondition] = useState<WatchlistAlertCondition>("price_above");
  const [threshold, setThreshold] = useState<number | null>(null);
  const [layoutMode, setLayoutMode] = useState<"table" | "cards">("table");
  const [quickImportOpen, setQuickImportOpen] = useState(false);

  const selectedStockCodes = useMemo(() => {
    const allItems = watchlist.data?.items ?? [];
    const codeSet = new Set<string>();
    for (const id of selectedIds) {
      const match = allItems.find((item) => item.id === id);
      if (match) codeSet.add(match.stock_code);
    }
    return Array.from(codeSet);
  }, [selectedIds, watchlist.data?.items]);

  const selectedStockNames = useMemo(() => {
    const allItems = watchlist.data?.items ?? [];
    const names: string[] = [];
    for (const id of selectedIds) {
      const match = allItems.find((item) => item.id === id);
      if (match) names.push(`${match.stock_name}(${match.stock_code})`);
    }
    return names;
  }, [selectedIds, watchlist.data?.items]);

  const addOptions = useMemo(() => stockSearch.currentResults.slice(0, 8).map((stock) => ({
    value: stock.code,
    label: (
      <span className="watchlist-page__search-option">
        <span>{stock.name}</span>
        <Text type="secondary">{stock.code}</Text>
        {stock.market === "hk" ? <Tag color="blue">港股</Tag> : null}
      </span>
    ),
  })), [stockSearch.currentResults]);

  const filteredItems = useMemo(() => {
    const keyword = filterText.trim().toLocaleLowerCase("zh-CN");
    const items = watchlist.data?.items ?? [];
    const textMatchedItems = keyword
      ? items.filter((item) => [
        item.stock_name,
        item.stock_code,
        ...item.concepts.flatMap((concept) => [concept.name, concept.code]),
      ].some((value) => value.toLocaleLowerCase("zh-CN").includes(keyword)))
      : items;
    const marketMatchedItems = marketFilter === "all"
      ? textMatchedItems
      : textMatchedItems.filter((item) => marketDirection(item.change_pct) === marketFilter);
    return sortWatchlistItems(marketMatchedItems, sortKey, sortDirection);
  }, [filterText, marketFilter, sortDirection, sortKey, watchlist.data?.items]);

  const availableConceptGroups = useMemo(
    () => groupWatchlistByConcept(watchlist.data?.items ?? []),
    [watchlist.data?.items],
  );
  const conceptGroups = useMemo(() => groupWatchlistByConcept(filteredItems), [filteredItems]);
  const visibleConceptGroups = useMemo(
    () => activeConcept === "all"
      ? conceptGroups
      : conceptGroups.filter((group) => group.name === activeConcept),
    [activeConcept, conceptGroups],
  );
  const marketSummary = useMemo(
    () => summarizeMarketBreadth(watchlist.data?.items ?? []),
    [watchlist.data?.items],
  );
  const marketFilterOptions = useMemo(() => {
    const counts: Record<MarketFilter, number> = {
      all: marketSummary.total,
      up: marketSummary.up,
      flat: marketSummary.flat,
      down: marketSummary.down,
      unavailable: marketSummary.total - marketSummary.quoted,
    };
    return MARKET_FILTER_OPTIONS.map((option) => ({
      ...option,
      label: (
        <span className="watchlist-page__market-option">
          <span>{option.label}</span>
          <span className="watchlist-page__market-count">{counts[option.value]}</span>
        </span>
      ),
    }));
  }, [marketSummary]);

  const handleAdd = async (stockCode: string) => {
    try {
      await addItem.mutateAsync({ stock_code: stockCode, note: "" });
      stockSearch.clear();
      message.success("已加入自选");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "添加自选失败");
    }
  };

  const handleUpdateNote = async (stockCode: string, note: string, market?: "cn" | "hk") => {
    await addItem.mutateAsync({ stock_code: stockCode, note, market });
  };

  const handleBatchImport = async (stocks: Array<{ code: string; market?: "cn" | "hk" }>) => {
    for (const stock of stocks) {
      await addItem.mutateAsync({ stock_code: stock.code, note: "", market: stock.market });
    }
  };

  const handleDelete = async (item: WatchlistItem) => {
    try {
      await deleteItem.mutateAsync(
        item.market === "hk"
          ? { stockCode: item.stock_code, market: "hk" }
          : item.stock_code,
      );
      message.success(`已移除 ${item.stock_name}`);
    } catch (error) {
      message.error(error instanceof Error ? error.message : "移除自选失败");
    }
  };

  const handleCreateAlert = async () => {
    if (!alertStock || threshold == null) return;
    try {
      await addAlert.mutateAsync({
        stockCode: alertStock.stock_code,
        request: { condition, threshold, ...(alertStock.market === "hk" ? { market: "hk" as const } : {}) },
      });
      setAlertStock(null);
      setThreshold(null);
      message.success("提醒规则已添加");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "添加提醒失败");
    }
  };

  const handleDeleteAlert = async (alertId: number) => {
    try {
      await deleteAlert.mutateAsync(alertId);
      message.success("提醒规则已删除");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除提醒失败");
    }
  };

  const toggleGroup = (groupName: string) => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      if (next.has(groupName)) next.delete(groupName);
      else next.add(groupName);
      return next;
    });
  };

  const expandAllGroups = () => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      visibleConceptGroups.forEach((group) => next.delete(group.name));
      return next;
    });
  };

  const collapseAllGroups = () => {
    setCollapsedGroups((current) => {
      const next = new Set(current);
      visibleConceptGroups.forEach((group) => next.add(group.name));
      return next;
    });
  };

  const focusConceptGroup = (conceptName: string) => {
    setViewMode("concept");
    setActiveConcept(conceptName);
    setCollapsedGroups((current) => {
      const next = new Set(current);
      next.delete(conceptName);
      return next;
    });
  };

  const resetFilters = () => {
    setFilterText("");
    setMarketFilter("all");
    setActiveConcept("all");
  };

  const columns: TableColumnsType<WatchlistItem> = [
    {
      title: "股票",
      key: "stock",
      fixed: "left",
      width: isMobile ? 120 : 156,
      render: (_, item) => {
        const isLimitUp = (item.change_pct ?? 0) >= 9.8;
        const isLimitDown = (item.change_pct ?? 0) <= -9.8;
        const isHighTurnover = (item.turnover_pct ?? 0) >= 10;
        return (
          <PreloadLink className="watchlist-page__stock" to={buildWatchlistStockUrl(item.stock_code, item.market)}>
            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
              <strong>{item.stock_name}</strong>
              {item.market === "hk" ? <Tag color="blue" style={{ margin: 0, padding: "0 3px", fontSize: 10 }}>港股</Tag> : null}
              {isLimitUp ? <Tag color="red" style={{ margin: 0, padding: "0 3px", fontSize: 10, lineHeight: "16px" }}>涨停</Tag> : null}
              {isLimitDown ? <Tag color="green" style={{ margin: 0, padding: "0 3px", fontSize: 10, lineHeight: "16px" }}>跌停</Tag> : null}
              {isHighTurnover ? <Tag color="orange" style={{ margin: 0, padding: "0 3px", fontSize: 10, lineHeight: "16px" }}>高换手</Tag> : null}
            </div>
            <span>{item.stock_code}</span>
          </PreloadLink>
        );
      },
    },
    {
      title: "最新价",
      dataIndex: "current_price",
      width: isMobile ? 80 : 92,
      fixed: isMobile ? undefined : "left",
      align: "right",
      render: (value: number | null, item) => (
        <strong className={`watchlist-page__price is-${marketDirection(item.change_pct)} financial-num`}>
          {formatPrice(value)}
        </strong>
      ),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: isMobile ? 84 : 96,
      fixed: isMobile ? undefined : "left",
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "日内区间",
      key: "price_range",
      width: isMobile ? 84 : 96,
      align: "center",
      render: (_, item) => (
        <PriceRangeBar
          low={item.low_price}
          high={item.high_price}
          current={item.current_price}
        />
      ),
    },
    {
      title: "今开",
      dataIndex: "open_price",
      width: isMobile ? 76 : 88,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatPrice(val)}</span>,
    },
    {
      title: "最高",
      dataIndex: "high_price",
      width: isMobile ? 76 : 88,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatPrice(val)}</span>,
    },
    {
      title: "最低",
      dataIndex: "low_price",
      width: isMobile ? 76 : 88,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatPrice(val)}</span>,
    },
    {
      title: "成交额",
      dataIndex: "amount",
      width: isMobile ? 90 : 104,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatCompactNumber(val)}</span>,
    },
    {
      title: "换手率",
      dataIndex: "turnover_pct",
      width: isMobile ? 80 : 92,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatPercent(val)}</span>,
    },
    {
      title: "市盈率",
      dataIndex: "pe_ttm",
      width: isMobile ? 76 : 88,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatPrice(val)}</span>,
    },
    {
      title: "总市值",
      dataIndex: "market_cap",
      width: isMobile ? 90 : 104,
      align: "right",
      render: (val: number | null) => <span className="financial-num">{formatCompactNumber(val)}</span>,
    },
    {
      title: "所属概念",
      dataIndex: "concepts",
      width: isMobile ? 180 : 230,
      render: (concepts: WatchlistConcept[]) => (
        <ConceptTags concepts={concepts} onSelect={focusConceptGroup} />
      ),
    },
    {
      title: "提醒",
      dataIndex: "alerts",
      width: isMobile ? 170 : 210,
      render: (_, item) => (
        <div className="watchlist-page__alerts">
          {item.alerts.slice(0, 2).map((alert) => (
            <Tag
              key={alert.id}
              color={alert.triggered ? "red" : "default"}
              closable
              onClose={(event) => {
                event.preventDefault();
                void handleDeleteAlert(alert.id);
              }}
            >
              {alert.triggered ? "已触发 · " : ""}{CONDITION_LABELS[alert.condition]} {alert.threshold}
            </Tag>
          ))}
          {item.alerts.length > 2 ? <Tag>+{item.alerts.length - 2}</Tag> : null}
          <Tooltip title="设置提醒">
            <Button
              type="text"
              size="small"
              aria-label={`设置${item.stock_name}提醒`}
              icon={<BellOutlined />}
              onClick={() => setAlertStock(item)}
            />
          </Tooltip>
        </div>
      ),
    },
    {
      title: "备注",
      dataIndex: "note",
      width: isMobile ? 120 : 150,
      render: (_, item) => (
        <WatchlistNoteCell item={item} onUpdateNote={handleUpdateNote} />
      ),
    },
    {
      title: "加入时间",
      dataIndex: "created_at",
      width: isMobile ? 100 : 116,
      render: formatDate,
    },
    {
      title: "操作",
      key: "actions",
      fixed: "right",
      width: isMobile ? 90 : 112,
      align: "center",
      render: (_, item) => (
        <Space size={2}>
          <Tooltip title="AI 深度体检">
            <Button
              type="text"
              size="small"
              aria-label={`AI体检${item.stock_name}`}
              icon={<RobotOutlined style={{ color: "var(--c-primary)" }} />}
              onClick={() =>
                navigate(
                  `/chat?prompt=${encodeURIComponent(
                    `请深度诊断【${item.stock_name}(${item.stock_code})】的投资价值、核心驱动力、估值水平与主要风险点`,
                  )}`,
                )
              }
            />
          </Tooltip>
          <Tooltip title="查看研报">
            <Button
              type="text"
              size="small"
              aria-label={`研报${item.stock_name}`}
              icon={<FileSearchOutlined />}
              onClick={() => navigate(buildStockAnalysisUrl(item.stock_code))}
            />
          </Tooltip>
          <Tooltip title="移除自选">
            <Button
              type="text"
              danger
              size="small"
              aria-label={`移除${item.stock_name}`}
              icon={<DeleteOutlined />}
              loading={deleteItem.isPending}
              onClick={() => void handleDelete(item)}
            />
          </Tooltip>
        </Space>
      ),
    },
  ];

  const renderTable = (items: WatchlistItem[], labelledBy?: string) => (
    <div className="watchlist-page__table-wrap" role="region" aria-labelledby={labelledBy}>
      {selectedStockCodes.length > 0 && (
        <div className="watchlist-page__batch-bar">
          <Tag color="blue" style={{ margin: 0 }}>已选 {selectedStockCodes.length} 只</Tag>
          <Button
            size="small"
            aria-label="AI 对比"
            icon={<SlidersOutlined />}
            onClick={() =>
              navigate(
                `/chat?prompt=${encodeURIComponent(
                  `请深度横向对比以下 ${selectedStockCodes.length} 只股票的投资价值、核心逻辑、估值水平与催化剂优劣：\n${selectedStockNames.join("、")}`,
                )}`,
              )
            }
          >
            AI 对比
          </Button>
          <Button
            size="small"
            aria-label="AI 组合诊断"
            icon={<RobotOutlined />}
            onClick={() =>
              navigate(
                `/chat?prompt=${encodeURIComponent(
                  `请对以下 ${selectedStockCodes.length} 只自选股组成的观察组合进行行业集中度、主线协同与潜在风险敞口诊断：\n${selectedStockNames.join("、")}`,
                )}`,
              )
            }
          >
            AI 组合诊断
          </Button>
          <Button
            size="small"
            aria-label="批量回测"
            icon={<ExperimentOutlined />}
            onClick={() => navigate(`/quant?codes=${encodeURIComponent(selectedStockCodes.join(","))}`)}
          >
            批量回测
          </Button>
          <Button size="small" type="link" onClick={() => setSelectedIds([])} style={{ padding: "0 4px" }}>
            清空选择
          </Button>
        </div>
      )}
      <Table<WatchlistItem>
        className="watchlist-page__table"
        columns={columns}
        dataSource={items}
        rowKey="id"
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys.map(Number)),
        }}
        size="small"
        pagination={false}
        scroll={{ x: isMobile ? 1380 : 1690 }}
        rowClassName={(item) => `watchlist-page__row is-${marketDirection(item.change_pct)}`}
      />
    </div>
  );

  const handleToggleSelect = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((i) => i !== id) : [...prev, id],
    );
  };

  const renderItemsView = (items: WatchlistItem[], labelledBy?: string) => {
    if (layoutMode === "cards") {
      return (
        <div role="region" aria-labelledby={labelledBy}>
          {selectedStockCodes.length > 0 && (
            <div className="watchlist-page__batch-bar" style={{ marginBottom: 12 }}>
              <Tag color="blue" style={{ margin: 0 }}>已选 {selectedStockCodes.length} 只</Tag>
              <Button
                size="small"
                aria-label="AI 对比"
                icon={<SlidersOutlined />}
                onClick={() =>
                  navigate(
                    `/chat?prompt=${encodeURIComponent(
                      `请深度横向对比以下 ${selectedStockCodes.length} 只股票的投资价值、核心逻辑、估值水平与催化剂优劣：\n${selectedStockNames.join("、")}`,
                    )}`,
                  )
                }
              >
                AI 对比
              </Button>
              <Button
                size="small"
                aria-label="AI 组合诊断"
                icon={<RobotOutlined />}
                onClick={() =>
                  navigate(
                    `/chat?prompt=${encodeURIComponent(
                      `请对以下 ${selectedStockCodes.length} 只自选股组成的观察组合进行行业集中度、主线协同与潜在风险敞口诊断：\n${selectedStockNames.join("、")}`,
                    )}`,
                  )
                }
              >
                AI 组合诊断
              </Button>
              <Button
                size="small"
                aria-label="批量回测"
                icon={<ExperimentOutlined />}
                onClick={() => navigate(`/quant?codes=${encodeURIComponent(selectedStockCodes.join(","))}`)}
              >
                批量回测
              </Button>
              <Button size="small" type="link" onClick={() => setSelectedIds([])} style={{ padding: "0 4px" }}>
                清空选择
              </Button>
            </div>
          )}
          <WatchlistCardList
            items={items}
            selectedIds={selectedIds}
            onToggleSelect={handleToggleSelect}
            onSetAlert={setAlertStock}
            onDelete={(item) => void handleDelete(item)}
            onSelectConcept={focusConceptGroup}
          />
        </div>
      );
    }
    return renderTable(items, labelledBy);
  };

  const totalCount = marketSummary.total;
  const hasFilter = Boolean(filterText.trim())
    || marketFilter !== "all"
    || (viewMode === "concept" && activeConcept !== "all");
  const visibleItemCount = viewMode === "concept" && activeConcept !== "all"
    ? visibleConceptGroups[0]?.items.length ?? 0
    : filteredItems.length;
  const isEmpty = totalCount === 0 || visibleItemCount === 0;

  return (
    <div className="watchlist-page" style={pageContainerStyle}>
      <header className="watchlist-page__header">
        <div className="watchlist-page__heading">
          <div className="watchlist-page__eyebrow">WATCHLIST · 自选观察</div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>我的自选</Title>
          </div>
          <Paragraph style={{ ...pageDescriptionStyle, marginBottom: 0 }}>
            集中跟踪自选股行情、所属概念和价格提醒，按概念快速定位市场主线。
          </Paragraph>
        </div>
        <div className="watchlist-page__status">
          <span>行情来源 · {sourceLabel(watchlist.data?.source)}</span>
          <span>更新于 {formatQuotedTime(watchlist.data?.quoted_at)}</span>
          <Button
            type="primary"
            icon={<RobotOutlined />}
            disabled={!watchlist.data?.items?.length}
            onClick={() => {
              const allItems = filteredItems.length > 0 ? filteredItems : (watchlist.data?.items ?? []);
              const stockListStr = allItems
                .slice(0, 15)
                .map((i) => `${i.stock_name}(${i.stock_code})`)
                .join("、");
              navigate(
                `/chat?prompt=${encodeURIComponent(
                  `请全面深度诊断我的自选股组合，分析各标的今日盘面走势、板块主线归属、估值分位及近期需要注意的风险点与潜在机会。\n当前自选标的：${stockListStr}${allItems.length > 15 ? ` 等共 ${allItems.length} 只` : ""}`,
                )}`,
              );
            }}
          >
            AI 诊断自选池
          </Button>
          <Button
            icon={<DownloadOutlined />}
            onClick={() => {
              const exportItems = filteredItems.length > 0 ? filteredItems : (watchlist.data?.items ?? []);
              if (exportItems.length === 0) {
                message.warning("暂无自选股数据可导出");
                return;
              }
              downloadWatchlistCsv(exportItems);
              message.success(`已导出 ${exportItems.length} 只自选股数据`);
            }}
            disabled={!watchlist.data?.items?.length}
          >
            导出 CSV
          </Button>
          <Button
            icon={<ReloadOutlined />}
            loading={watchlist.isFetching}
            onClick={() => void watchlist.refetch()}
          >
            刷新
          </Button>
        </div>
      </header>

      <div className="watchlist-page__metrics" role="group" aria-label="自选股涨跌概览">
        <WatchlistMetric
          icon={<StarOutlined />}
          label="自选总数"
          value={marketSummary.total}
          detail={`${marketSummary.quoted} 只已有行情`}
        />
        <WatchlistMetric
          icon={<RiseOutlined />}
          label="上涨"
          value={marketSummary.up}
          detail={formatShare(marketSummary.up, marketSummary.quoted)}
          tone="up"
        />
        <WatchlistMetric
          icon={<MinusCircleOutlined />}
          label="平盘"
          value={marketSummary.flat}
          detail={formatShare(marketSummary.flat, marketSummary.quoted)}
          tone="flat"
        />
        <WatchlistMetric
          icon={<FallOutlined />}
          label="下跌"
          value={marketSummary.down}
          detail={formatShare(marketSummary.down, marketSummary.quoted)}
          tone="down"
        />
      </div>

      <WatchlistAllocationBar
        items={watchlist.data?.items ?? []}
        activeConcept={activeConcept}
        onSelectConcept={focusConceptGroup}
      />

      <Card className="watchlist-page__toolbar-card" style={cardStyle}>
        <div className="watchlist-page__toolbar">
          <div className="watchlist-page__add">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span className="watchlist-page__field-label">添加自选</span>
              <Button
                type="link"
                size="small"
                icon={<ImportOutlined />}
                onClick={() => setQuickImportOpen(true)}
                style={{ padding: 0, fontSize: 12, height: "auto" }}
              >
                快速导入
              </Button>
            </div>
            <AutoComplete
              aria-label="搜索并添加自选股"
              value={stockSearch.inputValue}
              options={addOptions}
              onChange={stockSearch.setInputValue}
              onSelect={handleAdd}
              filterOption={false}
              notFoundContent={stockSearch.normalizedInput && !stockSearch.isPending ? "未找到股票" : null}
            >
              <Input prefix={<PlusOutlined />} placeholder="输入股票名称或代码" allowClear />
            </AutoComplete>
          </div>
          <div className="watchlist-page__filter">
            <span className="watchlist-page__field-label">筛选自选</span>
            <Input
              aria-label="筛选自选股"
              value={filterText}
              onChange={(event) => setFilterText(event.target.value)}
              prefix={<SearchOutlined />}
              placeholder="搜索名称、代码或概念"
              allowClear
            />
          </div>
          <div className="watchlist-page__view-control">
            <span className="watchlist-page__field-label">展示方式</span>
            <Segmented
              aria-label="自选股展示方式"
              value={viewMode}
              onChange={(value) => setViewMode(value as WatchlistViewMode)}
              options={[
                { label: "全部", value: "all" },
                { label: "概念分组", value: "concept", icon: <TagsOutlined /> },
              ]}
            />
          </div>
          <div className="watchlist-page__filter-bar">
            <div className="watchlist-page__market-filter">
              <span className="watchlist-page__field-label">行情状态</span>
              <Segmented
                aria-label="按行情状态筛选"
                value={marketFilter}
                onChange={(value) => setMarketFilter(value as MarketFilter)}
                options={marketFilterOptions}
              />
            </div>
            <div className="watchlist-page__sort-control">
              <span className="watchlist-page__field-label">排序方式</span>
              <Space.Compact block>
                <Select<WatchlistSortKey>
                  aria-label="排序指标"
                  value={sortKey}
                  onChange={setSortKey}
                  options={SORT_OPTIONS}
                />
                <Tooltip title={sortDirection === "ascend" ? "当前升序，点击切换为降序" : "当前降序，点击切换为升序"}>
                  <Button
                    aria-label={sortDirection === "ascend" ? "切换为降序" : "切换为升序"}
                    icon={sortDirection === "ascend" ? <SortAscendingOutlined /> : <SortDescendingOutlined />}
                    onClick={() => setSortDirection((current) => current === "ascend" ? "descend" : "ascend")}
                  >
                    {sortDirection === "ascend" ? "升序" : "降序"}
                  </Button>
                </Tooltip>
              </Space.Compact>
            </div>
          </div>
        </div>
      </Card>

      <Card className="watchlist-page__content-card" style={cardStyle}>
        <div className="watchlist-page__content-heading">
          <div className="watchlist-page__content-title">
            <strong>{viewMode === "all" ? "全部自选" : "概念分组"}</strong>
            <span>
              {hasFilter
                ? `筛选到 ${visibleItemCount} 只股票`
                : viewMode === "all"
                  ? "按实时行情集中查看"
                  : `共 ${conceptGroups.length} 个概念分组`}
            </span>
          </div>
          <div className="watchlist-page__content-actions">
            {viewMode === "concept" ? (
              <>
                <Select
                  aria-label="定位概念分组"
                  value={activeConcept}
                  onChange={setActiveConcept}
                  options={[
                    { label: "全部概念", value: "all" },
                    ...availableConceptGroups.map((group) => ({
                      label: `${group.name}（${group.items.length}）`,
                      value: group.name,
                    })),
                  ]}
                />
                <Space.Compact>
                  <Button size="small" onClick={expandAllGroups}>全部展开</Button>
                  <Button size="small" onClick={collapseAllGroups}>全部收起</Button>
                </Space.Compact>
              </>
            ) : null}
            {hasFilter ? (
              <Button type="link" size="small" onClick={resetFilters}>重置筛选</Button>
            ) : null}
            <Segmented
              aria-label="视图布局"
              size="small"
              value={layoutMode}
              onChange={(val) => setLayoutMode(val as "table" | "cards")}
              options={[
                { value: "table", icon: <TableOutlined />, label: "表格" },
                { value: "cards", icon: <AppstoreOutlined />, label: "卡片" },
              ]}
            />
            <span className="watchlist-page__visible-count">当前显示 {visibleItemCount} 只</span>
          </div>
        </div>
        <SectionDataState
          isLoading={watchlist.isLoading}
          error={!watchlist.data ? watchlist.error : undefined}
          onRetry={() => watchlist.refetch()}
          isEmpty={isEmpty}
          emptyText={totalCount === 0 ? "还没有自选股，请先搜索添加" : "没有符合当前筛选条件的自选股"}
          errorTitle="自选股加载失败"
          skeletonRows={5}
          minHeight={320}
        >
          {viewMode === "all" ? renderItemsView(filteredItems) : (
            <div className="watchlist-page__groups">
              {visibleConceptGroups.map((group, index) => {
                const isCollapsed = collapsedGroups.has(group.name);
                const groupSummary = summarizeMarketBreadth(group.items);
                const titleId = `watchlist-group-title-${index}`;
                const panelId = `watchlist-group-panel-${index}`;
                return (
                  <section className="watchlist-page__group" key={group.name}>
                    <button
                      id={titleId}
                      className="watchlist-page__group-header"
                      type="button"
                      aria-expanded={!isCollapsed}
                      aria-controls={panelId}
                      onClick={() => toggleGroup(group.name)}
                    >
                      <span className="watchlist-page__group-caret" aria-hidden="true">
                        {isCollapsed ? <CaretRightOutlined /> : <CaretDownOutlined />}
                      </span>
                      <span className="watchlist-page__group-name">{group.name}</span>
                      <span className="watchlist-page__group-breadth" aria-label={`${group.name}涨跌概览`}>
                        <span className="is-up">涨 {groupSummary.up}</span>
                        <span className="is-flat">平 {groupSummary.flat}</span>
                        <span className="is-down">跌 {groupSummary.down}</span>
                      </span>
                      <span className="watchlist-page__group-count">{group.items.length} 只</span>
                    </button>
                    {!isCollapsed ? (
                      <div id={panelId} aria-labelledby={titleId}>
                        {renderItemsView(group.items, titleId)}
                      </div>
                    ) : null}
                  </section>
                );
              })}
            </div>
          )}
        </SectionDataState>
      </Card>

      <Modal
        title={alertStock ? `设置 ${alertStock.stock_name} 提醒` : "设置提醒"}
        open={Boolean(alertStock)}
        onCancel={() => setAlertStock(null)}
        onOk={handleCreateAlert}
        okButtonProps={{ disabled: threshold == null, loading: addAlert.isPending }}
        okText="添加提醒"
        width="min(440px, calc(100vw - 32px))"
      >
        <Space orientation="vertical" style={{ width: "100%" }}>
          <Select
            aria-label="提醒条件"
            value={condition}
            onChange={setCondition}
            options={Object.entries(CONDITION_LABELS).map(([value, label]) => ({ value, label }))}
            style={{ width: "100%" }}
          />
          <InputNumber
            aria-label="提醒阈值"
            value={threshold}
            onChange={setThreshold}
            placeholder={condition.startsWith("change_pct") ? "阈值（%）" : "价格阈值"}
            style={{ width: "100%" }}
          />
        </Space>
      </Modal>

      <WatchlistQuickImportModal
        open={quickImportOpen}
        onClose={() => setQuickImportOpen(false)}
        existingCodes={(watchlist.data?.items ?? []).map((i) => i.stock_code)}
        onImport={handleBatchImport}
      />
    </div>
  );
}
