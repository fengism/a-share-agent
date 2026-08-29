import { ClockCircleOutlined } from "@ant-design/icons";
import { Button, Empty, Skeleton, Typography } from "antd";
import { useMemo } from "react";
import { useInfiniteAllAnalysisHistory } from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import type { AnalysisHistoryItem } from "../../types/stock";
import { buildAnalysisHistoryUrl, formatAnalysisDate, normalizeAnalysisDate } from "./analysisHistoryUrl";
import "./analysis-history-rail.css";

function signalLabel(signal: string | null) {
  if (signal === "buy" || signal === "strong_buy") return "关注";
  if (signal === "sell" || signal === "strong_sell") return "谨慎";
  return "观察";
}

interface Props {
  currentCode?: string;
  currentDate?: string;
  buildHistoryUrl?: (code: string, date: string) => string;
  allHistoryTarget?: string;
  embedded?: boolean;
}

export default function AnalysisHistoryRail({
  currentCode,
  currentDate,
  buildHistoryUrl = buildAnalysisHistoryUrl,
  allHistoryTarget = "/analysis",
  embedded = false,
}: Props) {
  const history = useInfiniteAllAnalysisHistory(8);
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
    <aside className={embedded ? "analysis-history-rail" : "analysis-workspace__history u-card"} aria-label="最近分析记录">
      <div className="analysis-rail__header">
        <span><ClockCircleOutlined /> 最近分析</span>
        <small>{items.length} 条</small>
      </div>
      {history.isLoading ? <Skeleton active paragraph={{ rows: 6 }} title={false} /> : null}
      {history.isError && items.length === 0 ? (
        <div role="alert" style={{ display: "grid", gap: 8, justifyItems: "start" }}>
          <Typography.Text type="danger">最近分析加载失败</Typography.Text>
          <Button size="small" onClick={() => void history.refetch()}>重试</Button>
        </div>
      ) : null}
      {!history.isLoading && !history.isError && items.length === 0 ? <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无记录" /> : null}
      <div className="analysis-history-list">
        {items.map((item) => {
          const itemDate = normalizeAnalysisDate(item.analysis_date);
          const currentItemDate = normalizeAnalysisDate(currentDate);
          const selected = item.stock_code === currentCode
            && Boolean(currentItemDate)
            && itemDate === currentItemDate;
          return (
            <PreloadLink
              className={`analysis-history-item${selected ? " is-active" : ""}`}
              aria-current={selected ? "page" : undefined}
              key={`${item.stock_code}:${item.analysis_date}`}
              to={buildHistoryUrl(item.stock_code, item.analysis_date)}
            >
              <span className="analysis-history-item__name">{item.stock_name}</span>
              <span className="analysis-history-item__score">评分 {item.overall_rating?.toFixed(1) ?? "-"}</span>
              <span className="analysis-history-item__meta">{item.stock_code} · {formatAnalysisDate(item.analysis_date)}</span>
              <span className={`analysis-history-item__signal is-${signalLabel(item.signal)}`}>{signalLabel(item.signal)}</span>
            </PreloadLink>
          );
        })}
      </div>
      <PreloadLink className="analysis-rail__more" to={allHistoryTarget}>查看全部分析记录</PreloadLink>
    </aside>
  );
}
