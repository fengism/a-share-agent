import { useEffect, useMemo, useState } from "react";
import {
  CloseOutlined,
  FullscreenOutlined,
  LineChartOutlined,
  ReloadOutlined,
  SearchOutlined,
  StarOutlined,
} from "@ant-design/icons";
import {
  AutoComplete,
  Button,
  Card,
  Col,
  Input,
  Modal,
  Pagination,
  Row,
  Segmented,
  Space,
  Table,
  Tag,
  Typography,
  message,
  type TableProps,
} from "antd";
import {
  useHKIndexHistory,
  useHKIndices,
  useHKStockHistory,
  useHKStockSearch,
  useHKStocks,
  type HKKlineData,
  type HKStockQuote,
  type HKStockSearchItem,
} from "../../api/queryHooks/hk";
import { useAddWatchlistItem } from "../../api/queryHooks/watchlist";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import LazyKlineChart from "../../charts/LazyKlineChart";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles, useTokens, type ThemeColors } from "../../styles/ui";
import type { KlineItem } from "../../types/stock";
import "./hk-market.css";

const { Title, Paragraph, Text } = Typography;
const INDEX_SYMBOLS = ["HSI", "HSCEI", "HSTECH"];
const MAX_COMPARE_STOCKS = 5;
const PERIOD_OPTIONS = [
  { label: "日K", value: "daily" },
  { label: "周K", value: "weekly" },
  { label: "月K", value: "monthly" },
];
const ADJUST_OPTIONS = [
  { label: "不复权", value: "none" },
  { label: "前复权", value: "qfq" },
  { label: "后复权", value: "hfq" },
];

const SORT_OPTIONS = [
  { label: "默认排序", value: "default" },
  { label: "涨幅榜", value: "gainers" },
  { label: "跌幅榜", value: "losers" },
  { label: "成交额榜", value: "amount" },
] as const;

type SortOption = (typeof SORT_OPTIONS)[number]["value"];

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? "-" : value.toLocaleString("zh-CN", { maximumFractionDigits: digits });
}

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return formatNumber(value, 0);
}

function getChangeColor(changePct: number | null | undefined, c: ThemeColors) {
  if (changePct == null) return c.textSecondary;
  if (changePct > 0) return c.up;
  if (changePct < 0) return c.down;
  return c.textSecondary;
}

function chartItems(items: HKKlineData["items"] | undefined): KlineItem[] {
  return (items ?? []).map((item) => ({
    date: item.date,
    open: item.open,
    close: item.close,
    high: item.high,
    low: item.low,
    volume: item.volume,
    amount: item.amount,
    amplitude: item.amplitude ?? null,
    turnover_pct: item.turnover_pct ?? null,
    change_pct: item.change_pct ?? null,
  }));
}

export interface HKMarketTabProps {
  embedded?: boolean;
  defaultStockCode?: string;
  onStockSelect?: (code: string | null) => void;
}

