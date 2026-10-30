import {
  AppstoreOutlined,
  BarsOutlined,
  DownloadOutlined,
  DownOutlined,
  FilterOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { useEffect, useRef, useState } from "react";
import { Alert, Button, Card, Drawer, Dropdown, InputNumber, message, Modal, Progress, Radio, Space, Tag, Tooltip, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { fetchScreenerExportData, useIndustries, useRunScreenerStrategy, useScreenerConcepts, useScreenerScreen, useScreenerStrategies } from "../../api/queries";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import PageShell, { PageHeader } from "../../components/page/PageShell";
import SectionDataState from "../../components/SectionDataState";
import { useAuthStore } from "../../store/authStore";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useStyles } from "../../styles/ui";
import type { ScreenerFilter, ScreenerItem, ScreenerStrategyPreset } from "../../types/stock";
import { downloadScreenerCsv } from "./exportCsv";
import FilterPanel from "./FilterPanel";
import ResultsTable from "./ResultsTable";
import SavedFilterToolbar from "./SavedFilterToolbar";
import ScreenerBatchActions from "./ScreenerBatchActions";
import ScreenerPoolInsightsBar from "./ScreenerPoolInsightsBar";
import ScreenerCardList from "./ScreenerCardList";
import StrategyResultInsightBar from "./StrategyResultInsightBar";
import { useScreenerBatchController } from "./useScreenerBatchController";
import { useScreenerFilterController } from "./useScreenerFilterController";
import { useScreenerPercentiles } from "./useScreenerPercentiles";

interface PresetStrategy {
  label: string;
  description: string;
  icon: string;
  filters: Partial<ScreenerFilter>;
}

function isPresetActive(presetFilters: Partial<ScreenerFilter>, currentFilters: ScreenerFilter): boolean {
  const keys = Object.keys(presetFilters) as (keyof ScreenerFilter)[];
  if (keys.length === 0) return false;
  return keys.every((key) => {
    if (key === "sort_by" || key === "sort_order" || key === "page" || key === "page_size") {
      return true;
    }
    const presetVal = presetFilters[key];
    const currentVal = currentFilters[key];
    if (presetVal === null || presetVal === undefined) {
      return currentVal === null || currentVal === undefined;
    }
    return currentVal === presetVal;
  });
}

const PRESET_STRATEGIES: PresetStrategy[] = [
  { label: "低估值蓝筹", description: "PE<15 · PB<2 · 市值>200亿", icon: "🛡️", filters: { pe_min: 0, pe_max: 15, pb_min: 0, pb_max: 2, market_cap_min: 200, market_cap_max: null, sort_by: "market_cap", sort_order: "desc" } },
  { label: "破净股", description: "PB<1 · 市值>50亿", icon: "💎", filters: { pb_min: 0, pb_max: 1, market_cap_min: 50, market_cap_max: null, sort_by: "pb", sort_order: "asc" } },
  { label: "大盘核心", description: "市值>500亿 · PE<25", icon: "👑", filters: { market_cap_min: 500, market_cap_max: null, pe_min: 0, pe_max: 25, sort_by: "market_cap", sort_order: "desc" } },
  { label: "高成长活跃", description: "涨跌幅>2% · 换手率>3%", icon: "🚀", filters: { change_pct_min: 2, change_pct_max: null, turnover_pct_min: 3, turnover_pct_max: null, sort_by: "change_pct", sort_order: "desc" } },
  { label: "放量突破", description: "换手率>5% · 涨跌幅>3%", icon: "💥", filters: { turnover_pct_min: 5, turnover_pct_max: null, change_pct_min: 3, change_pct_max: null, sort_by: "turnover_pct", sort_order: "desc" } },
  { label: "低价活跃股", description: "股价<10 · 换手率>5%", icon: "⚡", filters: { price_min: 0, price_max: 10, turnover_pct_min: 5, turnover_pct_max: null, sort_by: "turnover_pct", sort_order: "desc" } },
  { label: "绩优蓝筹", description: "PE 5-30 · PB 1-8 · 市值>500亿", icon: "🏆", filters: { pe_min: 5, pe_max: 30, pb_min: 1, pb_max: 8, market_cap_min: 500, market_cap_max: null, sort_by: "market_cap", sort_order: "desc" } },
];

const STRATEGY_SETTINGS_STORAGE_KEY = "screener-strategy-settings";

interface StoredStrategySettings {
  strategyKey?: string;
  parameters: Record<string, number | boolean | string>;
  maxSignalAgeBars: number | null;
  scanLimit: 50 | 200;
}

function defaultStrategySettings(): StoredStrategySettings {
  return {
    parameters: {},
    maxSignalAgeBars: 20,
    scanLimit: 50,
  };
}

function strategySettingsStorageKey(userId?: number): string | undefined {
  return userId == null ? undefined : `${STRATEGY_SETTINGS_STORAGE_KEY}:user:${userId}`;
}

function parseStrategySettings(raw: string | null): StoredStrategySettings {
  const defaults = defaultStrategySettings();
  if (raw == null) return defaults;
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object") return defaults;
  return {
    strategyKey: typeof parsed.strategyKey === "string" ? parsed.strategyKey : undefined,
    parameters: parsed.parameters && typeof parsed.parameters === "object" && !Array.isArray(parsed.parameters)
      ? parsed.parameters
      : {},
    maxSignalAgeBars: parsed.maxSignalAgeBars === null
      ? null
      : Number.isInteger(parsed.maxSignalAgeBars) && parsed.maxSignalAgeBars >= 0 && parsed.maxSignalAgeBars <= 250
        ? parsed.maxSignalAgeBars
        : defaults.maxSignalAgeBars,
    scanLimit: parsed.scanLimit === 200 ? 200 : 50,
  };
}

function loadStrategySettings(storageKey?: string): StoredStrategySettings {
  if (typeof window === "undefined" || !storageKey) return defaultStrategySettings();
  try {
    const scopedRaw = window.localStorage.getItem(storageKey);
    if (scopedRaw != null) return parseStrategySettings(scopedRaw);

    const legacyRaw = window.localStorage.getItem(STRATEGY_SETTINGS_STORAGE_KEY);
    const settings = parseStrategySettings(legacyRaw);
    if (legacyRaw != null) {
      window.localStorage.setItem(storageKey, JSON.stringify(settings));
      window.localStorage.removeItem(STRATEGY_SETTINGS_STORAGE_KEY);
    }
    return settings;
  } catch {
    return defaultStrategySettings();
  }
}

function restoreStrategyParameters(
  strategy: ScreenerStrategyPreset,
  stored: Record<string, number | boolean | string>,
) {
  return Object.fromEntries(strategy.parameter_definitions.map((definition) => {
    const saved = stored[definition.key];
    const isValidNumber = typeof saved === "number"
      && Number.isFinite(saved)
      && (definition.type !== "integer" || Number.isInteger(saved))
      && (definition.minimum == null || saved >= definition.minimum)
      && (definition.maximum == null || saved <= definition.maximum);
    const isValidValue = typeof definition.default === "number"
      ? isValidNumber
      : typeof saved === typeof definition.default;
    return [definition.key, isValidValue ? saved : definition.default];
  }));
}

export default function Screener() {
  const userId = useAuthStore((state) => state.user?.id);
  const strategyStorageKey = strategySettingsStorageKey(userId);
  const navigate = useNavigate();
  const filters = useScreenerFilterController();
  const batch = useScreenerBatchController();
  const strategies = useScreenerStrategies();
  const runStrategy = useRunScreenerStrategy();
  const [strategyResult, setStrategyResult] = useState<{
    name: string;
    version: string;
    hash: string;
    matchedCodes: string[];
    matchedItems: ScreenerItem[];
    signalDates: Map<string, string>;
    signalAges: Map<string, number>;
    returnsSinceSignal: Map<string, number | null>;
    averageAmounts: Map<string, number | null>;
    dataSources: Map<string, string>;
    fallbackCodes: Set<string>;
    evaluated: number;
    failed: number;
    excluded: Record<string, string>;
    fallbackCount: number;
  }>();
  const [showMatchedOnly, setShowMatchedOnly] = useState(false);
  const [excludedDetailsOpen, setExcludedDetailsOpen] = useState(false);
  const [selectedStrategyKey, setSelectedStrategyKey] = useState<string>();
  const [strategyParameters, setStrategyParameters] = useState<Record<string, number | boolean | string>>({});
  const [maxSignalAgeBars, setMaxSignalAgeBars] = useState<number | null>(20);
  const [scanLimit, setScanLimit] = useState<50 | 200>(50);
  const [strategyProgress, setStrategyProgress] = useState<{ completed: number; total: number; matched: number; excluded: number; failed: number }>();
  const [strategySettingsRestored, setStrategySettingsRestored] = useState(false);
  const [restoredStrategyStorageKey, setRestoredStrategyStorageKey] = useState<string>();
  const [cancelStrategy, setCancelStrategy] = useState<(() => void)>();
  const { data: industries = [], error: industriesError, refetch: refetchIndustries } = useIndustries();
  const { data: concepts = [] } = useScreenerConcepts();
  const {
    data: screenerResult,
    isLoading: screenerLoading,
    isFetching,
    error: screenerError,
    refetch: refetchScreener,
  } = useScreenerScreen(filters.appliedState.filters, true);
  const activeStrategyCancelRef = useRef<(() => void) | undefined>();
  const activeStrategyRunRef = useRef(0);
  const appliedFilterSignature = JSON.stringify(filters.appliedState.filters);
  const previousFilterSignatureRef = useRef(appliedFilterSignature);

  useEffect(() => {
    setStrategySettingsRestored(false);
    setRestoredStrategyStorageKey(undefined);
    setSelectedStrategyKey(undefined);
    setStrategyParameters({});
    setMaxSignalAgeBars(20);
    setScanLimit(50);
  }, [strategyStorageKey]);

  useEffect(() => {
    if (
      !strategyStorageKey
      || !strategies.data
      || restoredStrategyStorageKey === strategyStorageKey
    ) return;

    const settings = loadStrategySettings(strategyStorageKey);
    setMaxSignalAgeBars(settings.maxSignalAgeBars);
    setScanLimit(settings.scanLimit);

    const savedStrategy = strategies.data.find((strategy) => strategy.key === settings.strategyKey);
    if (savedStrategy) {
      setSelectedStrategyKey(savedStrategy.key);
      setStrategyParameters(restoreStrategyParameters(savedStrategy, settings.parameters));
    }
    setRestoredStrategyStorageKey(strategyStorageKey);
    setStrategySettingsRestored(true);
  }, [restoredStrategyStorageKey, strategies.data, strategyStorageKey]);

  useEffect(() => {
    if (
      !strategySettingsRestored
      || !strategyStorageKey
      || restoredStrategyStorageKey !== strategyStorageKey
      || typeof window === "undefined"
    ) return;
    const settings: StoredStrategySettings = {
      strategyKey: selectedStrategyKey,
      parameters: strategyParameters,
      maxSignalAgeBars,
      scanLimit,
    };
    window.localStorage.setItem(strategyStorageKey, JSON.stringify(settings));
  }, [
    maxSignalAgeBars,
    restoredStrategyStorageKey,
    scanLimit,
    selectedStrategyKey,
    strategyParameters,
    strategySettingsRestored,
    strategyStorageKey,
  ]);

  useEffect(() => {
    if (previousFilterSignatureRef.current === appliedFilterSignature) return;
    previousFilterSignatureRef.current = appliedFilterSignature;
    activeStrategyRunRef.current += 1;
    activeStrategyCancelRef.current?.();
    activeStrategyCancelRef.current = undefined;
    setCancelStrategy(undefined);
    setStrategyProgress(undefined);
    setStrategyResult(undefined);
    setShowMatchedOnly(false);
  }, [appliedFilterSignature]);

  useEffect(() => () => {
    activeStrategyRunRef.current += 1;
    activeStrategyCancelRef.current?.();
  }, []);

  const percentiles = useScreenerPercentiles({
    pbPercentileMax: filters.pbPercentileMax,
    pePercentileMax: filters.pePercentileMax,
    result: screenerResult,
    showPercentile: filters.showPercentile,
  });

  const [viewMode, setViewMode] = useState<"table" | "card">("table");
  const [mobileFilterDrawerOpen, setMobileFilterDrawerOpen] = useState(false);

  const handleBatchAiDiagnose = () => {
    if (batch.selectedCodes.length === 0) return;
    const selectedItems = screenerResult?.items.filter((item) => batch.selectedCodes.includes(item.code)) || [];
    const names = selectedItems.map((s) => `${s.name}(${s.code})`).join("、") || batch.selectedCodes.join("、");
    const prompt = `请对以下选中的 ${batch.selectedCodes.length} 只股票（${names}）进行横向对比诊断。重点分析：1. 各标的核心竞争壁垒与行业周期位置；2. 估值分位与性价比；3. 近期资金流向与技术形态；4. 综合投资性价比与弹性排序。`;
    navigate(`/chat?prompt=${encodeURIComponent(prompt)}`);
  };

  const handleSelectIndustryFromInsights = (industry: string) => {
    const current = filters.filters.industries || [];
    const next = current.includes(industry) ? current.filter((i) => i !== industry) : [...current, industry];
    filters.setFilters((prev) => ({
      ...prev,
      industries: next.length > 0 ? next : null,
      page: 1,
    }));
  };
  const applyHistoricalStrategy = async (strategy: ScreenerStrategyPreset) => {
    const codes = screenerResult?.items.map((item) => item.code) ?? [];
    if (scanLimit === 50 && codes.length === 0) {
      message.warning("当前页没有可执行策略的候选股票");
      return;
    }
    setStrategyResult(undefined);
    setShowMatchedOnly(false);
    setStrategyProgress(undefined);
    setCancelStrategy(undefined);
    activeStrategyCancelRef.current?.();
    activeStrategyCancelRef.current = undefined;
    const runId = activeStrategyRunRef.current + 1;
    activeStrategyRunRef.current = runId;
    try {
      const result = await runStrategy.mutateAsync({
        strategy_key: strategy.key,
        parameters: strategyParameters,
        max_signal_age_bars: maxSignalAgeBars,
        codes,
        candidate_items: screenerResult?.items ?? [],
        scan_limit: scanLimit,
        candidate_filters: filters.appliedState.filters,
        onProgress: (event) => {
          if (event.type === "progress") setStrategyProgress({
            completed: event.completed ?? 0,
            total: event.total ?? 0,
            matched: event.matched ?? 0,
            excluded: event.excluded ?? 0,
            failed: event.failed ?? 0,
          });
        },
        onStarted: (cancel) => {
          if (activeStrategyRunRef.current !== runId) {
            cancel();
            return;
          }
          activeStrategyCancelRef.current = cancel;
          setCancelStrategy(() => cancel);
          setStrategyProgress({ completed: 0, total: 0, matched: 0, excluded: 0, failed: 0 });
        },
      });
      if (activeStrategyRunRef.current !== runId) return;
      batch.setSelectedCodes(result.matched_codes.slice(0, 10));
      setStrategyResult({
        name: strategy.name,
        version: result.strategy_version,
        hash: result.definition_hash,
        matchedCodes: result.matched_codes,
        matchedItems: result.matched_items,
        signalDates: new Map(result.matches.map((match) => [match.code, match.signal_date])),
        signalAges: new Map(result.matches.map((match) => [match.code, match.signal_age_bars])),
        returnsSinceSignal: new Map(result.matches.map((match) => [match.code, match.return_since_signal_pct])),
        averageAmounts: new Map(result.matches.map((match) => [match.code, match.average_amount_20d_yi])),
        dataSources: new Map(result.matches.map((match) => [match.code, match.data_source || "-"])),
        fallbackCodes: new Set(result.matches.filter((match) => match.used_fallback).map((match) => match.code)),
        evaluated: result.evaluated,
        failed: Object.keys(result.failed).length,
        excluded: result.excluded ?? {},
        fallbackCount: result.fallback_count || 0,
      });
      setShowMatchedOnly(true);
      setStrategyProgress(undefined);
      setCancelStrategy(undefined);
      activeStrategyCancelRef.current = undefined;
    } catch (error) {
      if (activeStrategyRunRef.current !== runId) return;
      setStrategyProgress(undefined);
      setCancelStrategy(undefined);
      activeStrategyCancelRef.current = undefined;
      const detail = error instanceof Error ? error.message : "未知错误";
      if (detail === "已取消") message.info("策略扫描已取消");
      else message.error(`策略选股失败：${detail}`);
    }
  };

  const { cardStyle, sectionCardBodyStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const strategyControlsDisabled = runStrategy.isPending || isFetching;
  const displayedResult = showMatchedOnly && strategyResult
    ? {
        items: strategyResult.matchedItems,
        total: strategyResult.matchedItems.length,
        page: 1,
        page_size: Math.max(50, strategyResult.matchedItems.length),
      }
    : percentiles.displayData;

  const [isExportingAll, setIsExportingAll] = useState(false);

  const handleExportCurrent = () => {
    const items = displayedResult?.items ?? [];
    if (items.length === 0) {
      message.warning("当前没有可导出的数据");
      return;
    }
    downloadScreenerCsv({
      items,
      strategySignalDates: strategyResult?.signalDates,
      strategySignalAges: strategyResult?.signalAges,
      strategyReturnsSinceSignal: strategyResult?.returnsSinceSignal,
      strategyAverageAmounts: strategyResult?.averageAmounts,
      percentileMap: percentiles.percentileMap,
      showPercentile: filters.showPercentile,
    });
    message.success(`已导出当前页 ${items.length} 只股票数据`);
  };

  const handleExportAll = async () => {
    if (!screenerResult || screenerResult.total === 0) {
      message.warning("当前没有可导出的数据");
      return;
    }
    if (showMatchedOnly && strategyResult) {
      handleExportCurrent();
      return;
    }
    if (screenerResult.total <= (screenerResult.items?.length ?? 0)) {
      handleExportCurrent();
      return;
    }

    setIsExportingAll(true);
    try {
      const allItems = await fetchScreenerExportData(
        filters.appliedState.filters,
        Math.min(1000, screenerResult.total),
      );
      downloadScreenerCsv({
        items: allItems,
        percentileMap: percentiles.percentileMap,
        showPercentile: filters.showPercentile,
      });
      message.success(`已导出全量匹配 ${allItems.length} 只股票数据`);
    } catch {
      message.error("全量导出失败，请重试");
    } finally {
      setIsExportingAll(false);
    }
  };

  return (
    <PageShell>
      <PageHeader
        title="智能选股"
        description="按估值、价格、涨跌幅和行业等维度筛选股票，快速定位候选标的。"
      />
      <Card
        size="small"
        title={<span style={{ fontWeight: "var(--c-weight-semibold)" }}>筛选条件</span>}
        style={{ ...cardStyle, marginBottom: 16 }}
        styles={{ body: sectionCardBodyStyle }}
      >
        <div
          style={{
            marginBottom: 14,
            display: "flex",
            alignItems: "center",
            gap: 8,
            overflowX: "auto",
            whiteSpace: "nowrap",
            paddingBottom: 4,
            WebkitOverflowScrolling: "touch",
            scrollbarWidth: "none",
          }}
        >
          {PRESET_STRATEGIES.map((preset) => {
            const active = isPresetActive(preset.filters, filters.filters);
            return (
              <Button
                key={preset.label}
                size="small"
                shape="round"
                type={active ? "primary" : "default"}
                style={{ fontSize: "var(--c-font-md)", fontWeight: "var(--c-weight-medium)", flexShrink: 0 }}
                onClick={() => filters.applyPreset(preset.filters)}
                title={preset.description}
              >
                {preset.icon} {preset.label}
              </Button>
            );
          })}
        </div>
        <div style={{ marginBottom: 14 }}>
          <div style={{ marginBottom: 8, fontSize: "var(--c-font-md)", fontWeight: "var(--c-weight-semibold)" }}>历史信号选股（应用于候选范围）</div>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              overflowX: "auto",
              whiteSpace: "nowrap",
              paddingBottom: 4,
              WebkitOverflowScrolling: "touch",
              scrollbarWidth: "none",
            }}
          >
            {(strategies.data ?? []).map((strategy) => (
              <Button
                key={strategy.key}
                size="small"
                style={{ flexShrink: 0 }}
                type={selectedStrategyKey === strategy.key ? "primary" : "default"}
                disabled={strategyControlsDisabled}
                title={`${strategy.description} · ${strategy.scenario}`}
                onClick={() => {
                  setSelectedStrategyKey(strategy.key);
                  setStrategyParameters({ ...strategy.parameters });
                  setStrategyResult(undefined);
                  setShowMatchedOnly(false);
                }}
              >
                {strategy.name}
              </Button>
            ))}
          </div>
          {selectedStrategyKey ? (() => {
            const selected = (strategies.data ?? []).find((strategy) => strategy.key === selectedStrategyKey);
            if (!selected) return null;
            return (
              <div style={{ marginTop: 12, padding: 12, border: "1px solid var(--c-border)", borderRadius: 8 }}>
                <div style={{ marginBottom: 10, fontWeight: "var(--c-weight-semibold)" }}>{selected.name}参数</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "end" }}>
                  {selected.parameter_definitions.map((parameter) => (
                    <label key={parameter.key} style={{ display: "grid", gap: 4, fontSize: "var(--c-font-sm)", width: isNarrow ? "calc(50% - 6px)" : undefined }}>
                      <span>{parameter.label}</span>
                      <InputNumber
                        aria-label={parameter.label}
                        style={{ width: "100%" }}
                        value={Number(strategyParameters[parameter.key] ?? parameter.default)}
                        min={parameter.minimum ?? undefined}
                        max={parameter.maximum ?? undefined}
                        step={parameter.step ?? (parameter.type === "integer" ? 1 : 0.1)}
                        disabled={strategyControlsDisabled}
                        onChange={(value) => value == null || setStrategyParameters((current) => ({ ...current, [parameter.key]: value }))}
                      />
                    </label>
                  ))}
                  <label style={{ display: "grid", gap: 4, fontSize: "var(--c-font-sm)", width: isNarrow ? "100%" : undefined }}>
                    <span>
                      最大信号年龄（交易日K线）{" "}
                      <Tooltip title="从最近一次入场信号到最新交易日的 K 线根数；清空后不限制">
                        <InfoCircleOutlined aria-label="最大信号年龄说明" style={{ color: "var(--c-text-muted)" }} />
                      </Tooltip>
                    </span>
                    <InputNumber
                      aria-label="最大信号年龄"
                      style={{ width: "100%" }}
                      value={maxSignalAgeBars}
                      min={0}
                      max={250}
                      step={1}
                      suffix="根"
                      placeholder="不限制"
                      disabled={strategyControlsDisabled}
                      onChange={setMaxSignalAgeBars}
                    />
                  </label>
                  <Radio.Group disabled={strategyControlsDisabled} value={scanLimit} onChange={(event) => setScanLimit(event.target.value)} style={{ width: isNarrow ? "100%" : undefined }}>
                    <Radio.Button value={50} style={{ width: isNarrow ? "50%" : undefined, textAlign: "center" }}>当前页 {screenerResult?.items.length ?? 0}</Radio.Button>
                    <Radio.Button value={200} style={{ width: isNarrow ? "50%" : undefined, textAlign: "center" }}>前 200 候选</Radio.Button>
                  </Radio.Group>
                  <Button
                    type="primary"
                    block={isNarrow}
                    loading={runStrategy.isPending}
                    disabled={isFetching}
                    onClick={() => void applyHistoricalStrategy(selected)}
                  >执行策略选股</Button>
                </div>
              </div>
            );
          })() : null}
        </div>
        <SavedFilterToolbar
          state={{ ...filters.appliedState, filters: filters.filters }}
          onApply={(state) => {
            filters.applySavedFilter(state);
            batch.clearSelection();
          }}
        />
        {isNarrow ? (
          <>
            <div style={{ marginTop: 12 }}>
              <Button
                block
                icon={<FilterOutlined />}
                onClick={() => setMobileFilterDrawerOpen(true)}
              >
                展开高级筛选条件
              </Button>
            </div>
            <Drawer
              title="量化选股条件"
              placement="bottom"
              height="80vh"
              open={mobileFilterDrawerOpen}
              onClose={() => setMobileFilterDrawerOpen(false)}
              extra={
                <Button type="primary" size="small" onClick={() => setMobileFilterDrawerOpen(false)}>
                  完成 (查看结果)
                </Button>
              }
            >
              <FilterPanel
                filters={filters.filters}
                onFiltersChange={filters.setFilters}
                industries={industries}
                concepts={concepts}
                onSearch={() => {
                  filters.handleSearch();
                  setMobileFilterDrawerOpen(false);
                }}
                onReset={filters.handleReset}
                showPercentile={filters.showPercentile}
                onShowPercentileChange={filters.handleShowPercentileChange}
                pePercentileMax={filters.pePercentileMax}
                pbPercentileMax={filters.pbPercentileMax}
                onPePercentileMaxChange={filters.handlePePercentileMaxChange}
                onPbPercentileMaxChange={filters.handlePbPercentileMaxChange}
              />
            </Drawer>
          </>
        ) : (
          <FilterPanel
            filters={filters.filters}
            onFiltersChange={filters.setFilters}
            industries={industries}
            concepts={concepts}
            onSearch={filters.handleSearch}
            onReset={filters.handleReset}
            showPercentile={filters.showPercentile}
            onShowPercentileChange={filters.handleShowPercentileChange}
            pePercentileMax={filters.pePercentileMax}
            pbPercentileMax={filters.pbPercentileMax}
            onPePercentileMaxChange={filters.handlePePercentileMaxChange}
            onPbPercentileMaxChange={filters.handlePbPercentileMaxChange}
          />
        )}
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
      {strategyProgress ? (
        <Alert
          title={strategyProgress.total
            ? `策略扫描中：${strategyProgress.completed}/${strategyProgress.total}，命中 ${strategyProgress.matched}，排除 ${strategyProgress.excluded}，失败 ${strategyProgress.failed}`
            : "正在准备策略扫描候选股票"}
          description={<Progress percent={strategyProgress.total ? Math.round(strategyProgress.completed / strategyProgress.total * 100) : 0} size="small" />}
          action={<Button danger size="small" onClick={() => cancelStrategy?.()}>取消扫描</Button>}
          type="info"
          showIcon
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      ) : null}
      {strategyResult ? (
        <>
          <Alert
            title={`${strategyResult.name}@${strategyResult.version}：命中 ${strategyResult.matchedCodes.length}/${strategyResult.evaluated} 只${Object.keys(strategyResult.excluded).length ? `，排除 ${Object.keys(strategyResult.excluded).length} 只` : ""}${strategyResult.failed ? `，${strategyResult.failed} 只数据失败` : ""}`}
            description={strategyResult.matchedCodes.length
              ? `策略快照 ${strategyResult.hash.slice(0, 20)}… · ${strategyResult.matchedCodes.length > 10 ? "前 10 只命中股票" : "命中股票"}已自动勾选${strategyResult.fallbackCount ? ` · ${strategyResult.fallbackCount} 只使用 K 线 fallback` : ""}`
              : `策略快照 ${strategyResult.hash.slice(0, 20)}… · 当前候选中没有目标仓位为持有的股票`}
            action={(
              <Space size={6} wrap>
                {Object.keys(strategyResult.excluded).length ? (
                  <Button size="small" onClick={() => setExcludedDetailsOpen(true)}>查看排除明细</Button>
                ) : null}
                <Button size="small" onClick={() => setShowMatchedOnly((value) => !value)}>{showMatchedOnly ? "显示全部" : "只看命中"}</Button>
              </Space>
            )}
            type={strategyResult.failed || Object.keys(strategyResult.excluded).length || strategyResult.fallbackCount ? "warning" : "success"}
            showIcon
            closable
            onClose={() => { setStrategyResult(undefined); setShowMatchedOnly(false); setExcludedDetailsOpen(false); }}
            style={{ marginBottom: 16, borderRadius: 8 }}
          />
          <StrategyResultInsightBar
            strategyName={strategyResult.name}
            matchedCodes={strategyResult.matchedCodes}
            evaluated={strategyResult.evaluated}
            returnsSinceSignal={strategyResult.returnsSinceSignal}
            signalAges={strategyResult.signalAges}
            onSelectAllMatched={() => batch.setSelectedCodes(strategyResult.matchedCodes.slice(0, 10))}
            onBacktestAll={() => {
              const codesParam = encodeURIComponent(strategyResult.matchedCodes.join(","));
              const strategyParam = selectedStrategyKey ? `&strategy=${encodeURIComponent(selectedStrategyKey)}` : "";
              navigate(`/quant?codes=${codesParam}${strategyParam}`);
            }}
          />
        </>
      ) : null}
      <Modal
        title={`排除明细（${Object.keys(strategyResult?.excluded ?? {}).length}）`}
        open={excludedDetailsOpen}
        footer={<Button type="primary" onClick={() => setExcludedDetailsOpen(false)}>关闭</Button>}
        onCancel={() => setExcludedDetailsOpen(false)}
        width={560}
      >
        <ul style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {Object.entries(strategyResult?.excluded ?? {}).map(([code, reason]) => {
            const stockName = screenerResult?.items.find((item) => item.code === code)?.name;
            return (
              <li key={code} style={{ padding: "8px 0" }}>
                <Space align="start">
                  <Typography.Text code>{stockName ? `${code} ${stockName}` : code}</Typography.Text>
                  <Typography.Text>{reason}</Typography.Text>
                </Space>
              </li>
            );
          })}
        </ul>
      </Modal>
      {filters.showPercentile && percentiles.isPending && (
        <Alert
          title="正在计算估值百分位，请稍候..."
          type="info"
          showIcon
          style={{ marginBottom: 16, borderRadius: 8 }}
        />
      )}
      <Card
        size="small"
        title={(
          <span style={{ fontWeight: "var(--c-weight-semibold)" }}>
            {showMatchedOnly && strategyResult
              ? `策略命中 (${strategyResult.matchedItems.length} 只)`
              : `筛选结果${screenerResult ? ` (${screenerResult.total} 只)` : ""}`}
          </span>
        )}
        extra={(
          <Space size={6} wrap>
            {screenerResult ? (
              <>
                {!isNarrow ? (
                  <>
                    <Tag color={screenerResult.stock_master_complete ? "success" : "warning"}>
                      主表{screenerResult.stock_master_complete ? "完整" : "降级"}
                    </Tag>
                    <Tag>申万覆盖 {Math.round((screenerResult.sw_industry_coverage ?? 0) * 100)}%</Tag>
                    <Tag>交易所行业 {Math.round((screenerResult.exchange_industry_coverage ?? 0) * 100)}%</Tag>
                  </>
                ) : (
                  <Tooltip
                    title={`主表${screenerResult.stock_master_complete ? "完整" : "降级"} · 申万覆盖 ${Math.round((screenerResult.sw_industry_coverage ?? 0) * 100)}% · 交易所行业 ${Math.round((screenerResult.exchange_industry_coverage ?? 0) * 100)}%`}
                  >
                    <Tag color={screenerResult.stock_master_complete ? "success" : "warning"}>
                      覆盖 {Math.round((screenerResult.sw_industry_coverage ?? 0) * 100)}%
                    </Tag>
                  </Tooltip>
                )}
                <Space.Compact size="small">
                  <Button
                    loading={isExportingAll}
                    disabled={!displayedResult?.items?.length}
                    onClick={handleExportCurrent}
                    icon={<DownloadOutlined />}
                  >
                    {isNarrow ? "导出" : "导出 CSV"}
                  </Button>
                  <Dropdown
                    disabled={!displayedResult?.items?.length}
                    menu={{
                      items: [
                        {
                          key: "current",
                          label: `导出当前页 (${displayedResult?.items?.length ?? 0} 只)`,
                          onClick: handleExportCurrent,
                        },
                        {
                          key: "all",
                          label: `导出全量匹配 (${Math.min(1000, screenerResult.total)} 只)`,
                          disabled: isExportingAll || screenerResult.total === 0,
                          onClick: () => void handleExportAll(),
                        },
                      ],
                    }}
                  >
                    <Button icon={<DownOutlined />} disabled={!displayedResult?.items?.length} />
                  </Dropdown>
                </Space.Compact>
                <Space.Compact size="small">
                  <Button
                    type={viewMode === "table" ? "primary" : "default"}
                    icon={<BarsOutlined />}
                    aria-label="表格视图"
                    title="表格视图"
                    onClick={() => setViewMode("table")}
                  />
                  <Button
                    type={viewMode === "card" ? "primary" : "default"}
                    icon={<AppstoreOutlined />}
                    aria-label="卡片视图"
                    title="卡片视图"
                    onClick={() => setViewMode("card")}
                  />
                </Space.Compact>
              </>
            ) : null}
            <DataRefreshIndicator active={isFetching && !!screenerResult} />
          </Space>
        )}
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
          <ScreenerBatchActions
            selectedCodes={batch.selectedCodes}
            isAddingWatchlist={batch.isAddingWatchlist}
            isAnalyzing={batch.isBatchAnalyzing}
            analysisProgress={batch.analysisProgress}
            onAddWatchlist={() => void batch.handleAddSelectedToWatchlist()}
            onAnalyze={() => void batch.handleBatchAnalyze()}
            onAiDiagnose={handleBatchAiDiagnose}
            onBacktest={() => {
              const codesParam = encodeURIComponent(batch.selectedCodes.join(","));
              const strategyParam = selectedStrategyKey ? `&strategy=${encodeURIComponent(selectedStrategyKey)}` : "";
              navigate(`/quant?codes=${codesParam}${strategyParam}`);
            }}
            onClear={batch.clearSelection}
          />
          {displayedResult?.items && displayedResult.items.length > 0 ? (
            <ScreenerPoolInsightsBar
              items={displayedResult.items}
              total={screenerResult?.total ?? displayedResult.items.length}
              onSelectIndustry={handleSelectIndustryFromInsights}
              selectedIndustry={filters.filters.industries?.[0]}
            />
          ) : null}
          {viewMode === "card" ? (
            <ScreenerCardList
              data={displayedResult}
              isLoading={screenerLoading && !screenerResult}
              selectedCodes={batch.selectedCodes}
              onSelectedCodesChange={batch.setSelectedCodes}
              onPageChange={filters.handlePageChange}
              onAddWatchlist={batch.handleAddSingleToWatchlist}
            />
          ) : (
            <ResultsTable
              data={displayedResult}
              isLoading={screenerLoading && !screenerResult}
              percentileMap={percentiles.percentileMap}
              showPercentile={filters.showPercentile}
              onPageChange={filters.handlePageChange}
              filters={filters.appliedState.filters}
              onSortChange={filters.handleSortChange}
              selectedCodes={batch.selectedCodes}
              onSelectedCodesChange={batch.setSelectedCodes}
              onAddWatchlist={batch.handleAddSingleToWatchlist}
              strategySignalDates={strategyResult?.signalDates}
              strategySignalAges={strategyResult?.signalAges}
              strategyReturnsSinceSignal={strategyResult?.returnsSinceSignal}
              strategyAverageAmounts={strategyResult?.averageAmounts}
              strategyDataSources={strategyResult?.dataSources}
              strategyFallbackCodes={strategyResult?.fallbackCodes}
            />
          )}
        </SectionDataState>
      </Card>
      <div style={{ height: 72 }} aria-hidden />
    </PageShell>
  );
}
