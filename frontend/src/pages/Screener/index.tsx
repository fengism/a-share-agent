import { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Button, Card, Typography } from "antd";
import { useSearchParams } from "react-router-dom";
import { useScreenerScreen, useIndustries, useComputePercentiles } from "../../api/queries";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import SectionDataState from "../../components/SectionDataState";
import FilterPanel from "./FilterPanel";
import ResultsTable from "./ResultsTable";
import type { ScreenerFilter } from "../../types/stock";
import { useStyles } from "../../styles/ui";
import {
  DEFAULT_SCREENER_FILTERS,
  parseScreenerUrlState,
  serializeScreenerUrlState,
  type ScreenerUrlState,
} from "./screenerUrlState";

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

const { Title, Paragraph } = Typography;

export default function Screener() {
  const [searchParams, setSearchParams] = useSearchParams();
  const appliedState = useMemo(() => parseScreenerUrlState(searchParams), [searchParams]);
  const [filters, setFilters] = useState<ScreenerFilter>(appliedState.filters);
  const [percentileMap, setPercentileMap] = useState<Map<string, number | null>>(new Map());
  const { showPercentile, pePercentileMax, pbPercentileMax } = appliedState;

  const {
    data: industries = [],
    error: industriesError,
    refetch: refetchIndustries,
  } = useIndustries();
  const { cardStyle, pageContainerStyle, pageDescriptionStyle, pageHeaderStyle, pageTitleStyle, sectionCardBodyStyle } = useStyles();
  const {
    data: screenerResult,
    isLoading: screenerLoading,
    isFetching,
    error: screenerError,
    refetch: refetchScreener,
  } = useScreenerScreen(appliedState.filters, true);
  const { mutate: computePercentiles, isPending: isPercentilePending } = useComputePercentiles();

  const commitUrlState = useCallback((nextState: ScreenerUrlState) => {
    const nextParams = serializeScreenerUrlState(nextState);
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    setFilters(appliedState.filters);
  }, [appliedState.filters]);

  // 自动搜索（防抖）
  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      commitUrlState({ ...appliedState, filters: { ...filters } });
    }, 300);
    return () => window.clearTimeout(timeoutId);
  }, [appliedState, commitUrlState, filters]);

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
    commitUrlState({ ...appliedState, filters: { ...filters } });
  }, [appliedState, commitUrlState, filters]);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_SCREENER_FILTERS);
    commitUrlState({
      filters: DEFAULT_SCREENER_FILTERS,
      showPercentile: false,
      pePercentileMax: 50,
      pbPercentileMax: 50,
    });
    setPercentileMap(new Map());
  }, [commitUrlState]);

  const handlePageChange = useCallback((page: number, pageSize: number) => {
    const newFilters = { ...filters, page, page_size: pageSize };
    setFilters(newFilters);
    commitUrlState({ ...appliedState, filters: newFilters });
  }, [appliedState, commitUrlState, filters]);

  const handleSortChange = useCallback((sortBy: ScreenerFilter["sort_by"], sortOrder: ScreenerFilter["sort_order"]) => {
    const newFilters = { ...filters, sort_by: sortBy, sort_order: sortOrder, page: 1 };
    setFilters(newFilters);
    commitUrlState({ ...appliedState, filters: newFilters });
  }, [appliedState, commitUrlState, filters]);

  const handleShowPercentileChange = useCallback((value: boolean) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, showPercentile: value });
  }, [appliedState, commitUrlState, filters]);

  const handlePePercentileMaxChange = useCallback((value: number) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, pePercentileMax: value });
  }, [appliedState, commitUrlState, filters]);

  const handlePbPercentileMaxChange = useCallback((value: number) => {
    commitUrlState({ ...appliedState, filters: { ...filters }, pbPercentileMax: value });
  }, [appliedState, commitUrlState, filters]);

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
            <Button
              key={p.label}
              size="small"
              shape="round"
              style={{ fontSize: 13, fontWeight: 500 }}
              onClick={() => {
                const newFilters = { ...DEFAULT_SCREENER_FILTERS, ...p.filters, page: 1 };
                setFilters(newFilters);
                commitUrlState({ ...appliedState, filters: newFilters, showPercentile: false });
                setPercentileMap(new Map());
              }}
              title={p.description}
            >
              {p.icon} {p.label}
            </Button>
          ))}
        </div>

          <FilterPanel
            filters={filters}
            onFiltersChange={setFilters}
            industries={industries}
            onSearch={handleSearch}
            onReset={handleReset}
            showPercentile={showPercentile}
            onShowPercentileChange={handleShowPercentileChange}
            pePercentileMax={pePercentileMax}
            pbPercentileMax={pbPercentileMax}
            onPePercentileMaxChange={handlePePercentileMaxChange}
            onPbPercentileMaxChange={handlePbPercentileMaxChange}
          />
          {industriesError && industries.length === 0 && (
            <Alert
              title="行业列表加载失败，仍可使用其他筛选条件"
              type="warning"
              showIcon
              action={<Button size="small" onClick={() => refetchIndustries()}>重试</Button>}
              style={{ marginTop: 12, borderRadius: 8 }}
            />
          )}
        </Card>

        {/* Percentile loading */}
        {showPercentile && isPercentilePending && (
          <Alert
            title="正在计算估值百分位，请稍候..."
            type="info"
            showIcon
            style={{ marginBottom: 16, borderRadius: 8 }}
          />
        )}

        {/* Results */}
        <Card
          size="small"
          title={<span style={{ fontWeight: 600 }}>筛选结果 {screenerResult ? `(${screenerResult.total} 只)` : ""}</span>}
          extra={<DataRefreshIndicator active={isFetching && !!screenerResult} />}
          style={cardStyle}
          styles={{ body: { padding: "12px 18px" } }}
        >
          <SectionDataState
            isLoading={screenerLoading && !screenerResult}
            error={screenerResult ? undefined : screenerError}
            onRetry={() => refetchScreener()}
            isEmpty={!screenerLoading && !screenerError && !screenerResult}
            emptyText="暂无筛选结果"
            errorTitle="筛选结果加载失败"
            minHeight={320}
          >
            <ResultsTable
              data={displayData}
              isLoading={screenerLoading && !screenerResult}
              percentileMap={percentileMap}
              showPercentile={showPercentile}
              onPageChange={handlePageChange}
              filters={appliedState.filters}
              onSortChange={handleSortChange}
            />
          </SectionDataState>
        </Card>
    </div>
  );
}
