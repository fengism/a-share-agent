import { Component, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { useMarketIndices } from "../api/queries";
import { useColors } from "../styles/ui";
import { HEADER_TICKER_INDEX_COUNT, isHeaderTickerIndex } from "../utils/keyMarketIndices";
import "./header-market-ticker.css";

interface ErrorBoundaryProps {
  fallback: ReactNode;
  children: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class TickerErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

function formatIndexName(name: string): string {
  if (name.includes("上证")) return "上证";
  if (name.includes("深证") || name.includes("深成")) return "深成";
  if (name.includes("创业板")) return "创指";
  if (name.includes("科创")) return "科创50";
  return name.slice(0, 4);
}

function TickerContent() {
  const navigate = useNavigate();
  const colors = useColors();
  const { data } = useMarketIndices();

  const allIndices = data?.indices ?? [];
  if (allIndices.length === 0) return null;

  // 前端只负责「挑出要展示的指数」；具体顺序由后端按 INDEX_FALLBACKS 归一。
  const selected = allIndices.filter(isHeaderTickerIndex).slice(0, HEADER_TICKER_INDEX_COUNT);

  const displayList = selected.length > 0 ? selected : allIndices.slice(0, HEADER_TICKER_INDEX_COUNT);

  return (
    <div
      className="header-market-ticker"
      role="region"
      aria-label="大盘即时指数"
      onClick={() => navigate("/market?tab=a-index")}
      title="点击查看大盘行情"
    >
      {displayList.map((idx) => {
        const changePct = idx.change_pct ?? 0;
        const isUp = changePct > 0;
        const isDown = changePct < 0;
        const color = isUp ? colors.up : isDown ? colors.down : colors.textSecondary;
        const prefix = isUp ? "+" : "";

        return (
          <div key={idx.code} className="header-market-ticker__item">
            <span className="header-market-ticker__name">{formatIndexName(idx.name)}</span>
            <span className="header-market-ticker__price financial-num">
              {idx.price != null ? idx.price.toFixed(2) : "--"}
            </span>
            <span
              className="header-market-ticker__pct financial-num"
              style={{ color }}
            >
              {idx.change_pct != null ? `${prefix}${idx.change_pct.toFixed(2)}%` : "--"}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export default function HeaderMarketTicker() {
  return (
    <TickerErrorBoundary fallback={null}>
      <TickerContent />
    </TickerErrorBoundary>
  );
}
