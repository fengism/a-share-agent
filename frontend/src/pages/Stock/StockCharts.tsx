import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { BarChartOutlined, LineChartOutlined, FundProjectionScreenOutlined, FullscreenOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Modal, Segmented, Skeleton, Switch, Tooltip } from "antd";
import { useHKStockHistory } from "../../api/queryHooks/hk";
import { useKlineData, useStockChipDistribution, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import { useFullscreenChartHeight } from "../../hooks/useFullscreenChartHeight";
import { useStyles } from "../../styles/ui";
import type { KlineItem } from "../../types/stock";
import { analyzeChanlun } from "../../utils/chanlun";
import { MAX_KLINE_HISTORY_YEARS, yearsAgoDate } from "../../utils/date";
import StockSectionTitle from "./StockSectionTitle";

const ChipDistributionPanel = lazy(() => import("../../features/stock-insights/ChipDistributionPanel"));

interface KlinePanelProps {
  code: string;
  chanlunEnabled: boolean;
  onChanlunChange: (enabled: boolean) => void;
  height?: number;
  viewKeySuffix?: string;
  period?: string;
  onPeriodChange?: (period: string) => void;
  historyYears: number;
  onReachLeftEdge?: () => void;
  historyLimitReached: boolean;
  /** 每次 K 线数据到达时上报当前条目数，外层据此判断上游是否已无更早数据 */
  onHistoryExhausted?: (itemCount: number) => void;
  market?: "cn" | "hk";
}

function CNKlinePanel({
  code,
  chanlunEnabled,
  onChanlunChange,
  height = 380,
  viewKeySuffix = "",
  period: controlledPeriod,
  onPeriodChange,
  historyYears,
  onReachLeftEdge,
  historyLimitReached,
  onHistoryExhausted,
}: KlinePanelProps) {
  const [internalPeriod, setInternalPeriod] = useState("daily");
  const period = controlledPeriod ?? internalPeriod;
  const setPeriod = onPeriodChange ?? setInternalPeriod;
  const [adjust, setAdjust] = useState("qfq");
  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  // 日 K 在交易时段盘中轮询，让当日进行中的那根 K 线随行情更新；周/月/年不轮询。
  const query = useKlineData(code, period, adjust, true, { startDate }, { liveRefresh: period === "daily" });
  const items = query.data?.items;

  const chanlun = useMemo(
    () => (chanlunEnabled && items && items.length >= 10 ? analyzeChanlun(items) : null),
    [chanlunEnabled, items],
  );

  // 放大横屏时页面工具栏被固定层遮住，这里把周期/复权/缠论控件带进图表 HUD
  const landscapeToolbar = (
    <>
      <Segmented
        size="small"
        aria-label="K 线周期"
        options={[
          { label: "日K", value: "daily" },
          { label: "周K", value: "weekly" },
          { label: "月K", value: "monthly" },
          { label: "年K", value: "annual" },
        ]}
        value={period}
        onChange={(value) => setPeriod(String(value))}
      />
      <Segmented
        size="small"
        aria-label="复权方式"
        options={[{ label: "前复权", value: "qfq" }, { label: "后复权", value: "hfq" }, { label: "不复权", value: "none" }]}
        value={adjust}
        onChange={(value) => setAdjust(String(value))}
      />
      <label className="stock-chart-chanlun-toggle">
        缠论
        <Switch aria-label="缠论" size="small" checked={chanlunEnabled} onChange={onChanlunChange} />
      </label>
    </>
  );

  // 筹码分布（日K线周期时启用）
  const chipQuery = useStockChipDistribution(code);

  // 上游已无更早数据时通知外层停止回溯（由 StockCharts 的 onHistoryExhausted 处理）
  const itemCount = items?.length ?? null;
  useEffect(() => {
    if (itemCount != null) onHistoryExhausted?.(itemCount);
  }, [itemCount, onHistoryExhausted]);

  const viewKey = `${code}-${period}-${adjust}${viewKeySuffix}`;

  return (
    <>
      <div className="stock-chart-toolbar">
        <Segmented
          aria-label="K 线周期"
          options={[
            { label: "日K", value: "daily" },
            { label: "周K", value: "weekly" },
            { label: "月K", value: "monthly" },
            { label: "年K", value: "annual" },
          ]}
          value={period}
          onChange={(value) => setPeriod(String(value))}
          size="small"
        />
        <Segmented
          aria-label="复权方式"
          options={[{ label: "前复权", value: "qfq" }, { label: "后复权", value: "hfq" }, { label: "不复权", value: "none" }]}
          value={adjust}
          onChange={(value) => setAdjust(String(value))}
          size="small"
        />
        <Tooltip title="叠加缠论笔、中枢及一二三类买卖点；仅供技术研究参考">
          <label className="stock-chart-chanlun-toggle">
            缠论
            <Switch aria-label="缠论" size="small" checked={chanlunEnabled} onChange={onChanlunChange} />
          </label>
        </Tooltip>
        <div className="stock-kline-ma-legend" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "var(--c-font-xs)", fontFamily: "var(--c-font-mono)", opacity: 0.9 }}>
          <span style={{ color: "#faad14" }}>● MA5</span>
          <span style={{ color: "#13c2c2" }}>● MA10</span>
          <span style={{ color: "#722ed1" }}>● MA20</span>
          <span style={{ color: "#52c41a" }}>● MA60</span>
        </div>
        <span className="stock-chart-hint" data-testid="kline-history-range">
          {historyLimitReached
            ? `已加载近 ${MAX_KLINE_HISTORY_YEARS} 年（上限）`
            : `近 ${historyYears} 年 · 向左滑动加载更早数据（最多 ${MAX_KLINE_HISTORY_YEARS} 年）`}
        </span>
      </div>
      {chanlunEnabled && items && items.length > 0 && items.length < 10 ? (
        <p className="stock-chart-hint" role="status">当前周期 K 线不足 10 根，暂无法绘制缠论。</p>
      ) : null}
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={!items?.length}
        emptyText="暂无 K 线数据"
        errorTitle="K 线数据加载失败"
        minHeight={height}
      >
        <LazyKlineChart
          data={items ?? []}
          chanlun={chanlun}
          height={height}
          viewKey={viewKey}
          onReachLeftEdge={historyLimitReached ? undefined : onReachLeftEdge}
          historyLimitReached={historyLimitReached}
          chipDistribution={chipQuery?.data}
          landscapeToolbar={landscapeToolbar}
        />
      </SectionDataState>
    </>
  );
}