export default function HKMarketTab({
  embedded = false,
  defaultStockCode,
  onStockSelect,
}: HKMarketTabProps = {}) {
  const colors = useColors();
  const tokens = useTokens();
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const [activeIndex, setActiveIndex] = useState("HSI");
  const [indexPeriod, setIndexPeriod] = useState("daily");
  const [stockPeriod, setStockPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const [selectedStocks, setSelectedStocks] = useState<HKStockQuote[]>([]);
  const [activeStock, setActiveStock] = useState<Pick<HKStockQuote, "code" | "name"> | null>(() => (
    defaultStockCode ? { code: defaultStockCode, name: defaultStockCode } : null
  ));
  const [search, setSearch] = useState("");
  const [selectedSearchValue, setSelectedSearchValue] = useState<string | null>(null);
  const [sortOption, setSortOption] = useState<SortOption>("default");
  const [indexChartExpanded, setIndexChartExpanded] = useState(false);
  const [stockChartExpanded, setStockChartExpanded] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const normalizedSearch = search.trim();
  const debouncedSearch = useDebouncedValue(normalizedSearch, 200);
  const isSelectedSearch = selectedSearchValue != null && selectedSearchValue === normalizedSearch;
  const searchQuery = isSelectedSearch ? "" : debouncedSearch;
  const [page, setPage] = useState(1);
  const pageSize = 50;

  const indicesQuery = useHKIndices();
  const indexHistoryQuery = useHKIndexHistory(activeIndex, indexPeriod);
  const stocksQuery = useHKStocks("", page, pageSize);
  const stockSearchQuery = useHKStockSearch(searchQuery);
  const stockHistoryQuery = useHKStockHistory(activeStock?.code ?? "", stockPeriod, adjust);
  const addWatchlistItem = useAddWatchlistItem();

  useEffect(() => {
    if (defaultStockCode && defaultStockCode !== activeStock?.code) {
      const match = stocksQuery.data?.items.find((item) => item.code === defaultStockCode);
      setActiveStock(match ?? { code: defaultStockCode, name: defaultStockCode });
    }
  }, [activeStock?.code, defaultStockCode, stocksQuery.data?.items]);

  useEffect(() => {
    if (activeStock && activeStock.name === activeStock.code && stocksQuery.data?.items) {
      const match = stocksQuery.data.items.find((item) => item.code === activeStock.code);
      if (match) {
        setActiveStock(match);
      }
    }
  }, [activeStock, stocksQuery.data?.items]);

  const indices = useMemo(
    () => INDEX_SYMBOLS.map((symbol) => indicesQuery.data?.indices.find((item) => item.code === symbol)).filter((item) => item != null),
    [indicesQuery.data],
  );
  const activeIndexObj = useMemo(
    () => indices.find((item) => item.code === activeIndex),
    [indices, activeIndex],
  );

  const activeStockQuote = useMemo(() => {
    if (!activeStock) return null;
    return stocksQuery.data?.items.find((item) => item.code === activeStock.code) ?? null;
  }, [activeStock, stocksQuery.data?.items]);

  const selectedCodes = useMemo(() => selectedStocks.map((stock) => stock.code), [selectedStocks]);

  const searchItems = useMemo(
    () => !isSelectedSearch && normalizedSearch === debouncedSearch
      ? stockSearchQuery.data?.items ?? []
      : [],
    [debouncedSearch, isSelectedSearch, normalizedSearch, stockSearchQuery.data?.items],
  );

  const searchOptions = useMemo(
    () => searchItems.map((stock) => ({
      value: stock.code,
      label: (
        <div className="hk-stock-search-option">
          <Text strong style={{ color: colors.textPrimary }}>{stock.name}</Text>
          <Text className="financial-num" type="secondary" style={{ color: colors.primary }}>{stock.code}</Text>
          {stock.english_name && <Text type="secondary" style={{ color: colors.textSecondary }}>{stock.english_name}</Text>}
        </div>
      ),
    })),
    [colors.primary, colors.textPrimary, colors.textSecondary, searchItems],
  );

  const isSearchPending = !isSelectedSearch && Boolean(normalizedSearch)
    && (normalizedSearch !== debouncedSearch || stockSearchQuery.isFetching);

  const displayStocks = useMemo(() => {
    const list = [...(stocksQuery.data?.items ?? [])];
    if (sortOption === "gainers") {
      return list.sort((a, b) => (b.change_pct ?? -Infinity) - (a.change_pct ?? -Infinity));
    }
    if (sortOption === "losers") {
      return list.sort((a, b) => (a.change_pct ?? Infinity) - (b.change_pct ?? Infinity));
    }
    if (sortOption === "amount") {
      return list.sort((a, b) => (b.amount ?? -Infinity) - (a.amount ?? -Infinity));
    }
    return list;
  }, [sortOption, stocksQuery.data?.items]);

  const columns: TableProps<HKStockQuote>["columns"] = [
    {
      title: "代码",
      dataIndex: "code",
      key: "code",
      width: 96,
      render: (value: string) => <Text className="financial-num" strong style={{ color: colors.primary }}>{value}</Text>,
    },
    {
      title: "名称",
      dataIndex: "name",
      key: "name",
      width: 170,
      ellipsis: true,
      render: (_: unknown, record: HKStockQuote) => (
        <div className="hk-stock-name-cell">
          <Text strong ellipsis style={{ color: colors.textPrimary }}>{record.name}</Text>
          {record.english_name && <span className="hk-stock-english-name">{record.english_name}</span>}
        </div>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      key: "price",
      align: "right" as const,
      sorter: (a, b) => (a.price ?? 0) - (b.price ?? 0),
      render: (value: number | null, record: HKStockQuote) => (
        <span
          className="financial-num"
          style={{ fontWeight: 600, color: getChangeColor(record.change_pct, colors) }}
        >
          {formatNumber(value)}
        </span>
      ),
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      key: "change_pct",
      align: "right" as const,
      sorter: (a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
      render: (value: number | null) => <ChangeValue value={value} showIcon />,
    },
    {
      title: "今开",
      dataIndex: "open",
      key: "open",
      align: "right" as const,
      responsive: ["md"],
      sorter: (a, b) => (a.open ?? 0) - (b.open ?? 0),
      render: (value: number | null) => <span className="financial-num" style={{ color: colors.textPrimary }}>{formatNumber(value)}</span>,
    },
    {
      title: "最高",
      dataIndex: "high",
      key: "high",
      align: "right" as const,
      responsive: ["md"],
      sorter: (a, b) => (a.high ?? 0) - (b.high ?? 0),
      render: (value: number | null) => <span className="financial-num" style={{ color: colors.textPrimary }}>{formatNumber(value)}</span>,
    },
    {
      title: "最低",
      dataIndex: "low",
      key: "low",
      align: "right" as const,
      responsive: ["md"],
      sorter: (a, b) => (a.low ?? 0) - (b.low ?? 0),
      render: (value: number | null) => <span className="financial-num" style={{ color: colors.textPrimary }}>{formatNumber(value)}</span>,
    },
    {
      title: "成交额",
      dataIndex: "amount",
      key: "amount",
      align: "right" as const,
      responsive: ["lg"],
      sorter: (a, b) => (a.amount ?? 0) - (b.amount ?? 0),
      render: (value: number | null) => <span className="financial-num" style={{ color: colors.textPrimary }}>{formatAmount(value)}</span>,
    },
    {
      title: "操作",
      key: "actions",
      align: "center" as const,
      width: 72,
      render: (_: unknown, record: HKStockQuote) => (
        <Button
          type="link"
          size="small"
          icon={<LineChartOutlined />}
          aria-label={`查看${record.name}走势`}
          onClick={(e) => {
            e.stopPropagation();
            handleStockRowClick(record);
          }}
        >
          走势
        </Button>
      ),
    },
  ];

  const handleSelectionChange: NonNullable<TableProps<HKStockQuote>["rowSelection"]>["onChange"] = (keys, rows) => {
    const stockByCode = new Map(selectedStocks.map((stock) => [stock.code, stock]));
    rows.forEach((stock) => stockByCode.set(stock.code, stock));
    setSelectedStocks(
      keys
        .map((key) => stockByCode.get(String(key)))
        .filter((stock): stock is HKStockQuote => stock != null)
        .slice(0, MAX_COMPARE_STOCKS),
    );
  };

  const selectSearchItem = (code: string) => {
    const stock = searchItems.find((item: HKStockSearchItem) => item.code === code);
    if (stock) {
      setSearch(stock.name);
      setSelectedSearchValue(stock.name.trim());
      setActiveStock(stock);
      onStockSelect?.(stock.code);
    }
  };

  const handleSearchChange = (value: string) => {
    setSelectedSearchValue(null);
    setSearch(value);
  };

  const handleStockRowClick = (record: HKStockQuote) => {
    setActiveStock(record);
    onStockSelect?.(record.code);
  };

  const handleCloseStock = () => {
    setActiveStock(null);
    onStockSelect?.(null);
  };

  const removeSelectedStock = (stockCode: string) => {
    setSelectedStocks((current) => current.filter((stock) => stock.code !== stockCode));
  };

  const handleRefreshAll = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        indicesQuery.refetch(),
        stocksQuery.refetch(),
        indexHistoryQuery.refetch(),
        activeStock ? stockHistoryQuery.refetch() : Promise.resolve(),
      ]);
      message.success("港股实时行情已更新");
    } finally {
      setIsRefreshing(false);
    }
  };

  const addSelectedToWatchlist = async () => {
    let added = 0;
    for (const stock of selectedStocks) {
      try {
        await addWatchlistItem.mutateAsync({
          stock_code: stock.code,
          market: "hk",
          note: "",
        });
        added += 1;
      } catch {
        // Continue adding the remaining selected stocks and report a combined result.
      }
    }
    const failed = selectedStocks.length - added;
    if (failed === 0) {
      message.success(`已将 ${added} 只港股加入自选`);
    } else if (added > 0) {
      message.warning(`已加入 ${added} 只，${failed} 只添加失败`);
    } else {
      message.error("所选港股加入自选失败");
    }
  };

  return (
    <div style={embedded ? undefined : pageContainerStyle} className="hk-market-page">
      <div style={embedded ? { marginBottom: 12 } : pageHeaderStyle} className="hk-market-header">
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={embedded ? 4 : 3} style={pageTitleStyle}>港股行情</Title>
            <Tag color="green" className="hk-live-tag">
              <span className="hk-live-dot" />
              Sina 实时
            </Tag>
          </div>
          <Paragraph style={pageDescriptionStyle}>港股核心指数与个股的实时行情、历史 K 线及复权走势。</Paragraph>
        </div>
        <div className="hk-market-header-actions">
          <Button
            icon={<ReloadOutlined spin={isRefreshing} />}
            loading={isRefreshing}
            onClick={() => void handleRefreshAll()}
          >
            刷新行情
          </Button>
        </div>
      </div>

      <SectionDataState
        isLoading={indicesQuery.isLoading && indices.length === 0}
        error={indices.length ? undefined : indicesQuery.error}
        onRetry={() => indicesQuery.refetch()}
        isEmpty={indices.length === 0}
        emptyText="暂无港股指数数据"
        errorTitle="港股指数加载失败"
        minHeight={150}
      >
        <Row gutter={[16, 16]} className="hk-index-grid">
          {indices.map((index) => {
            const active = index.code === activeIndex;
            return (
              <Col xs={24} sm={8} key={index.code}>
                <button
                  type="button"
                  className={`hk-index-button${active ? " is-active" : ""}`}
                  onClick={() => setActiveIndex(index.code)}
                  aria-pressed={active}
                >
                  <Card hoverable styles={{ body: { padding: tokens.space[4] } }}>
                    <div className="hk-index-card-head">
                      <span
                        className="hk-index-name"
                        style={{ color: active ? colors.primary : colors.textPrimary }}
                      >
                        {index.name}
                      </span>
                      <span className="hk-index-code-badge">{index.code}</span>
                    </div>
                    <div
                      className="hk-index-price"
                      style={{ color: getChangeColor(index.change_pct, colors) }}
                    >
                      {formatNumber(index.price)}
                    </div>
                    <div className="hk-index-change-wrap">
                      <ChangeValue value={index.change_pct} showIcon />
                    </div>
                    <div className="hk-index-mini-stats">
                      <span>今开 {formatNumber(index.open)}</span>
                      <span>最高 {formatNumber(index.high)}</span>
                      <span>最低 {formatNumber(index.low)}</span>
                    </div>
                  </Card>
                </button>
              </Col>
            );
          })}
        </Row>
      </SectionDataState>

      <Card
        className="hk-section-card"
        title={
          <div className="hk-card-title-group">
            <span style={{ fontWeight: 600, color: colors.textPrimary }}>{activeIndexObj?.name ?? activeIndex} · 历史行情</span>
            {activeIndexObj?.price != null && (
              <Tag color={getChangeColor(activeIndexObj.change_pct, colors)}>
                最新: {formatNumber(activeIndexObj.price)}
              </Tag>
            )}
          </div>
        }
        extra={
          <Space wrap>
            <Segmented
              aria-label="指数K线周期"
              options={PERIOD_OPTIONS}
              value={indexPeriod}
              onChange={(value) => setIndexPeriod(String(value))}
            />
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              aria-label="全屏查看指数行情"
              onClick={() => setIndexChartExpanded(true)}
            />
          </Space>
        }
      >
        <SectionDataState
          isLoading={indexHistoryQuery.isLoading}
          error={indexHistoryQuery.error}
          onRetry={() => indexHistoryQuery.refetch()}
          isEmpty={!indexHistoryQuery.data?.items.length}
          emptyText="暂无指数历史行情"
          minHeight={360}
        >
          <LazyKlineChart
            data={chartItems(indexHistoryQuery.data?.items)}
            height={360}
            viewKey={`hk-index-${activeIndex}-${indexPeriod}`}
          />
        </SectionDataState>
      </Card>

      {/* ── 选中个股走势卡片（置于列表上方，点击后立刻可见） ── */}
      {activeStock && (
        <Card
          className="hk-section-card hk-active-stock-card"
          title={
            <div className="hk-card-title-group">
              <span style={{ fontWeight: 600, color: colors.textPrimary }}>{activeStock.name}</span>
              <Tag color="blue">{activeStock.code}</Tag>
              {activeStockQuote?.price != null && (
                <span
                  className="financial-num"
                  style={{
                    fontWeight: 700,
                    fontSize: 16,
                    color: getChangeColor(activeStockQuote.change_pct, colors),
                  }}
                >
                  {formatNumber(activeStockQuote.price)}
                </span>
              )}
              {activeStockQuote?.change_pct != null && (
                <ChangeValue value={activeStockQuote.change_pct} showIcon />
              )}
            </div>
          }
          extra={
            <Space wrap>
              <Segmented
                aria-label="个股K线周期"
                options={PERIOD_OPTIONS}
                value={stockPeriod}
                onChange={(value) => setStockPeriod(String(value))}
              />
              <Segmented
                aria-label="复权方式"
                options={ADJUST_OPTIONS}
                value={adjust}
                onChange={(value) => setAdjust(String(value))}
              />
              <Button
                type="text"
                size="small"
                icon={<FullscreenOutlined />}
                aria-label="全屏查看个股走势"
                onClick={() => setStockChartExpanded(true)}
              />
              <Button
                type="text"
                size="small"
                icon={<CloseOutlined />}
                onClick={handleCloseStock}
                aria-label="关闭个股行情"
              />
            </Space>
          }
        >
          {activeStockQuote && (
            <div className="hk-active-stock-stats">
              <div className="hk-metric-item">
                <span className="hk-metric-label">今开</span>
                <span className="hk-metric-value">{formatNumber(activeStockQuote.open)}</span>
              </div>
              <div className="hk-metric-item">
                <span className="hk-metric-label">昨收</span>
                <span className="hk-metric-value">{formatNumber(activeStockQuote.pre_close)}</span>
              </div>
              <div className="hk-metric-item">
                <span className="hk-metric-label">最高</span>
                <span className="hk-metric-value" style={{ color: colors.up }}>
                  {formatNumber(activeStockQuote.high)}
                </span>
              </div>
              <div className="hk-metric-item">
                <span className="hk-metric-label">最低</span>
                <span className="hk-metric-value" style={{ color: colors.down }}>
                  {formatNumber(activeStockQuote.low)}
                </span>
              </div>
              <div className="hk-metric-item">
                <span className="hk-metric-label">成交额</span>
                <span className="hk-metric-value">{formatAmount(activeStockQuote.amount)}</span>
              </div>
              <div className="hk-metric-item">
                <span className="hk-metric-label">成交量</span>
                <span className="hk-metric-value">{formatAmount(activeStockQuote.volume)}</span>
              </div>
            </div>
          )}

          <SectionDataState
            isLoading={stockHistoryQuery.isLoading}
            error={stockHistoryQuery.error}
            onRetry={() => stockHistoryQuery.refetch()}
            isEmpty={!stockHistoryQuery.data?.items.length}
            emptyText="暂无个股历史行情"
            minHeight={380}
          >
            <LazyKlineChart
              data={chartItems(stockHistoryQuery.data?.items)}
              height={380}
              viewKey={`hk-stock-${activeStock.code}-${stockPeriod}-${adjust}`}
            />
          </SectionDataState>
        </Card>
      )}

      {/* ── 港股个股行情与筛选 ── */}
      <Card
        className="hk-section-card"
        title={<span style={{ color: colors.textPrimary, fontWeight: 600 }}>港股实时行情</span>}
        extra={
          <AutoComplete
            className="hk-stock-search"
            value={search}
            options={searchOptions}
            onChange={handleSearchChange}
            onSelect={selectSearchItem}
            filterOption={false}
            notFoundContent={
              isSearchPending
                ? "搜索中..."
                : stockSearchQuery.isError
                  ? "搜索失败，请稍后重试"
                  : normalizedSearch
                    ? "未找到匹配港股"
                    : undefined
            }
          >
            <Input
              allowClear
              aria-busy={isSearchPending}
              aria-label="搜索港股"
              prefix={<SearchOutlined />}
              placeholder="搜索代码、中英文名称"
            />
          </AutoComplete>
        }
      >
        <div className="hk-toolbar-container">
          <div className="hk-filter-bar">
            <div className="hk-quick-filters">
              <Text type="secondary" style={{ fontSize: 13, marginRight: 4, color: colors.textSecondary }}>快速排序：</Text>
              <Segmented
                options={SORT_OPTIONS as unknown as string[]}
                value={sortOption}
                onChange={(val) => setSortOption(val as SortOption)}
              />
            </div>
          </div>

          <div className="hk-selection-toolbar">
            <div className="hk-selection-summary">
              <Text strong style={{ color: colors.textPrimary }}>已选 {selectedStocks.length}/{MAX_COMPARE_STOCKS}</Text>
              <div className="hk-selection-tags" aria-label="已选港股">
                {selectedStocks.map((stock) => (
                  <Tag
                    key={stock.code}
                    closable
                    onClose={(event) => {
                      event.preventDefault();
                      removeSelectedStock(stock.code);
                    }}
                    style={{
                      background: colors.cardBg,
                      borderColor: colors.border,
                      color: colors.textSecondary,
                    }}
                  >
                    {stock.name} {stock.code}
                  </Tag>
                ))}
              </div>
            </div>
            <Space wrap>
              <Button disabled={selectedStocks.length === 0} onClick={() => setSelectedStocks([])}>清空</Button>
              <Button
                type="primary"
                icon={<StarOutlined />}
                disabled={selectedStocks.length === 0}
                loading={addWatchlistItem.isPending}
                onClick={() => void addSelectedToWatchlist()}
              >
                加入自选
              </Button>
            </Space>
          </div>
        </div>

        <SectionDataState
          isLoading={stocksQuery.isLoading && !stocksQuery.data}
          error={stocksQuery.error}
          onRetry={() => stocksQuery.refetch()}
          isEmpty={displayStocks.length === 0}
          emptyText="没有匹配的港股"
          errorTitle="港股实时行情加载失败"
          minHeight={320}
        >
          <Table<HKStockQuote>
            rowKey="code"
            size="small"
            columns={columns}
            dataSource={displayStocks}
            pagination={false}
            scroll={{ x: 800 }}
            rowSelection={{
              selectedRowKeys: selectedCodes,
              preserveSelectedRowKeys: true,
              onChange: handleSelectionChange,
              getCheckboxProps: (record) => ({
                disabled: selectedStocks.length >= MAX_COMPARE_STOCKS && !selectedCodes.includes(record.code),
                "aria-label": `选择${record.name}`,
              }),
            }}
            rowClassName={(record) => record.code === activeStock?.code ? "hk-stock-row-selected" : ""}
            onRow={(record) => ({
              onClick: () => handleStockRowClick(record),
              tabIndex: 0,
              onKeyDown: (event) => {
                if (event.key === "Enter") handleStockRowClick(record);
              },
            })}
          />
          {(stocksQuery.data?.total ?? 0) > pageSize && (
            <Pagination
              current={page}
              pageSize={pageSize}
              total={stocksQuery.data?.total ?? 0}
              showSizeChanger={false}
              onChange={setPage}
              className="hk-pagination"
            />
          )}
        </SectionDataState>
      </Card>

      {/* ── 港股对比 ── */}
      {selectedStocks.length > 0 && (
        <Card className="hk-section-card hk-compare-card" title={`港股对比 · ${selectedStocks.length} 只`}>
          <Table<HKStockQuote>
            rowKey="code"
            size="small"
            columns={columns}
            dataSource={selectedStocks}
            pagination={false}
            scroll={{ x: 760 }}
          />
        </Card>
      )}

      {/* ── 指数全屏模态框 ── */}
      <Modal
        title={`${activeIndexObj?.name ?? activeIndex} · ${indexPeriod === "daily" ? "日K" : indexPeriod === "weekly" ? "周K" : "月K"}线全屏`}
        open={indexChartExpanded}
        onCancel={() => setIndexChartExpanded(false)}
        footer={null}
        width="90vw"
        styles={{ body: { height: "72vh" } }}
      >
        <LazyKlineChart
          data={chartItems(indexHistoryQuery.data?.items)}
          height={560}
          viewKey={`hk-index-modal-${activeIndex}-${indexPeriod}`}
        />
      </Modal>

      {/* ── 个股全屏模态框 ── */}
      {activeStock && (
        <Modal
          title={`${activeStock.name}（${activeStock.code}）· ${stockPeriod === "daily" ? "日K" : stockPeriod === "weekly" ? "周K" : "月K"}线全屏`}
          open={stockChartExpanded}
          onCancel={() => setStockChartExpanded(false)}
          footer={null}
          width="90vw"
          styles={{ body: { height: "72vh" } }}
        >
          <LazyKlineChart
            data={chartItems(stockHistoryQuery.data?.items)}
            height={560}
            viewKey={`hk-stock-modal-${activeStock.code}-${stockPeriod}-${adjust}`}
          />
        </Modal>
      )}
    </div>
  );
}
