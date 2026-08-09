import type { ReactNode } from "react";

export interface ResponsiveMetricItem {
  key: string;
  label: ReactNode;
  value: ReactNode;
}

export default function ResponsiveMetricGrid({ items }: { items: ResponsiveMetricItem[] }) {
  return (
    <div className="responsive-metric-grid">
      {items.map((item) => (
        <div className="responsive-metric-item" key={item.key}>
          <span className="responsive-metric-label">{item.label}</span>
          <span className="responsive-metric-value">{item.value}</span>
        </div>
      ))}
    </div>
  );
}
