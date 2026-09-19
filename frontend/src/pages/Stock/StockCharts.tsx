import { lazy, Suspense, useState } from "react";
import { FundProjectionScreenOutlined } from "@ant-design/icons";
import { Card, Segmented, Skeleton } from "antd";
import { useKlineData, useStockChipDistribution, useStockIntraday } from "../../api/queries";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

const ChipDistributionPanel = lazy(() => import("../../features/stock-insights/ChipDistributionPanel"));

function KlinePanel({ code }: { code: string }) {
  const [period, setPeriod] = useState("daily");
  const [adjust, setAdjust] = useState("qfq");
  const query = useKlineData(code, period, adjust);
  const items = query.data?.items ?? [];

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
      </div>
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={items.length === 0}
        emptyText="暂无 K 线数据"
        errorTitle="K 线数据加载失败"
        minHeight={380}
      >
        <LazyKlineChart data={items} height={380} viewKey={`${code}-${period}-${adjust || "none"}`} />
      </SectionDataState>
    </>
  );
}

function IntradayPanel({ code }: { code: string }) {
  const query = useStockIntraday(code);
  const items = query.data?.items ?? [];
  return (
    <SectionDataState
      isLoading={query.isLoading}
      error={query.error}
      onRetry={() => query.refetch()}
      isEmpty={items.length === 0}
      emptyText="暂无分时数据"
      errorTitle="分时数据加载失败"
      minHeight={380}
    >
      <IntradayChart data={items} prevClose={query.data?.prev_close} height={380} viewKey={code} />
    </SectionDataState>
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
  const [activeView, setActiveView] = useState<ChartView>("kline");
  const { cardStyle } = useStyles();

  return (
    <Card
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
        <KlinePanel code={code} />
      ) : activeView === "intraday" ? (
        <IntradayPanel code={code} />
      ) : activeView === "macd" || activeView === "rsi" || activeView === "kdj" ? (
        <div className="stock-macd-panel">
          <IndicatorSubCharts
            code={code}
            types={["macd", "rsi", "kdj"]}
            activeType={activeView}
            onTypeChange={(type) => setActiveView(type)}
            height={260}
          />
        </div>
      ) : (
        <ChipDistributionView code={code} />
      )}
    </Card>
  );
}
