import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { DeleteOutlined, FileTextOutlined } from "@ant-design/icons";
import { Alert, Button, Card, DatePicker, Divider, message, Popconfirm, Skeleton, Space, Tag, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import dayjs from "dayjs";
import { useDailyReview, useDeleteDailyReview, useInfiniteDailyReviewHistory } from "../../api/queries";
import { streamDailyReview, type DailyReviewProgress } from "../../api/sse";
import { ApiError } from "../../api/client";
import PushModal from "../../components/PushModal";
import QueryErrorState from "../../components/QueryErrorState";
import SectionDataState from "../../components/SectionDataState";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowProgressPanel from "../../components/workflows/WorkflowProgressPanel";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { usePdfExport } from "../../hooks/usePdfExport";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import type { PushRequest } from "../../types/stock";
import { useColors, useStyles } from "../../styles/ui";
import { normalizeIsoDate } from "../../utils/date";

const { Title, Paragraph, Text } = Typography;

function formatDate(value: dayjs.Dayjs | null) {
  return value?.format("YYYY-MM-DD") ?? "";
}

function buildMoodSummary(review: NonNullable<ReturnType<typeof useDailyReview>["data"]>) {
  const rising = review.data_snapshot.indices.filter((item) => Number(item.change_pct ?? 0) > 0).length;
  const falling = review.data_snapshot.indices.filter((item) => Number(item.change_pct ?? 0) < 0).length;
  const strongestSector = review.data_snapshot.top_sectors?.[0];
  const weakestSector = review.data_snapshot.bottom_sectors?.[0];
  const indexMood = rising > falling ? "指数偏强" : rising < falling ? "指数偏弱" : "指数分化";
  const sectorMood = strongestSector && weakestSector
    ? `强势板块为${String(strongestSector.name)}，弱势板块为${String(weakestSector.name)}`
    : "板块强弱暂不明显";
  return `${indexMood}，${sectorMood}`;
}

function unwrapJsonBlock(value: string) {
  const text = value.trim();
  const match = text.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  return match ? match[1].trim() : text;
}

function stringifyReviewValue(value: unknown): string {
  if (value == null) return "";
  if (Array.isArray(value)) {
    return value
      .map((item) => typeof item === "string" ? `- ${item}` : `- ${stringifyReviewValue(item)}`)
      .join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => `- **${key}**：${stringifyReviewValue(item)}`)
      .join("\n");
  }
  return String(value);
}

function formatReviewTitle(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/([a-z])([A-Z])/g, "$1 $2")
    .replace(/^./, (char) => char.toUpperCase());
}

function renderReviewContent(value: string) {
  const text = unwrapJsonBlock(value);
  try {
    const parsed = JSON.parse(text) as unknown;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return Object.entries(parsed as Record<string, unknown>)
        .map(([key, item]) => `## ${formatReviewTitle(key)}\n\n${stringifyReviewValue(item)}`)
        .join("\n\n");
    }
    return stringifyReviewValue(parsed);
  } catch {
    return value;
  }
}

