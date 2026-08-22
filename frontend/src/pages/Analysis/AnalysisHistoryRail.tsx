import { ClockCircleOutlined } from "@ant-design/icons";
import { Empty, Skeleton } from "antd";
import { useMemo } from "react";
import { useInfiniteAllAnalysisHistory } from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import type { AnalysisHistoryItem } from "../../types/stock";
import { buildAnalysisHistoryUrl, formatAnalysisDate } from "./analysisHistoryUrl";

function signalLabel(signal: string | null) {
  if (signal === "buy" || signal === "strong_buy") return "关注";
  if (signal === "sell" || signal === "strong_sell") return "谨慎";
  return "观察";
}

interface Props {
  currentCode?: string;
  currentDate?: string;
}

export default function AnalysisHistoryRail({ currentCode, currentDate }: Props) {
  const history = useInfiniteAllAnalysisHistory(30);
  const items = useMemo(() => {
    const all = history.data?.pages.flat() ?? [];
    const seen = new Set<string>();
    return all.filter((item: AnalysisHistoryItem) => {
      const key = `${item.stock_code}:${item.analysis_date}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).slice(0, 8);
  }, [history.data]);

  return (
    <aside className="analysis-workspace__history u-card" aria-label="最近分析记录">
      <div className="analysis-rail__header">
        <span><ClockCircleOutlined /> 最近分析</span>
        <small>{items.length} 条</small>
      </div>
      {history.isLoading ? <Skeleton active paragraph={{ rows: 6 }} title={false} /> : null}
      {!history.isLoading && items.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无记录" /> : null}
      <div className="analysis-history-list">
        {items.map((item) => {
          const selected = item.stock_code === currentCode
            && (!currentDate || item.analysis_date === currentDate);
          return (
            <PreloadLink
              className={`analysis-history-item${selected ? " is-active" : ""}`}
              aria-current={selected ? "page" : undefined}
              key={`${item.stock_code}:${item.analysis_date}`}
              to={buildAnalysisHistoryUrl(item.stock_code, item.analysis_date)}
            >
              <span className="analysis-history-item__name">{item.stock_name}</span>
              <span className="analysis-history-item__score">评分 {item.overall_rating?.toFixed(1) ?? "-"}</span>
              <span className="analysis-history-item__meta">{item.stock_code} · {formatAnalysisDate(item.analysis_date)}</span>
              <span className={`analysis-history-item__signal is-${signalLabel(item.signal)}`}>{signalLabel(item.signal)}</span>
            </PreloadLink>
          );
        })}
      </div>
      <PreloadLink className="analysis-rail__more" to="/analysis">查看全部分析记录</PreloadLink>
    </aside>
  );
}
