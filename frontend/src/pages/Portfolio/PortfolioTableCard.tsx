import { Card } from "antd";
import { useMemo, type ReactNode } from "react";
import { useStyles } from "../../styles/ui";

const TABLE_BODY_STYLES = { body: { padding: 0 } };

interface PortfolioTableCardProps {
  title: string;
  stacked?: boolean;
  children: ReactNode;
}

export default function PortfolioTableCard({
  title,
  stacked = false,
  children,
}: PortfolioTableCardProps) {
  const { cardStyle } = useStyles();
  const style = useMemo(
    () => (stacked ? { ...cardStyle, marginBottom: 16 } : cardStyle),
    [cardStyle, stacked],
  );

  return (
    <Card title={title} size="small" style={style} styles={TABLE_BODY_STYLES}>
      {children}
    </Card>
  );
}
