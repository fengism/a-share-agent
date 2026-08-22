import { useMemo, useState } from "react";
import { Button, Card, Empty, Input, message, Popconfirm, Tag, Typography } from "antd";
import { DeleteOutlined, RobotOutlined, SearchOutlined } from "@ant-design/icons";
import SearchBar from "../../features/stock-search/SearchBar";
import { useDeleteAnalysisHistory, useInfiniteAllAnalysisHistory } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import type { AnalysisHistoryItem } from "../../types/stock";
import { useColors, useStyles, useTokens } from "../../styles/ui";
import { filterAnalysisHistory } from "./analysisHistoryFilter";
import { buildAnalysisHistoryUrl } from "./analysisHistoryUrl";
import PreloadLink from "../../components/PreloadLink";

const { Paragraph } = Typography;

function signalColor(c_up: string, c_down: string, c_default: string, signal: string | null) {
  if (signal === "strong_buy" || signal === "buy") return c_up;
  if (signal === "strong_sell" || signal === "sell") return c_down;
  return c_default;
}

function signalLabel(signal: string | null) {
  if (signal === "strong_buy") return "强烈买入";
  if (signal === "buy") return "买入";
  if (signal === "sell") return "卖出";
  if (signal === "strong_sell") return "强烈卖出";
  return "持有";
}

function groupByStock(items: AnalysisHistoryItem[]): Record<string, AnalysisHistoryItem[]> {
  const groups: Record<string, AnalysisHistoryItem[]> = {};
  for (const item of items) {
    const key = item.stock_code;
    if (!groups[key]) groups[key] = [];
    groups[key].push(item);
  }
  for (const code of Object.keys(groups)) {
    groups[code].sort((a, b) => b.analysis_date.localeCompare(a.analysis_date));
  }
  return groups;
}