function HKKlinePanel({
  code,
  height = 380,
  viewKeySuffix = "",
  period: controlledPeriod,
  onPeriodChange,
  historyYears,
  onReachLeftEdge,
  historyLimitReached,
  onHistoryExhausted,
}: KlinePanelProps) {
  const [internalPeriod, setInternalPeriod] = useState("daily");
  const period = controlledPeriod ?? internalPeriod;
  const setPeriod = onPeriodChange ?? setInternalPeriod;
  const [adjust, setAdjust] = useState("qfq");
  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  const query = useHKStockHistory(code, period, adjust, startDate);
  const rawItems = query.data?.items;
  const items: KlineItem[] = useMemo(() => {
    return (rawItems ?? []).map((item) => ({
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
  }, [rawItems]);

  const landscapeToolbar = (
    <>
      <Segmented
        size="small"
        aria-label="K线周期"
        options={[
          { label: "日K", value: "daily" },
          { label: "周K", value: "weekly" },
          { label: "月K", value: "monthly" },
          { label: "年K", value: "annual" },
        ]}
        value={period}
        onChange={(value) => setPeriod(String(value))}
      />
      <Segmented
        size="small"
        aria-label="复权方式"
        options={[{ label: "前复权", value: "qfq" }, { label: "后复权", value: "hfq" }, { label: "不复权", value: "none" }]}
        value={adjust}
        onChange={(value) => setAdjust(String(value))}
      />
    </>
  );

  const itemCount = items?.length ?? null;
  useEffect(() => {
    if (itemCount != null) onHistoryExhausted?.(itemCount);
  }, [itemCount, onHistoryExhausted]);

  const viewKey =
    viewKeySuffix === "-fullscreen"
      ? `hk-stock-modal-${code}-${period}-${adjust}`
      : `hk-stock-page-${code}-${period}-${adjust}`;

  return (
    <>
      <div className="stock-chart-toolbar">
        <Segmented
          aria-label="K线周期"
          options={[
            { label: "日K", value: "daily" },
            { label: "周K", value: "weekly" },
            { label: "月K", value: "monthly" },
            { label: "年K", value: "annual" },
          ]}
          value={period}
          onChange={(value) => setPeriod(String(value))}
          size="small"
        />
        <Segmented
          aria-label="复权方式"
          options={[{ label: "前复权", value: "qfq" }, { label: "后复权", value: "hfq" }, { label: "不复权", value: "none" }]}
          value={adjust}
          onChange={(value) => setAdjust(String(value))}
          size="small"
        />
        <div className="stock-kline-ma-legend" style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: "var(--c-font-xs)", fontFamily: "var(--c-font-mono)", opacity: 0.9 }}>
          <span style={{ color: "#faad14" }}>● MA5</span>
          <span style={{ color: "#13c2c2" }}>● MA10</span>
          <span style={{ color: "#722ed1" }}>● MA20</span>
          <span style={{ color: "#52c41a" }}>● MA60</span>
        </div>
        <span className="stock-chart-hint" data-testid="kline-history-range">
          {historyLimitReached
            ? `已加载近 ${MAX_KLINE_HISTORY_YEARS} 年（上限）`
            : `近 ${historyYears} 年 · 向左滑动加载更早数据（最多 ${MAX_KLINE_HISTORY_YEARS} 年）`}
        </span>
      </div>
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={!items?.length}
        emptyText="暂无港股历史行情数据"
        errorTitle="港股历史行情加载失败"
        minHeight={height}
      >
        <LazyKlineChart
          data={items ?? []}
          chanlun={null}
          height={height}
          viewKey={viewKey}
          onReachLeftEdge={historyLimitReached ? undefined : onReachLeftEdge}
          historyLimitReached={historyLimitReached}
          landscapeToolbar={landscapeToolbar}
        />
      </SectionDataState>
    </>
  );
}

function KlinePanel(props: KlinePanelProps) {
  if (props.market === "hk") {
    return <HKKlinePanel {...props} />;
  }
  return <CNKlinePanel {...props} />;
}

function IntradayPanel({
  code,
  height = 380,
  viewKeySuffix = "",
  market = "cn",
}: {
  code: string;
  height?: number;
  viewKeySuffix?: string;
  market?: "cn" | "hk";
}) {
  const isHK = market === "hk";
  const [showAvgLine, setShowAvgLine] = useState(true);
  const [showPrevClose, setShowPrevClose] = useState(true);
  const query = useStockIntraday(code);
  const items = query.data?.items ?? [];
  const latestTime = items.length > 0 ? items[items.length - 1].time : null;

  const viewKey = isHK
    ? viewKeySuffix === "-fullscreen"
      ? `hk-intraday-modal-${code}`
      : `hk-intraday-${code}`
    : `${code}${viewKeySuffix}`;

  return (
    <>
      <div className="stock-chart-toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "var(--c-font-sm)", color: "var(--c-text-secondary)" }}>
          {latestTime && (
            <span>
              数据时间: <strong style={{ color: "var(--c-text-primary)", fontFamily: "var(--c-font-mono)" }}>{latestTime}</strong>
            </span>
          )}
          {query.isFetching && <span style={{ color: "var(--c-primary)" }}>刷新中...</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <label className="stock-chart-chanlun-toggle" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--c-font-sm)" }}>
            均价线
            <Switch aria-label="均价线" size="small" checked={showAvgLine} onChange={setShowAvgLine} />
          </label>
          <label className="stock-chart-chanlun-toggle" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "var(--c-font-sm)" }}>
            昨收线
            <Switch aria-label="昨收线" size="small" checked={showPrevClose} onChange={setShowPrevClose} />
          </label>
          <Button
            size="small"
            type="text"
            icon={<ReloadOutlined spin={query.isFetching} />}
            onClick={() => query.refetch()}
            title="刷新分时数据"
            style={{ color: "var(--c-text-secondary)" }}
          >
            刷新
          </Button>
        </div>
      </div>
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={items.length === 0}
        emptyText={isHK ? "暂无港股分时行情数据" : "暂无分时数据"}
        errorTitle="分时数据加载失败"
        minHeight={height}
      >
        <IntradayChart
          data={items}
          prevClose={query.data?.prev_close}
          height={height}
          viewKey={viewKey}
          showAvgLine={showAvgLine}
          showPrevCloseLine={showPrevClose}
          market={market}
        />
      </SectionDataState>
    </>
  );
}

