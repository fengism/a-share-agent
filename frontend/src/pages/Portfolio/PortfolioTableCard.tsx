import { Card } from "antd";
import { useMemo, type ReactNode } from "react";

const TABLE_BODY_STYLES = { body: { padding: 0 } };

interface PortfolioTableCardProps {
  title: string;
  extra?: ReactNode;
  stacked?: boolean;
  bare?: boolean;
  children: ReactNode;
}

export default function PortfolioTableCard({
  title,
  extra,
  stacked = false,
  bare = false,
  children,
}: PortfolioTableCardProps) {
  const style = useMemo(() => (stacked ? { marginBottom: 16 } : undefined), [stacked]);

  if (bare) {
    return (
      <div className="portfolio-bare-table-container">
        {extra ? (
          <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10, padding: "0 4px" }}>
            {extra}
          </div>
        ) : null}
        {children}
      </div>
    );
  }

  return (
    <Card title={title} extra={extra} size="small" className="u-card" style={style} styles={TABLE_BODY_STYLES}>
      {children}
    </Card>
  );
}
