import { lazy, Suspense, useMemo, useState } from "react";
import { FundProjectionScreenOutlined, ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Segmented, Skeleton, Switch, Tooltip } from "antd";
import { useKlineData, useStockChipDistribution, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import { analyzeChanlun } from "../../utils/chanlun";
import StockSectionTitle from "./StockSectionTitle";

const ChipDistributionPanel = lazy(() => import("../../features/stock-insights/ChipDistributionPanel"));

function KlinePanel({ code, chanlunEnabled, onChanlunChange }: { code: string; chanlunEnabled: boolean; onChanlunChange: (enabled: boolean) => void }) {
  const [period, setPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const query = useKlineData(code, period, adjust);
  const items = query.data?.items;
  const chanlun = useMemo(
    () => chanlunEnabled && items && items.length >= 10 ? analyzeChanlun(items) : null,
    [chanlunEnabled, items],
  );

  return (
    <>
      <div className="stock-chart-toolbar">
        <Segmented
          aria-label="K 线周期"
          options={[{ label: "日K", value: "daily" }, { label: "周K", value: "weekly" }, { label: "月K", value: "monthly" }]}
          value={period}
          onChange={(value) => setPeriod(String(value))}
          size="small"
        />
        <Segmented
          aria-label="复权方式"
          options={[{ label: "前复权", value: "qfq" }, { label: "后复权", value: "hfq" }, { label: "不复权", value: "" }]}
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
        minHeight={380}
      >
        <LazyKlineChart data={items ?? []} chanlun={chanlun} height={380} viewKey={`${code}-${period}-${adjust || "none"}`} />
      </SectionDataState>
    </>
  );
}

function IntradayPanel({ code }: { code: string }) {
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
        minHeight={380}
      >
        <IntradayChart
          data={items}
          prevClose={query.data?.prev_close}
          height={380}
          viewKey={code}
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
  const { cardStyle } = useStyles();

  return (
    <Card
      id="stock-charts"
      className="stock-section-card stock-chart-card"
      title={<StockSectionTitle icon={<FundProjectionScreenOutlined />} title="行情、技术与筹码" description="价格趋势、动量变化与持仓成本" />}
      extra={(
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
      )}
      style={cardStyle}
    >
      {activeView === "kline" ? (
        <KlinePanel code={code} chanlunEnabled={chanlunEnabled} onChanlunChange={setChanlunEnabled} />
      ) : activeView === "intraday" ? (
        <IntradayPanel code={code} />
      ) : activeView === "macd" || activeView === "rsi" || activeView === "kdj" ? (
        <div className="stock-macd-panel" style={{ minHeight: 436 }}>
          <IndicatorSubCharts
            code={code}
            types={["macd", "rsi", "kdj"]}
            activeType={activeView}
            onTypeChange={(type) => setActiveView(type)}
            height={340}
          />
        </div>
      ) : (
        <ChipDistributionView code={code} />
      )}
    </Card>
  );
}
