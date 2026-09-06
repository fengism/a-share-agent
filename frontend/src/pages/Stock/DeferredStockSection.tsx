import { type ReactNode, useEffect, useRef, useState } from "react";
import { Skeleton } from "antd";

interface DeferredStockSectionProps {
  children: ReactNode;
  label: string;
  minHeight: number;
}

export default function DeferredStockSection({
  children,
  label,
  minHeight,
}: DeferredStockSectionProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [shouldRender, setShouldRender] = useState(
    () => typeof IntersectionObserver === "undefined",
  );

  useEffect(() => {
    if (shouldRender || !containerRef.current || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        setShouldRender(true);
        observer.disconnect();
      }
    }, { rootMargin: "300px 0px" });

    observer.observe(containerRef.current);
    return () => observer.disconnect();
  }, [shouldRender]);

  return (
    <div
      ref={containerRef}
      aria-label={shouldRender ? undefined : `${label}即将加载`}
      className="stock-deferred-section"
      style={{ minHeight }}
    >
      {shouldRender ? children : (
        <div className="stock-deferred-section__placeholder" aria-hidden="true">
          <Skeleton active paragraph={{ rows: 5 }} title />
        </div>
      )}
    </div>
  );
}