export default function DailyReviewPage() {
  const { cardStyle, pageContainerStyle } = useStyles();
  const c = useColors();
  const defaultDate = dayjs().format("YYYY-MM-DD");
  const [dateParam, setDate] = useUrlSearchParam("date", defaultDate, { replace: true });
  const date = normalizeIsoDate(dateParam, defaultDate);
  const selectedDate = dayjs(date);
  const exportRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const {
    data: historyPages,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: retryHistory,
    hasNextPage,
    fetchNextPage,
    isFetchingNextPage,
  } = useInfiniteDailyReviewHistory();
  const {
    data: review,
    isLoading: isReviewLoading,
    isError: isReviewError,
    error: reviewError,
    refetch: retryReview,
  } = useDailyReview(date);
  const deleteMutation = useDeleteDailyReview();
  const { push, isPushing } = useWorkflowPush();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationMessage, setGenerationMessage] = useState("");
  const cancelGenerationRef = useRef<(() => Promise<unknown>) | null>(null);
  const detachGenerationRef = useRef<(() => void) | null>(null);
  const cancellationRequestedRef = useRef(false);

  useEffect(() => {
    if (dateParam !== date) setDate(date);
  }, [date, dateParam, setDate]);

  useEffect(() => () => {
    detachGenerationRef.current?.();
    detachGenerationRef.current = null;
    cancelGenerationRef.current = null;
  }, []);

  const { exportPdf: handleExportPdf, isExporting: isExportingPdf } = usePdfExport({
    targetRef: exportRef,
    filename: () => `每日复盘-${date}.pdf`,
    backgroundColor: c.pageBg,
    onStart: () => message.loading({ content: "正在生成 PDF...", key: "daily-review-export" }),
    onSuccess: () => message.success({ content: "PDF 导出成功", key: "daily-review-export" }),
    onError: (error) => {
      console.error("[DailyReview] PDF 导出失败", error);
      message.error({ content: "PDF 导出失败，请稍后重试", key: "daily-review-export" });
    },
  });

  const historyItems = historyPages?.pages.flat() ?? [];

  const handleGenerate = async (force = false) => {
    if (!date) {
      message.warning("请先选择复盘日期");
      return;
    }
    if (cancelGenerationRef.current) await cancelGenerationRef.current();
    cancellationRequestedRef.current = false;
    setIsGenerating(true);
    setGenerationMessage("正在提交每日复盘任务");
    try {
      const stream = streamDailyReview({ date, force }, (event: DailyReviewProgress) => {
        if (event.message) setGenerationMessage(event.message);
      });
      cancelGenerationRef.current = stream.cancel;
      detachGenerationRef.current = stream.detach;
      const generated = await stream.promise;
      if (generated.date !== date) {
        setDate(generated.date);
        message.info(`所选日期不是已完成交易日，已生成 ${generated.date} 复盘`);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReviewHistoryRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReview(generated.date) }),
      ]);
      message.success(force ? "已重新生成复盘" : "已生成复盘");
    } catch (error) {
      if (cancellationRequestedRef.current && error instanceof Error
        && (error.message === "已取消" || error.message === "已停止等待")) {
        return;
      }
      message.error(`生成失败: ${String(error)}`);
    } finally {
      cancelGenerationRef.current = null;
      detachGenerationRef.current = null;
      setIsGenerating(false);
    }
  };

  const handleCancelGeneration = () => {
    cancellationRequestedRef.current = true;
    setGenerationMessage("正在取消每日复盘任务");
    void cancelGenerationRef.current?.().then((result) => {
      message.info(result === "detached" ? "已停止等待，后台共享任务仍在运行" : "已取消每日复盘任务");
    }).catch((error) => {
      cancellationRequestedRef.current = false;
      message.error(error instanceof Error ? error.message : "取消每日复盘失败");
    });
  };

  const handleDelete = async (deleteDate: string) => {
    try {
      await deleteMutation.mutateAsync(deleteDate);
      queryClient.removeQueries({ queryKey: queryKeys.workflows.dailyReview(deleteDate), exact: true });
      if (deleteDate === date) {
        const nextItem = historyItems.find((item) => item.date !== deleteDate);
        setDate(nextItem?.date || defaultDate);
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReviewHistoryRoot });
      message.success("复盘记录已删除");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除复盘记录失败");
    }
  };

  const handlePush = async (req: PushRequest) => {
    const response = await push(req);
    if (!response) return false;
    setPushModalOpen(false);
    return true;
  };

  return (
    <div style={pageContainerStyle}>
      <WorkflowPageHeader
        title="每日复盘"
        description="按日期生成并保存市场复盘历史"
        icon={<FileTextOutlined />}
        actions={(
          <Space wrap>
            <DatePicker
              value={selectedDate}
              allowClear={false}
              disabled={isGenerating || isExportingPdf}
              onChange={(value) => setDate(formatDate(value))}
              disabledDate={(value) => value.startOf("day").isAfter(dayjs().startOf("day"))}
            />
            <Button type="primary" loading={isGenerating} disabled={isExportingPdf} onClick={() => handleGenerate(false)}>生成复盘</Button>
            <Button loading={isGenerating} disabled={isExportingPdf} onClick={() => handleGenerate(true)}>重新生成</Button>
            {isGenerating && <Button danger onClick={handleCancelGeneration}>取消任务</Button>}
            <Button loading={isExportingPdf} onClick={handleExportPdf} disabled={!review || isGenerating}>导出 PDF</Button>
            <Button onClick={() => setPushModalOpen(true)} disabled={!review || isGenerating || isExportingPdf}>推送</Button>
            <PushModal
              open={pushModalOpen}
              type="daily_review"
              date={date}
              onConfirm={handlePush}
              onCancel={() => setPushModalOpen(false)}
              loading={isPushing}
            />
          </Space>
        )}
      />

      {isGenerating ? (
        <WorkflowProgressPanel
          current={0}
          status="running"
          message={generationMessage || "正在汇总市场数据并生成复盘报告"}
          items={[{ title: "生成每日复盘", status: "process" }]}
        />
      ) : null}

      <WorkflowWorkspace
        historyTitle="历史复盘"
        historyButtonLabel="历史复盘"
        historyVersion={date}
        history={(
          <SectionDataState
            isLoading={isHistoryLoading && historyItems.length === 0}
            error={isHistoryError && historyItems.length === 0 ? historyError : undefined}
            onRetry={() => retryHistory()}
            isEmpty={!isHistoryLoading && !isHistoryError && historyItems.length === 0}
            emptyText="暂无历史复盘"
            errorTitle="历史复盘加载失败"
            skeletonRows={5}
            minHeight={240}
          >
            <ul aria-label="复盘历史记录" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {historyItems.map((item) => (
                <li key={item.date} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  <button
                    type="button"
                    onClick={() => setDate(item.date)}
                    aria-pressed={item.date === date}
                    style={{
                      flex: 1,
                      minWidth: 0,
                      textAlign: "left",
                      padding: "12px 8px",
                      cursor: "pointer",
                      background: item.date === date ? c.activeBg : "transparent",
                      border: 0,
                      borderLeft: item.date === date ? `3px solid ${c.primary}` : "3px solid transparent",
                      borderRadius: 4,
                    }}
                  >
                    <span style={{ display: "block", fontWeight: 500 }}>{item.title}</span>
                    <Text type="secondary">{item.date}</Text>
                  </button>
                  {item.can_delete ? (
                    <Popconfirm
                      title="删除这条复盘记录？"
                      description="删除后无法恢复"
                      okText="删除"
                      cancelText="取消"
                      okButtonProps={{ danger: true }}
                      onConfirm={() => handleDelete(item.date)}
                    >
                      <Button
                        type="text"
                        danger
                        size="small"
                        icon={<DeleteOutlined />}
                        loading={deleteMutation.isPending && deleteMutation.variables === item.date}
                        aria-label={`删除 ${item.date} 复盘记录`}
                        onClick={(event) => {
                          event.preventDefault();
                          event.stopPropagation();
                        }}
                      />
                    </Popconfirm>
                  ) : null}
                </li>
              ))}
            </ul>
            {hasNextPage ? (
              <Button block loading={isFetchingNextPage} onClick={() => fetchNextPage()} style={{ marginTop: 12 }}>
                加载更多
              </Button>
            ) : null}
          </SectionDataState>
        )}
      >
        <div ref={exportRef}>
          {isReviewLoading ? (
            <Card style={cardStyle}>
              <div aria-label="复盘内容加载中" style={{ minHeight: 420, padding: 16 }}>
                <Skeleton active paragraph={{ rows: 10 }} />
              </div>
            </Card>
          ) : isReviewError && !(reviewError instanceof ApiError && reviewError.status === 404) ? (
            <QueryErrorState error={reviewError} onRetry={() => retryReview()} title="复盘内容加载失败" />
          ) : review ? (
            <Space orientation="vertical" size={16} style={{ width: "100%" }}>
              {(review.quality_status === "degraded" || review.session_status === "adjusted" || Boolean(review.warnings?.length)) && (
                <Alert
                  type={review.quality_status === "degraded" ? "warning" : "info"}
                  showIcon
                  title={review.quality_status === "degraded" ? "复盘数据或生成过程不完整" : "复盘日期已调整"}
                  description={(
                    <div>
                      {review.requested_date && review.effective_date && review.requested_date !== review.effective_date && (
                        <div>请求日期 {review.requested_date}，实际复盘交易日 {review.effective_date}</div>
                      )}
                      {review.warnings?.length ? <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>{review.warnings.map((item) => <li key={item}>{item}</li>)}</ul> : null}
                    </div>
                  )}
                />
              )}
              <Card style={cardStyle}>
                <Title level={4} style={{ marginTop: 0 }}>{review.title}</Title>
                <Paragraph>{review.market_summary}</Paragraph>
                <Paragraph><Text strong>市场情绪结论：</Text>{buildMoodSummary(review)}</Paragraph>
                <Space wrap>
                  <Tag style={{ background: `${c.primary}26`, color: c.primary, border: "none" }}>指数 {review.data_snapshot.indices.length}</Tag>
                  <Tag style={{ background: `${c.accent}26`, color: c.accent, border: "none" }}>热股 {review.data_snapshot.hot_stocks.length}</Tag>
                  <Tag style={{ background: `${c.accent}26`, color: c.accent, border: "none" }}>概念 {review.data_snapshot.hot_concepts.length}</Tag>
                  <Tag style={{ background: `${c.down}26`, color: c.down, border: "none" }}>行业 {review.data_snapshot.hot_industries.length}</Tag>
                  <Tag style={{ background: `${c.up}26`, color: c.up, border: "none" }}>龙虎榜 {review.data_snapshot.dragon_tiger.length}</Tag>
                </Space>
                <div style={{ marginTop: 8 }}>
                  <Text type="secondary">生成时间：{review.generated_at}</Text>
                </div>
                <div style={{ marginTop: 8, display: "flex", flexWrap: "wrap", gap: 6 }}>
                  <Tag color={review.quality_status === "degraded" ? "warning" : "success"}>质量：{review.quality_status === "degraded" ? "降级" : "完整"}</Tag>
                  <Tag color={review.generation_status === "fallback" ? "warning" : "processing"}>报告：{review.generation_status === "fallback" ? "确定性兜底" : "AI 生成"}</Tag>
                </div>
              </Card>
              {review.data_snapshot.source_status && (
                <Card title="复盘数据状态" style={cardStyle}>
                  <Space wrap>
                    {Object.entries(review.data_snapshot.source_status).map(([name, status]) => (
                      <Tag key={name} color={status.status === "complete" ? "success" : status.status === "partial" ? "warning" : "error"}>
                        {name}：{status.status === "complete" ? "完整" : status.status === "partial" ? "部分" : "不可用"}
                        {status.data_date ? ` (${status.data_date})` : ""}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}
              {review.llm_review ? (
                <Card title="复盘报告" style={{ ...cardStyle, background: c.nestedBg }}>
                  <ReactMarkdown>{renderReviewContent(review.llm_review)}</ReactMarkdown>
                </Card>
              ) : (
                <>
                  {[review.index_review, review.hotspot_review, review.dragon_tiger_review].map((section) => (
                    <Card key={section.title} title={section.title} style={cardStyle}>
                      <Paragraph>{section.summary}</Paragraph>
                      <ul>
                        {section.bullets.map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    </Card>
                  ))}
                  <Card title="机会与风险" style={cardStyle}>
                    <Paragraph><Text strong>机会：</Text>{review.opportunities.join("；") || "-"}</Paragraph>
                    <Paragraph><Text strong>风险：</Text>{review.risk_alerts.join("；") || "-"}</Paragraph>
                    <Paragraph><Text strong>策略：</Text>{review.strategy_notes.join("；") || "-"}</Paragraph>
                  </Card>
                  <Card title="原始数据快照" style={cardStyle}>
                    <Paragraph><Text strong>指数样本：</Text>{review.data_snapshot.indices.slice(0, 3).map((item) => String(item.name || item.code || "")).join("、") || "-"}</Paragraph>
                    <Divider style={{ margin: "12px 0" }} />
                    <Paragraph><Text strong>领涨板块：</Text>{review.data_snapshot.top_sectors?.slice(0, 5).map((item: Record<string, unknown>) => `${String(item.name || "")}(${String(item.change_pct ?? "-") }%)`).join("、") || "-"}</Paragraph>
                    <Divider style={{ margin: "12px 0" }} />
                    <Paragraph><Text strong>领跌板块：</Text>{review.data_snapshot.bottom_sectors?.slice(0, 5).map((item: Record<string, unknown>) => `${String(item.name || "")}(${String(item.change_pct ?? "-") }%)`).join("、") || "-"}</Paragraph>
                    <Divider style={{ margin: "12px 0" }} />
                    <Paragraph><Text strong>热点概念样本：</Text>{review.data_snapshot.hot_concepts.slice(0, 5).map((item) => String(item.name || item.code || "")).join("、") || "-"}</Paragraph>
                    <Divider style={{ margin: "12px 0" }} />
                    <Paragraph><Text strong>龙虎榜样本：</Text>{review.data_snapshot.dragon_tiger.slice(0, 5).map((item) => String(item.name || item.code || "")).join("、") || "-"}</Paragraph>
                  </Card>
                </>
              )}
            </Space>
          ) : (
            <Card style={cardStyle}><Paragraph type="secondary">请选择日期后生成复盘。</Paragraph></Card>
          )}
        </div>
      </WorkflowWorkspace>
    </div>
  );
}
