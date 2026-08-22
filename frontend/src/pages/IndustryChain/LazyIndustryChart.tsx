import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Skeleton } from "antd";
import { useColors } from "../../styles/ui";

const IndustryChart = lazy(() => import("./IndustryChart"));

interface LazyIndustryChartProps {
  option: Record<string, unknown>;
  height: string;
}

export default function LazyIndustryChart({ option, height }: LazyIndustryChartProps) {
  const colors = useColors();
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
    <div
      ref={containerRef}
      style={{
        height,
        width: "100%",
        minHeight: 300,
        borderRadius: 8,
        background: shouldRender ? "transparent" : colors.hoverBg,
      }}
    >
      {shouldRender ? (
        <Suspense
          fallback={(
            <div aria-label="产业链图表加载中" style={{ height: "100%", width: "100%" }}>
              <Skeleton.Node active style={{ width: "100%", height: "100%" }} />
            </div>
          )}
        >
          <IndustryChart option={option} height="100%" />
        </Suspense>
      ) : (
        <div aria-hidden="true" style={{ height: "100%", width: "100%" }}>
          <Skeleton.Node style={{ width: "100%", height: "100%" }} />
        </div>
      )}
    </div>
  );
}