export default function AnalysisEntry() {
  const c = useColors();
  const t = useTokens();
  const { pageContainerStyle } = useStyles();
  const {
    data: historyPages,
    isLoading,
    isError,
    error,
    refetch,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteAllAnalysisHistory();
  const deleteMutation = useDeleteAnalysisHistory();
  const [historyFilter, setHistoryFilter] = useState("");
  const allHistory = useMemo(() => historyPages?.pages.flat() ?? [], [historyPages]);
  const filteredHistory = useMemo(
    () => filterAnalysisHistory(allHistory, historyFilter),
    [allHistory, historyFilter],
  );
  const grouped = useMemo(() => groupByStock(filteredHistory), [filteredHistory]);

  const handleDelete = async (item: AnalysisHistoryItem) => {
    try {
      await deleteMutation.mutateAsync({ code: item.stock_code, date: item.analysis_date });
      await refetch();
      message.success("分析记录已删除");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除分析记录失败");
    }
  };

  return (
    <div style={pageContainerStyle}>
      <WorkflowPageHeader
        title="AI 智能分析"
        description="输入股票代码或名称，查看基本面、技术面、情绪面与 AI 结论"
        icon={<RobotOutlined />}
      />
      <WorkflowWorkspace
        historyTitle="分析历史"
        historyButtonLabel="分析历史"
        history={(
          <div>
            <Input
              aria-label="筛选分析历史"
              placeholder="按股票代码或名称筛选"
              prefix={<SearchOutlined />}
              value={historyFilter}
              allowClear
              onChange={(event) => setHistoryFilter(event.target.value)}
              style={{ marginBottom: t.space[3] }}
            />
            <SectionDataState
              isLoading={isLoading && allHistory.length === 0}
              error={isError && allHistory.length === 0 ? error : undefined}
              onRetry={() => refetch()}
              isEmpty={!isLoading && !isError && allHistory.length === 0}
              emptyText="暂无分析记录"
              errorTitle="分析历史加载失败"
              skeletonRows={6}
              minHeight={260}
            >
              <>
                {filteredHistory.length === 0 ? (
                  <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="未找到匹配的分析记录" />
                ) : (
                  <div role="list" aria-label="个股分析历史记录">
                    {Object.entries(grouped).map(([code, items]) => (
                      <div key={code} role="group" aria-label={`${code} 分析历史`} style={{ marginBottom: t.space[3] }}>
                        {items.map((item) => {
                          const dateStr = item.analysis_date;
                          const displayDate = `${dateStr.slice(0, 4)}-${dateStr.slice(4, 6)}-${dateStr.slice(6, 8)}`;
                          const sc = signalColor(c.up, c.down, c.textPrimary, item.signal);
                          const itemKey = `${code}-${dateStr}`;
                          const isDeleting = deleteMutation.isPending
                            && `${deleteMutation.variables?.code}-${deleteMutation.variables?.date}` === itemKey;
                          return (
                            <div
                              key={itemKey}
                              role="listitem"
                              className="hover-row"
                              style={{
                                display: "flex", justifyContent: "space-between", alignItems: "center",
                                padding: `0 ${t.space[1]} 0 0`, marginBottom: t.space[1],
                                borderRadius: t.radius.md,
                              }}
                            >
                              <PreloadLink
                                to={buildAnalysisHistoryUrl(code, dateStr)}
                                aria-label={`查看 ${item.stock_name || code} ${displayDate} 分析记录`}
                                style={{
                                  display: "flex", flex: 1, minWidth: 0, justifyContent: "space-between", alignItems: "center",
                                  padding: `${t.space[2]} ${t.space[2]} ${t.space[2]} ${t.space[3]}`, color: "inherit", textDecoration: "none",
                                }}
                              >
                                <div style={{ display: "flex", flexDirection: "column", gap: t.space[1], minWidth: 0 }}>
                                  <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
                                    <span style={{ fontSize: t.font.sm, color: c.primary, fontFamily: "monospace", fontWeight: Number(t.weight.semibold) }}>{item.stock_code}</span>
                                    <span style={{ fontSize: t.font.sm, color: c.textPrimary, fontWeight: Number(t.weight.medium), overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.stock_name}</span>
                                  </div>
                                  <span style={{ fontSize: t.font.xs, color: c.textSecondary }}>{displayDate}</span>
                                </div>
                                <div style={{ display: "flex", alignItems: "center", gap: t.space[2], flexShrink: 0 }}>
                                  {item.overall_rating != null && (
                                    <span style={{ fontSize: t.font.sm, fontWeight: Number(t.weight.bold), color: item.overall_rating >= 7 ? c.up : item.overall_rating <= 3 ? c.down : c.textPrimary }}>
                                      {item.overall_rating}
                                    </span>
                                  )}
                                  {item.signal && (
                                    <Tag style={{ color: sc, background: "transparent", border: `1px solid ${sc}33`, fontSize: t.font.xs, margin: 0, padding: `0 ${t.space[1]}` }}>
                                      {signalLabel(item.signal)}
                                    </Tag>
                                  )}
                                </div>
                              </PreloadLink>
                              {item.can_delete ? (
                                <Popconfirm
                                  title="删除这条分析记录？"
                                  description="删除后无法恢复"
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
                                    loading={isDeleting}
                                    aria-label={`删除 ${item.stock_code} ${displayDate} 分析记录`}
                                    onClick={(event) => {
                                      event.preventDefault();
                                      event.stopPropagation();
                                    }}
                                  />
                                </Popconfirm>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                    ))}
                  </div>
                )}
                {hasNextPage && (
                  <Button
                    block
                    size="small"
                    loading={isFetchingNextPage}
                    onClick={() => fetchNextPage()}
                    style={{ marginTop: t.space[2] }}
                  >
                    加载更多
                  </Button>
                )}
              </>
            </SectionDataState>
          </div>
        )}
      >
        <div style={{ minHeight: "calc(100vh - 260px)", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: `${t.space[8]} ${t.space[6]}` }}>
          <div style={{ textAlign: "center", marginBottom: t.space[7] }}>
            <div style={{ fontSize: t.font.display, marginBottom: t.space[2] }}>
              <RobotOutlined style={{ color: c.accent }} />
            </div>
            <Paragraph style={{ fontSize: t.font.lg, margin: 0, color: c.textSecondary }}>
              选择一只股票，进入独立分析页
            </Paragraph>
          </div>
          <Card
            style={{
              borderRadius: t.radius.lg, boxShadow: t.shadow.xs,
              padding: `${t.space[2]} 0`, width: "100%", maxWidth: 560,
              background: c.cardBg, border: `1px solid ${c.border}`,
            }}
            styles={{ body: { padding: `${t.space[6]} ${t.space[6]} ${t.space[4]}`, display: "flex", justifyContent: "center" } }}
          >
            <SearchBar />
          </Card>
        </div>
      </WorkflowWorkspace>
    </div>
  );
}
