import { useEffect, useRef, useState, type ReactNode } from "react";

interface LazyChartProps {
  /** 未进入视口时占位高度，需与实际图表高度一致，避免懒加载时页面跳动。 */
  height: number;
  children: ReactNode;
}

/**
 * 进入视口后才挂载图表。
 *
 * 国家队页一次要渲染 10+ 个 ECharts，全部立即挂载会让首屏解析与绘制明显变慢。
 * 与 `charts/LazyKlineChart`、`pages/IndustryChain/LazyIndustryChart` 保持同一套
 * 约定：无 `IntersectionObserver`（jsdom）时直接渲染，测试无需额外桩。
 */
export default function LazyChart({ height, children }: LazyChartProps) {
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
    <div ref={containerRef} style={{ minHeight: height, width: "100%" }}>
      {shouldRender ? children : <div aria-hidden="true" style={{ height }} />}
    </div>
  );
}
