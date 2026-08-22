import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Skeleton } from "antd";
import type { KlineItem } from "../types/stock";
import type { KlineTradeMarker } from "./klineMarkers";

const KlineChart = lazy(() => import("./KlineChart"));

interface LazyKlineChartProps {
  data: KlineItem[];
  height?: number;
  viewKey?: string;
  tradeMarkers?: KlineTradeMarker[];
}

export default function LazyKlineChart({ data, height = 500, viewKey, tradeMarkers }: LazyKlineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [shouldRender, setShouldRender] = useState(() => typeof IntersectionObserver === "undefined");

  useEffect(() => {
    if (shouldRender || !containerRef.current || typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setShouldRender(true);
        observer.disconnect();
      }
    }, { rootMargin: "240px 0px" });
    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [shouldRender]);

  return (
    <div ref={containerRef} style={{ minHeight: height }}>
      {shouldRender ? (
        <Suspense fallback={<Skeleton active paragraph={{ rows: 8 }} />}>
          <KlineChart data={data} height={height} viewKey={viewKey} tradeMarkers={tradeMarkers} />
        </Suspense>
      ) : (
        <div aria-label="K线图即将加载" style={{ minHeight: height }}>
          <Skeleton active paragraph={{ rows: 8 }} />
        </div>
      )}
    </div>
  );
}
