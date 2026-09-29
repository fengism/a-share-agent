import { useMemo, useState } from "react";
import type { InfiniteData } from "@tanstack/react-query";
import { DeleteOutlined, SearchOutlined } from "@ant-design/icons";
import { Button, Input, Popconfirm, Tag, Typography, message } from "antd";
import {
  useDeleteAnalysisHistory,
  useInfiniteAllAnalysisHistory,
} from "../../api/queries";
import PreloadLink from "../../components/PreloadLink";
import SectionDataState from "../../components/SectionDataState";
import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useColors, useTokens } from "../../styles/ui";
import type { AnalysisHistoryItem } from "../../types/stock";
import { formatAnalysisDate, normalizeAnalysisDate } from "./analysisHistoryUrl";
import "./analysis-history-manager.css";

const { Text } = Typography;

interface AnalysisHistoryManagerProps {
  buildHistoryUrl: (code: string, date: string) => string;
  currentCode?: string;
  currentDate?: string;
  onDeletedCurrent?: () => void;
  ariaLabel?: string;
  initialHistory?: InfiniteData<AnalysisHistoryItem[]>;
}

function signalLabel(signal: string | null) {
  if (signal === "strong_buy") return "强烈关注";
  if (signal === "buy") return "关注";
  if (signal === "sell") return "谨慎";
  if (signal === "strong_sell") return "回避";
  return "观察";
}

function signalColor(up: string, down: string, neutral: string, signal: string | null) {
  if (signal === "strong_buy" || signal === "buy") return up;
  if (signal === "strong_sell" || signal === "sell") return down;
  return neutral;
}

function groupByStock(items: AnalysisHistoryItem[]) {
  const groups = new Map<string, AnalysisHistoryItem[]>();
  for (const item of items) {
    const group = groups.get(item.stock_code) ?? [];
    group.push(item);
    groups.set(item.stock_code, group);
  }
  return [...groups.entries()];
}

export default function AnalysisHistoryManager({
  buildHistoryUrl,
  currentCode,
  currentDate,
  onDeletedCurrent,
  ariaLabel = "个股研究历史记录",
  initialHistory,
}: AnalysisHistoryManagerProps) {
  const colors = useColors();
  const t = useTokens();
  const [filter, setFilter] = useState("");
  const debouncedFilter = useDebouncedValue(filter, 250);
  const history = useInfiniteAllAnalysisHistory(50, debouncedFilter, initialHistory);
  const deleteMutation = useDeleteAnalysisHistory();
  const items = useMemo(() => history.data?.pages.flat() ?? [], [history.data]);
  const groups = useMemo(() => groupByStock(items), [items]);

  const handleDelete = async (item: AnalysisHistoryItem) => {
    const date = normalizeAnalysisDate(item.analysis_date);
    try {
      await deleteMutation.mutateAsync({ code: item.stock_code, date });
      if (item.stock_code === currentCode && date === normalizeAnalysisDate(currentDate)) {
        onDeletedCurrent?.();
      }
      message.success("分析记录已删除");
    } catch (error) {
      message.error(error instanceof Error ? error.message : "删除分析记录失败");
    }
  };

  return (
    <div className="analysis-history-manager">
      <Input
        aria-label="筛选研究历史"
        placeholder="按股票代码或名称筛选全部历史"
        prefix={<SearchOutlined />}
        value={filter}
        allowClear
        onChange={(event) => setFilter(event.target.value)}
        style={{ marginBottom: t.space[3] }}
      />
      <SectionDataState
        isLoading={history.isLoading && items.length === 0}
        error={history.isError && items.length === 0 ? history.error : undefined}
        onRetry={() => history.refetch()}
        isEmpty={!history.isLoading && !history.isError && items.length === 0}
        emptyText={debouncedFilter ? "未找到匹配的分析记录" : "暂无分析记录"}
        errorTitle="研究历史加载失败"
        skeletonRows={6}
        minHeight={240}
      >
        <div role="list" aria-label={ariaLabel}>
          {groups.map(([code, groupItems]) => (
            <section key={code} className="analysis-history-manager__group" aria-label={`${code} 研究历史`}>
              {groupItems.map((item) => {
                const itemDate = normalizeAnalysisDate(item.analysis_date);
                const selected = item.stock_code === currentCode
                  && itemDate === normalizeAnalysisDate(currentDate);
                const itemKey = `${item.stock_code}:${itemDate}`;
                const deleting = deleteMutation.isPending
                  && deleteMutation.variables?.code === item.stock_code
                  && deleteMutation.variables.date === itemDate;
                const tone = signalColor(colors.up, colors.down, colors.accent, item.signal);
                return (
                  <div key={itemKey} role="listitem" className="analysis-history-manager__item">
                    <PreloadLink
                      to={buildHistoryUrl(item.stock_code, item.analysis_date)}
                      aria-current={selected ? "page" : undefined}
                      className={selected ? "is-active" : undefined}
                    >
                      <span>
                        <strong>{item.stock_name || item.stock_code}</strong>
                        <Text type="secondary">{item.stock_code} · {formatAnalysisDate(item.analysis_date)}</Text>
                      </span>
                      <span className="analysis-history-manager__metrics">
                        <strong>{item.overall_rating?.toFixed(1) ?? "-"}</strong>
                        <Tag style={{ margin: 0, color: tone, borderColor: `${tone}66` }}>
                          {signalLabel(item.signal)}
                        </Tag>
                      </span>
                    </PreloadLink>
                    {item.can_delete ? (
                      <Popconfirm
                        title="删除这天的分析记录及全部版本？"
                        description="当天最新报告与该日所有历史版本都会删除，无法恢复"
                        okText="删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                        onConfirm={() => handleDelete(item)}
                      >
                        <Button
                          type="text"
                          danger
                          size="small"
                          icon={<DeleteOutlined />}
                          loading={deleting}
                          aria-label={`删除 ${item.stock_code} ${formatAnalysisDate(item.analysis_date)} 分析记录`}
                        />
                      </Popconfirm>
                    ) : null}
                  </div>
                );
              })}
            </section>
          ))}
        </div>
        {history.hasNextPage ? (
          <Button
            block
            size="small"
            loading={history.isFetchingNextPage}
            onClick={() => history.fetchNextPage()}
            style={{ marginTop: t.space[2] }}
          >
            加载更多
          </Button>
        ) : null}
      </SectionDataState>
    </div>
  );
}
