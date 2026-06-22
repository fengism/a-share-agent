import { useState, useCallback, useEffect, useRef } from "react";
import { Card, Alert, Tag, Typography } from "antd";
import { useScreenerScreen, useIndustries, useComputePercentiles } from "../../api/queries";
import FilterPanel from "./FilterPanel";
import ResultsTable from "./ResultsTable";
import type { ScreenerFilter } from "../../types/stock";
import { useStyles } from "../../styles/ui";

interface PresetStrategy {
  label: string;
  description: string;
  icon: string;
  filters: Partial<ScreenerFilter>;
}

const PRESET_STRATEGIES: PresetStrategy[] = [
  {
    label: "低估值蓝筹",
    description: "PE<15 · PB<2 · 市值>200亿",
    icon: "🛡️",
    filters: { pe_min: 0, pe_max: 15, pb_min: 0, pb_max: 2, market_cap_min: 200, market_cap_max: null, sort_by: "market_cap", sort_order: "desc" },
  },
  {
    label: "破净股",
    description: "PB<1 · 市值>50亿",
    icon: "💎",
    filters: { pb_min: 0, pb_max: 1, market_cap_min: 50, market_cap_max: null, sort_by: "pb", sort_order: "asc" },
  },
  {
    label: "高成长活跃",
    description: "涨跌幅>2% · 换手率>3%",
    icon: "🚀",
    filters: { change_pct_min: 2, change_pct_max: null, turnover_pct_min: 3, turnover_pct_max: null, sort_by: "change_pct", sort_order: "desc" },
  },
  {
    label: "低价活跃股",
    description: "股价<10 · 换手率>5%",
    icon: "⚡",
    filters: { price_min: 0, price_max: 10, turnover_pct_min: 5, turnover_pct_max: null, sort_by: "turnover_pct", sort_order: "desc" },
  },
  {
    label: "绩优蓝筹",
    description: "PE 5-30 · PB 1-8 · 市值>500亿",
    icon: "🏆",
    filters: { pe_min: 5, pe_max: 30, pb_min: 1, pb_max: 8, market_cap_min: 500, market_cap_max: null, sort_by: "market_cap", sort_order: "desc" },
  },
];

const DEFAULT_FILTERS: ScreenerFilter = {
  sort_by: "market_cap",
  sort_order: "desc",
  page: 1,
  page_size: 50,
};

const { Title, Paragraph } = Typography;

