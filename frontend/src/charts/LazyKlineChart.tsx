import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Skeleton } from "antd";
import type { KlineItem } from "../types/stock";
import type { ChanlunResult } from "../utils/chanlun";
import { loadKlineChart } from "./klineChartLoader";
import type { KlineTradeMarker } from "./klineMarkers";

const KlineChart = lazy(loadKlineChart);

interface LazyKlineChartProps {
  data: KlineItem[];
  height?: number;
  viewKey?: string;
  tradeMarkers?: KlineTradeMarker[];
  chanlun?: ChanlunResult | null;
  forceRender?: boolean;
  onReachLeftEdge?: () => void;
  historyLimitReached?: boolean;
}

export default function LazyKlineChart({
  data,
  height = 500,
  viewKey,
  tradeMarkers,
  chanlun,
  forceRender = false,
  onReachLeftEdge,
  historyLimitReached,
}: LazyKlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [shouldRender, setShouldRender] = useState(() => typeof IntersectionObserver === "undefined");
  const renderChart = forceRender || shouldRender;

  useEffect(() => {
    if (renderChart || !containerRef.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setShouldRender(true);
        observer.disconnect();
      }
    }, { rootMargin: "240px 0px" });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [renderChart]);

  return (
    <div ref={containerRef} style={{ minHeight: height, backgroundColor: "var(--c-card-bg)" }}>
      {renderChart ? (
        <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
          <KlineChart
            data={data}
            height={height}
            viewKey={viewKey}
            tradeMarkers={tradeMarkers}
            chanlun={chanlun}
            onReachLeftEdge={onReachLeftEdge}
            historyLimitReached={historyLimitReached}
          />
        </Suspense>
      ) : (
        <div aria-label="K线图即将加载" style={{ minHeight: height }}>
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      )}
    </div>
  );
}
