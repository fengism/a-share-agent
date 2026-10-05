import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { FundProjectionScreenOutlined, FullscreenOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Modal, Segmented, Skeleton, Switch, Tooltip } from "antd";
import { useKlineData, useStockChipDistribution, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import { analyzeChanlun } from "../../utils/chanlun";
import { MAX_KLINE_HISTORY_YEARS, yearsAgoDate } from "../../utils/date";
import StockSectionTitle from "./StockSectionTitle";

const ChipDistributionPanel = lazy(() => import("../../features/stock-insights/ChipDistributionPanel"));

function KlinePanel({
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
}: {
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
}) {
  const [internalPeriod, setInternalPeriod] = useState("daily");
  const period = controlledPeriod ?? internalPeriod;
  const setPeriod = onPeriodChange ?? setInternalPeriod;
  const [adjust, setAdjust] = useState("qfq");
  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  // 日 K 在交易时段盘中轮询，让当日进行中的那根 K 线随行情更新；周/月/年不轮询。
  const query = useKlineData(code, period, adjust, true, { startDate }, { liveRefresh: period === "daily" });
  const items = query.data?.items;
  const chanlun = useMemo(
    () => chanlunEnabled && items && items.length >= 10 ? analyzeChanlun(items) : null,
    [chanlunEnabled, items],
  );

  // 上游已无更早数据时通知外层停止回溯（由 StockCharts 的 onHistoryExhausted 处理）
  const itemCount = items?.length ?? null;
  useEffect(() => {
    if (itemCount != null) onHistoryExhausted?.(itemCount);
  }, [itemCount, onHistoryExhausted]);

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
          viewKey={`${code}-${period}-${adjust}${viewKeySuffix}`}
          onReachLeftEdge={historyLimitReached ? undefined : onReachLeftEdge}
          historyLimitReached={historyLimitReached}
        />
      </SectionDataState>
    </>
  );
}

function IntradayPanel({
  code,
  height = 380,
  viewKeySuffix = "",
}: {
  code: string;
  height?: number;
  viewKeySuffix?: string;
}) {
  const [showAvgLine, setShowAvgLine] = useState(true);
  const [showPrevClose, setShowPrevClose] = useState(true);
  const query = useStockIntraday(code);
  const items = query.data?.items ?? [];
  const latestTime = items.length > 0 ? items[items.length - 1].time : null;

  return (
    <>
      <div className="stock-chart-toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "12px", color: "var(--c-text-secondary)" }}>
          {latestTime && (
            <span>
              数据时间: <strong style={{ color: "var(--c-text-primary)", fontFamily: "var(--c-font-mono)" }}>{latestTime}</strong>
            </span>
          )}
          {query.isFetching && <span style={{ color: "var(--c-primary)" }}>刷新中...</span>}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <label className="stock-chart-chanlun-toggle" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px" }}>
            均价线
            <Switch aria-label="均价线" size="small" checked={showAvgLine} onChange={setShowAvgLine} />
          </label>
          <label className="stock-chart-chanlun-toggle" style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px" }}>
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
        emptyText="暂无分时数据"
        errorTitle="分时数据加载失败"
        minHeight={height}
      >
        <IntradayChart
          data={items}
          prevClose={query.data?.prev_close}
          height={height}
          viewKey={`${code}${viewKeySuffix}`}
          showAvgLine={showAvgLine}
          showPrevCloseLine={showPrevClose}
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

export default function StockCharts({ code }: { code: string }) {
  const [chanlunEnabled, setChanlunEnabled] = useState(false);
  const [activeView, setActiveView] = useState<ChartView>("kline");
  const [period, setPeriod] = useState("daily");
  const [historyYears, setHistoryYears] = useState(1);
  const [expanded, setExpanded] = useState(false);
  const { cardStyle } = useStyles();

  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  const historyLimitReached = historyYears >= MAX_KLINE_HISTORY_YEARS;

  // 回溯终止保护：扩大窗口后若条目数没有增加，说明上游已无更早数据。
  // 此时必须停止继续回溯——KlineChart 的左缘回调在数据填不满视口时会反复触发，
  // 若放任下去会形成 startDate 变化→重新请求→仍然触底的死循环，持续打后端接口。
  const historyExhaustedRef = useRef(false);
  const loadedCountRef = useRef<number | null>(null);
  const handleHistoryExhausted = useCallback((itemCount: number) => {
    if (loadedCountRef.current != null && itemCount <= loadedCountRef.current) {
      historyExhaustedRef.current = true;
    }
    loadedCountRef.current = itemCount;
  }, []);

  // 切换股票或周期时回到默认 1 年窗口，并重置回溯状态
  useEffect(() => {
    setHistoryYears(1);
    historyExhaustedRef.current = false;
    loadedCountRef.current = null;
  }, [code, period]);

  const handleReachLeftEdge = useCallback(() => {
    if (historyExhaustedRef.current) return;
    setHistoryYears((years) => Math.min(years + 1, MAX_KLINE_HISTORY_YEARS));
  }, []);

  return (
    <Card
      id="stock-charts"
      className="stock-section-card stock-chart-card"
      title={<StockSectionTitle icon={<FundProjectionScreenOutlined />} title="行情、技术与筹码" description="价格趋势、动量变化与持仓成本" />}
      extra={(
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Segmented
            options={[
              { label: "K 线", value: "kline" },
              { label: "分时", value: "intraday" },
              { label: "MACD", value: "macd" },
              { label: "RSI", value: "rsi" },
              { label: "KDJ", value: "kdj" },
              { label: "筹码分布", value: "chips" },
            ]}
            value={activeView}
            onChange={(value) => setActiveView(value as ChartView)}
            size="small"
          />
          <Tooltip title="全屏查看图表">
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              aria-label="全屏查看图表"
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
        />
      ) : activeView === "intraday" ? (
        <IntradayPanel code={code} />
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
        }
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width="92vw"
        styles={{ body: { height: "76vh", overflowY: "auto" } }}
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
            height={580}
            viewKeySuffix="-fullscreen"
          />
        ) : activeView === "intraday" ? (
          <IntradayPanel code={code} height={580} viewKeySuffix="-fullscreen" />
        ) : activeView === "macd" || activeView === "rsi" || activeView === "kdj" ? (
          <div className="stock-macd-panel" style={{ minHeight: 600 }}>
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
              height={560}
            />
          </div>
        ) : (
          <ChipDistributionView code={code} />
        )}
      </Modal>
    </Card>
  );
}
