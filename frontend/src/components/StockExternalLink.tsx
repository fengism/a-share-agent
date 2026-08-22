import type { CSSProperties, ReactNode } from "react";
import { getEastmoneyStockUrl, normalizeAshareStockCode } from "../utils/stockLinks";

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
  const href = getEastmoneyStockUrl(code);
  if (!href) {
    return <span className={className} style={style}>{children}</span>;
  }

  const normalizedCode = normalizeAshareStockCode(code);
  const stockLabel = name ? `${name}（${normalizedCode}）` : normalizedCode;

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      title={`在东方财富查看${stockLabel}`}
      className={className}
      style={style}
    >
      {children}
    </a>
  );
}
