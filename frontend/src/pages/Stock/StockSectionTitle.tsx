import type { ReactNode } from "react";

export default function StockSectionTitle({
  icon,
  title,
  description,
}: {
  icon: ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="stock-section-title">
      <span className="stock-section-title__icon" aria-hidden="true">{icon}</span>
      <span className="stock-section-title__copy">
        <h2>{title}</h2>
        <small>{description}</small>
      </span>
    </div>
  );
}
