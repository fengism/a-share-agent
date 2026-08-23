import type { CSSProperties, ReactNode } from "react";
import { Link } from "react-router-dom";
import { normalizeAshareStockCode } from "../utils/stockLinks";

interface StockExternalLinkProps {
  code: string;
  name?: string;
  children: ReactNode;
  className?: string;
  style?: CSSProperties;
}

export default function StockExternalLink({
  code,
  name,
  children,
  className,
  style,
}: StockExternalLinkProps) {
  const normalizedCode = normalizeAshareStockCode(code);
  if (!normalizedCode) {
    return <span className={className} style={style}>{children}</span>;
  }

  const stockLabel = name ? `${name}（${normalizedCode}）` : normalizedCode;

  return (
    <Link
      to={`/analysis/${normalizedCode}`}
      title={`查看${stockLabel}个股详情`}
      className={className}
      style={style}
    >
      {children}
    </Link>
  );
}
