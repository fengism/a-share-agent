import { Button, Card, message, Popconfirm, Tag, Typography } from "antd";
import { DeleteOutlined, HistoryOutlined, RobotOutlined } from "@ant-design/icons";
import { Link } from "react-router-dom";
import SearchBar from "../Dashboard/SearchBar";
import { useDeleteAnalysisHistory, useInfiniteAllAnalysisHistory } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import type { AnalysisHistoryItem } from "../../types/stock";
import { useColors } from "../../styles/ui";

const { Title, Paragraph } = Typography;

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
  const allHistory = historyPages?.pages.flat() ?? [];

  const grouped = groupByStock(allHistory);

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
    <div className="two-pane" style={{ display: "flex", gap: 20, minHeight: "calc(100vh - 120px)" }}>
      {/* Left: History Panel */}
      <div className="pane-side" style={{ width: 280, flexShrink: 0 }}>
        <Card
          style={{ background: c.cardBg, border: `1px solid ${c.border}`, borderRadius: 10, height: "100%" }}
          styles={{ body: { padding: 0 } }}
        >
          <div style={{ padding: "14px 16px 10px", borderBottom: `1px solid ${c.border}` }}>
            <span style={{ fontWeight: 600, color: c.textPrimary, fontSize: 14 }}>
              <HistoryOutlined style={{ marginRight: 8, color: c.primary }} />
              分析历史
            </span>
          </div>
          <div style={{ maxHeight: "calc(100vh - 220px)", overflowY: "auto", padding: "8px 10px" }}>
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
                {Object.entries(grouped).map(([code, items]) => (
                  <div key={code} style={{ marginBottom: 10 }}>
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
                          className="hover-row"
                          style={{
                            display: "flex", justifyContent: "space-between", alignItems: "center",
                            padding: "0 4px 0 0", marginBottom: 4,
                            borderRadius: 8,
                          }}
                        >
                          <Link
                            to={`/analysis/${code}`}
                            style={{
                              display: "flex", flex: 1, minWidth: 0, justifyContent: "space-between", alignItems: "center",
                              padding: "8px 6px 8px 10px", color: "inherit", textDecoration: "none",
                            }}
                          >
                            <div style={{ display: "flex", flexDirection: "column", gap: 2, minWidth: 0 }}>
                              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                                <span style={{ fontSize: 12, color: c.primary, fontFamily: "monospace", fontWeight: 600 }}>{item.stock_code}</span>
                                <span style={{ fontSize: 12, color: c.textPrimary, fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{item.stock_name}</span>
                              </div>
                              <span style={{ fontSize: 11, color: c.textSecondary }}>{displayDate}</span>
                            </div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                              {item.overall_rating != null && (
                                <span style={{ fontSize: 12, fontWeight: 700, color: item.overall_rating >= 7 ? c.up : item.overall_rating <= 3 ? c.down : c.textPrimary }}>
                                  {item.overall_rating}
                                </span>
                              )}
                              {item.signal && (
                                <Tag style={{ color: sc, background: "transparent", border: `1px solid ${sc}33`, fontSize: 11, margin: 0, padding: "0 4px" }}>
                                  {signalLabel(item.signal)}
                                </Tag>
                              )}
                            </div>
                          </Link>
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
                {hasNextPage && (
                  <Button
                    block
                    size="small"
                    loading={isFetchingNextPage}
                    onClick={() => fetchNextPage()}
                    style={{ marginTop: 8 }}
                  >
                    加载更多
                  </Button>
                )}
              </>
            </SectionDataState>
          </div>
        </Card>
      </div>

      {/* Right: Search / Landing */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "60px 24px" }}>
        <div style={{ textAlign: "center", marginBottom: 48 }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>
            <RobotOutlined style={{ color: c.accent, marginRight: 12 }} />
          </div>
          <Title level={2} style={{ margin: 0, color: c.textPrimary }}>AI 智能分析</Title>
          <Paragraph style={{ fontSize: 16, marginTop: 8, color: c.textSecondary }}>
            输入股票代码或名称，进入独立分析页，查看基本面、技术面、情绪面与 AI 结论
          </Paragraph>
        </div>
        <Card
          style={{
            borderRadius: 10, boxShadow: "0 1px 2px rgba(0,0,0,0.18)",
            padding: "8px 0", width: "100%", maxWidth: 560,
            background: c.cardBg, border: `1px solid ${c.border}`,
          }}
          styles={{ body: { padding: "24px 24px 16px", display: "flex", justifyContent: "center" } }}
        >
          <SearchBar />
        </Card>
      </div>
    </div>
  );
}