function ChipDistributionView({ code }: { code: string }) {
  const query = useStockChipDistribution(code);

  return (
    <SectionDataState
      isLoading={query.isLoading}
      error={query.error}
      onRetry={() => query.refetch()}
      isEmpty={!query.data}
      emptyText="暂无筹码分布数据"
      errorTitle="筹码分布加载失败"
      minHeight={380}
    >
      {query.data ? (
        <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
          <ChipDistributionPanel data={query.data} embedded />
        </Suspense>
      ) : null}
    </SectionDataState>
  );
}

type ChartView = "kline" | "intraday" | "macd" | "rsi" | "kdj" | "chips";

interface StockChartsProps {
  code: string;
  market?: "cn" | "hk";
  name?: string;
}

export default function StockCharts({ code, market = "cn", name }: StockChartsProps) {
  const isHK = market === "hk";
  const [chanlunEnabled, setChanlunEnabled] = useState(false);
  const [activeView, setActiveView] = useState<ChartView>(isHK ? "intraday" : "kline");
  const [period, setPeriod] = useState("daily");
  const [historyYears, setHistoryYears] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const { cardStyle } = useStyles();
  const fullscreenHeight = useFullscreenChartHeight();

  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  const historyLimitReached = historyYears >= MAX_KLINE_HISTORY_YEARS;

  const historyExhaustedRef = useRef(false);
  const loadedCountRef = useRef<number | null>(null);
  const handleHistoryExhausted = useCallback((itemCount: number) => {
    if (loadedCountRef.current != null && itemCount <= loadedCountRef.current) {
      historyExhaustedRef.current = true;
    }
    loadedCountRef.current = itemCount;
  }, []);

  useEffect(() => {
    setHistoryYears(1);
    historyExhaustedRef.current = false;
    loadedCountRef.current = null;
  }, [code, period]);

  const handleReachLeftEdge = useCallback(() => {
    if (historyExhaustedRef.current) return;
    setHistoryYears((years) => Math.min(years + 1, MAX_KLINE_HISTORY_YEARS));
  }, []);

  const viewOptions = isHK
    ? [
        { label: "分时", value: "intraday" },
        { label: "K线", value: "kline" },
        { label: "MACD", value: "macd" },
        { label: "RSI", value: "rsi" },
        { label: "KDJ", value: "kdj" },
      ]
    : [
        { label: "K 线", value: "kline" },
        { label: "分时", value: "intraday" },
        { label: "MACD", value: "macd" },
        { label: "RSI", value: "rsi" },
        { label: "KDJ", value: "kdj" },
        { label: "筹码分布", value: "chips" },
      ];

  const cardTitle = isHK ? (
    <StockSectionTitle
      icon={
        activeView === "intraday" ? (
          <BarChartOutlined />
        ) : activeView === "kline" ? (
          <LineChartOutlined />
        ) : (
          <FundProjectionScreenOutlined />
        )
      }
      title={
        activeView === "intraday"
          ? "分时走势"
          : activeView === "kline"
          ? "走势与历史行情"
          : `${activeView.toUpperCase()} 技术指标`
      }
      description={`${name || code} ${
        activeView === "intraday"
          ? "当日分时与成交走势"
          : activeView === "kline"
          ? "多周期K线与技术走势"
          : `${activeView.toUpperCase()} 动量与趋势分析`
      }`}
    />
  ) : (
    <StockSectionTitle
      icon={<FundProjectionScreenOutlined />}
      title="行情、技术与筹码"
      description="价格趋势、动量变化与持仓成本"
    />
  );

  return (
    <Card
      id="stock-charts"
      className="stock-section-card stock-chart-card"
      title={cardTitle}
      extra={(
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Segmented
            aria-label={isHK ? "走势类型" : undefined}
            options={viewOptions}
            value={activeView}
            onChange={(value) => setActiveView(value as ChartView)}
            size="small"
          />
          <Tooltip title={isHK ? undefined : "全屏查看图表"}>
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              aria-label={isHK ? "全屏查看行情" : "全屏查看图表"}
              onClick={() => setExpanded(true)}
              style={{ color: "var(--c-text-secondary)" }}
            />
          </Tooltip>
        </div>
      )}
      style={cardStyle}
    >
      {activeView === "kline" ? (
        <KlinePanel
          code={code}
          chanlunEnabled={chanlunEnabled}
          onChanlunChange={setChanlunEnabled}
          period={period}
          onPeriodChange={setPeriod}
          historyYears={historyYears}
          onReachLeftEdge={handleReachLeftEdge}
          historyLimitReached={historyLimitReached}
          onHistoryExhausted={handleHistoryExhausted}
          market={market}
        />
      ) : activeView === "intraday" ? (
        <IntradayPanel code={code} market={market} />
      ) : activeView === "macd" || activeView === "rsi" || activeView === "kdj" ? (
        <div className="stock-macd-panel" style={{ minHeight: 436 }}>
          <IndicatorSubCharts
            code={code}
            types={["macd", "rsi", "kdj"]}
            activeType={activeView}
            onTypeChange={(type) => setActiveView(type)}
            period={period}
            onPeriodChange={setPeriod}
            startDate={startDate}
            historyYears={historyYears}
            onReachLeftEdge={handleReachLeftEdge}
            historyLimitReached={historyLimitReached}
            height={340}
          />
        </div>
      ) : (
        <ChipDistributionView code={code} />
      )}

      <Modal
        title={
          isHK ? (
            `${name || code}（${code}）· ${
              activeView === "intraday"
                ? "分时图全屏"
                : activeView === "kline"
                ? (period === "daily" ? "日K" : period === "weekly" ? "周K" : period === "monthly" ? "月K" : "年K") + "线全屏"
                : `${activeView.toUpperCase()} 技术副图全屏`
            }`
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 12, justifyContent: "space-between", paddingRight: 32 }}>
              <span style={{ fontWeight: 600 }}>
                {`${code} · ${
                  activeView === "kline"
                    ? "K 线图全屏"
                    : activeView === "intraday"
                    ? "分时图全屏"
                    : activeView === "chips"
                    ? "筹码分布全屏"
                    : activeView.toUpperCase() + " 技术副图全屏"
                }`}
              </span>
            </div>
          )
        }
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width={isHK ? "94vw" : "92vw"}
        style={isHK ? { top: 20 } : undefined}
        styles={{ body: { height: fullscreenHeight, minHeight: isHK ? 320 : undefined, overflowY: "auto" } }}
        destroyOnHidden
      >
        {activeView === "kline" ? (
          <KlinePanel
            code={code}
            chanlunEnabled={chanlunEnabled}
            onChanlunChange={setChanlunEnabled}
            period={period}
            onPeriodChange={setPeriod}
            historyYears={historyYears}
            onReachLeftEdge={handleReachLeftEdge}
            historyLimitReached={historyLimitReached}
            height={fullscreenHeight}
            viewKeySuffix="-fullscreen"
            market={market}
          />
        ) : activeView === "intraday" ? (
          <IntradayPanel code={code} height={fullscreenHeight} viewKeySuffix="-fullscreen" market={market} />
        ) : activeView === "macd" || activeView === "rsi" || activeView === "kdj" ? (
          <div className="stock-macd-panel" style={{ minHeight: fullscreenHeight }}>
            <IndicatorSubCharts
              code={code}
              types={["macd", "rsi", "kdj"]}
              activeType={activeView}
              onTypeChange={(type) => setActiveView(type)}
              period={period}
              onPeriodChange={setPeriod}
              startDate={startDate}
              historyYears={historyYears}
              onReachLeftEdge={handleReachLeftEdge}
              historyLimitReached={historyLimitReached}
              height={Math.max(240, fullscreenHeight - 40)}
            />
          </div>
        ) : (
          <ChipDistributionView code={code} />
        )}
      </Modal>
    </Card>
  );
}