export default function Screener() {
  const [filters, setFilters] = useState<ScreenerFilter>(DEFAULT_FILTERS);
  const [searchFilters, setSearchFilters] = useState<ScreenerFilter | null>(null);
  const [showPercentile, setShowPercentile] = useState(false);
  const [pePercentileMax, setPePercentileMax] = useState(50);
  const [pbPercentileMax, setPbPercentileMax] = useState(50);
  const [percentileMap, setPercentileMap] = useState<Map<string, number | null>>(new Map());
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  const { data: industries = [] } = useIndustries();
  const { cardStyle, pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle, sectionCardBodyStyle } = useStyles();
  const { data: screenerResult, isLoading: screenerLoading, isFetching } = useScreenerScreen(
    searchFilters || DEFAULT_FILTERS,
    searchFilters !== null,
  );
  const { mutate: computePercentiles, isPending: isPercentilePending } = useComputePercentiles();

  // 自动搜索（防抖）
  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setSearchFilters({ ...filters });
    }, 300);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [filters]);

  // 百分位计算
  useEffect(() => {
    if (!showPercentile || !screenerResult?.items?.length) {
      setPercentileMap(new Map());
      return;
    }

    const codes = screenerResult.items.map((item) => item.code);
    setPercentileMap(new Map());

    computePercentiles(
      { codes, period: "近三年", indicator: "市盈率(TTM)" },
      {
        onSuccess: (result) => {
          const map = new Map<string, number | null>();
          for (const item of result.items) {
            map.set(item.code, item.percentile);
          }
          setPercentileMap(map);
        },
      },
    );

    computePercentiles(
      { codes, period: "近三年", indicator: "市净率" },
      {
        onSuccess: (result) => {
          setPercentileMap((prev) => {
            const map = new Map(prev);
            for (const item of result.items) {
              map.set(item.code + "_pb", item.percentile);
            }
            return map;
          });
        },
      },
    );
  }, [computePercentiles, showPercentile, screenerResult?.items]);

  const handleSearch = useCallback(() => {
    setSearchFilters({ ...filters });
  }, [filters]);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
    setSearchFilters(DEFAULT_FILTERS);
    setShowPercentile(false);
    setPePercentileMax(50);
    setPbPercentileMax(50);
    setPercentileMap(new Map());
  }, []);

  const handlePageChange = useCallback((page: number, pageSize: number) => {
    const newFilters = { ...filters, page, page_size: pageSize };
    setFilters(newFilters);
    setSearchFilters(newFilters);
  }, [filters]);

  const handleSortChange = useCallback((sortBy: ScreenerFilter["sort_by"], sortOrder: ScreenerFilter["sort_order"]) => {
    const newFilters = { ...filters, sort_by: sortBy, sort_order: sortOrder, page: 1 };
    setFilters(newFilters);
    setSearchFilters(newFilters);
  }, [filters]);

  // 百分位过滤（客户端）
  const filteredItems = showPercentile && percentileMap.size > 0
    ? screenerResult?.items.filter((item) => {
        const peP = percentileMap.get(item.code);
        const pbP = percentileMap.get(item.code + "_pb");
        return (peP == null || peP <= pePercentileMax) && (pbP == null || pbP <= pbPercentileMax);
      })
    : screenerResult?.items;

  const displayData = filteredItems
    ? { ...screenerResult!, items: filteredItems, total: filteredItems.length }
    : screenerResult;

  return (
    <div style={pageContainerStyle}>
        <div style={pageHeaderStyle}>
          <Title level={3} style={pageTitleStyle}>智能选股</Title>
          <Paragraph style={pageDescriptionStyle}>按估值、价格、涨跌幅和行业等维度筛选股票，快速定位候选标的。</Paragraph>
        </div>
        {/* Filter Panel */}
        <Card
          size="small"
          title={<span style={{ fontWeight: 600 }}>筛选条件</span>}
          style={{ ...cardStyle, marginBottom: 16 }}
          styles={{ body: sectionCardBodyStyle }}
        >
        {/* Preset strategies */}
        <div style={{ marginBottom: 14, display: "flex", flexWrap: "wrap", gap: 8 }}>
          {PRESET_STRATEGIES.map((p) => (
            <Tag
              key={p.label}
              style={{ cursor: "pointer", padding: "4px 14px", borderRadius: 999, fontSize: 13, fontWeight: 500, border: "none", transition: "all 0.2s" }}
              color="blue"
              onClick={() => {
                const newFilters = { ...DEFAULT_FILTERS, ...p.filters, page: 1 };
                setFilters(newFilters);
                setSearchFilters(newFilters);
                setShowPercentile(false);
                setPercentileMap(new Map());
              }}
              title={p.description}
            >
              {p.icon} {p.label}
            </Tag>
          ))}
        </div>

          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            industries={industries}
            onSearch={handleSearch}
            onReset={handleReset}
            showPercentile={showPercentile}
            onShowPercentileChange={setShowPercentile}
            pePercentileMax={pePercentileMax}
            pbPercentileMax={pbPercentileMax}
            onPePercentileMaxChange={setPePercentileMax}
            onPbPercentileMaxChange={setPbPercentileMax}
          />
        </Card>

        {/* Percentile loading */}
        {showPercentile && isPercentilePending && (
          <Alert
            message="正在计算估值百分位，请稍候..."
            type="info"
            showIcon
            style={{ marginBottom: 16, borderRadius: 8 }}
          />
        )}

        {/* Results */}
        <Card
          size="small"
          title={<span style={{ fontWeight: 600 }}>筛选结果 {screenerResult ? `(${screenerResult.total} 只)` : ""}</span>}
          style={cardStyle}
          styles={{ body: { padding: "12px 18px" } }}
        >
          <ResultsTable
            data={displayData}
            isLoading={screenerLoading || isFetching}
            percentileMap={percentileMap}
            showPercentile={showPercentile}
            onPageChange={handlePageChange}
            filters={filters}
            onSortChange={handleSortChange}
          />
        </Card>
    </div>
  );
}
