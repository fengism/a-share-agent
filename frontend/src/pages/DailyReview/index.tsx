import { useDailyReviewWorkflowStore } from "../../store/dailyReviewWorkflowStore";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import {
  BulbOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownOutlined,
  DownloadOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  MoreOutlined,
  RiseOutlined,
  SearchOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Divider,
  Dropdown,
  Input,
  message,
  Popconfirm,
  Skeleton,
  Space,
  Tag,
  Typography,
} from "antd";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import dayjs from "dayjs";
import {
  downloadDailyReviewPdf,
  useDailyReview,
  useDeleteDailyReview,
  useInfiniteDailyReviewHistory,
} from "../../api/queries";
import { startDailyReviewWorkflow } from "../../features/workflows/workflowRuntime";
import {
  DAILY_REVIEW_STAGES,
  buildDailyReviewStepItems,
} from "./progress";
import { ApiError } from "../../api/client";
import PushModal from "../../components/PushModal";
import QueryErrorState from "../../components/QueryErrorState";
import SectionDataState from "../../components/SectionDataState";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowProgressPanel from "../../components/workflows/WorkflowProgressPanel";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import type { PushRequest } from "../../types/stock";
import { useColors, useStyles } from "../../styles/ui";
import { normalizeIsoDate } from "../../utils/date";
import DailyReviewCharts from "./DailyReviewCharts";
import DailyReviewHero from "./DailyReviewHero";
import SectionAnchorNav from "../../components/SectionAnchorNav";
import CollapsibleSection from "../../components/CollapsibleSection";
import PreviousCheckCard from "./sections/PreviousCheckCard";
import CycleTrendTimeline from "./sections/CycleTrendTimeline";
import {
  eventDirectionLabels,
  eventHorizonLabels,
  eventTimingLabels,
  eventTypeLabels,
} from "./reviewLabels";
import {
  buildDailyReviewMarkdown,
  renderReviewContent,
} from "./reviewMarkdown";
import {
  buildCheckAccuracy,
  buildMoodSummary,
  buildReviewHeadline,
  buildReviewSections,
  type DailyReviewPayload,
  type ReviewSectionDescriptor,
} from "./reviewView";
import "./daily-review.css";

function formatDate(value: dayjs.Dayjs | null) {
  return value?.format("YYYY-MM-DD") ?? "";
}

const { Paragraph, Text } = Typography;

export default function DailyReviewPage() {
  const { cardStyle, pageContainerStyle } = useStyles();
  const c = useColors();
  const defaultDate = dayjs().format("YYYY-MM-DD");
  const [dateParam, setDate] = useUrlSearchParam("date", defaultDate, { replace: true });
  const date = normalizeIsoDate(dateParam, defaultDate);
  const selectedDate = dayjs(date);
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

  // 视图模型：Hero 指标、章节清单与自检命中率（页面/导出/长图共用）
  const reviewView = (review ?? null) as DailyReviewPayload | null;
  const headline = useMemo(() => (reviewView ? buildReviewHeadline(reviewView) : null), [reviewView]);
  const moodSummary = useMemo(() => (reviewView ? buildMoodSummary(reviewView) : ""), [reviewView]);
  const checkAccuracy = useMemo(() => (reviewView ? buildCheckAccuracy(reviewView) : null), [reviewView]);
  const sections = useMemo<ReviewSectionDescriptor[]>(
    () => (reviewView ? buildReviewSections(reviewView) : []),
    [reviewView],
  );
  const sectionItems = useMemo(
    () => sections.map((section) => ({
      id: section.id,
      label: section.title,
      badge: section.count ? `${section.count} 条` : undefined,
    })),
    [sections],
  );
  const sectionSummary = useCallback(
    (id: string) => {
      const target = sections.find((section) => section.id === id);
      return target?.count ? `${target.count} 条` : undefined;
    },
    [sections],
  );
  const [openSectionParam, setOpenSectionParam] = useUrlSearchParam("section", "", { replace: true });
  const openSectionId = openSectionParam;
  const handleSectionToggle = useCallback(
    (id: string, next: boolean) => {
      setOpenSectionParam(next ? id : "");
    },
    [setOpenSectionParam],
  );

  const { push, isPushing } = useWorkflowPush();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [historyFilter, setHistoryFilter] = useState("");
  const generation = useDailyReviewWorkflowStore();
  const isGenerating = generation.isGenerating;
  const generationMessage = generation.message;
  const generationProgress = generation.progress;

  useEffect(() => {
    if (dateParam !== date) setDate(date);
  }, [date, dateParam, setDate]);


  const handleExportPdf = async () => {
    setIsExportingPdf(true);
    message.loading({ content: "正在生成 PDF...", key: "daily-review-export" });
    try {
      await downloadDailyReviewPdf(date);
      message.success({ content: "PDF 导出成功", key: "daily-review-export" });
    } catch (error) {
      console.error("[DailyReview] PDF 导出失败", error);
      message.error({
        content: error instanceof Error ? error.message : "PDF 导出失败，请稍后重试",
        key: "daily-review-export",
      });
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleExportMarkdown = () => {
    if (!review) return;
    const content = buildDailyReviewMarkdown(review);
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `每日复盘_${review.date}.md`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
    message.success("Markdown 文件已导出");
  };

  const handleCopyMarkdown = async () => {
    if (!review) return;
    const content = buildDailyReviewMarkdown(review);
    try {
      await navigator.clipboard.writeText(content);
      message.success("复盘内容已复制到剪贴板");
    } catch {
      message.error("复制到剪贴板失败，请手动选择复制");
    }
  };

  const historyItems = historyPages?.pages.flat() ?? [];
  const filteredHistoryItems = historyItems.filter((item) =>
    !historyFilter.trim() || item.date.includes(historyFilter.trim()) || item.title.includes(historyFilter.trim()),
  );

  const handleGenerate = async (force = false) => {
    if (!date) {
      message.warning("请先选择复盘日期");
      return;
    }
    const store = useDailyReviewWorkflowStore.getState();
    if (store.isGenerating) await store.cancelActiveRun();
    startDailyReviewWorkflow(date, force);
  };

  const handleCancelGeneration = () => {
    const store = useDailyReviewWorkflowStore.getState();
    if (!store.isGenerating || store.isCancelling) return;
    void store.cancelActiveRun().then((result) => {
      message.info(result === "detached" ? "已停止等待，后台共享任务仍在运行" : "已取消每日复盘任务");
    }).catch(() => {
      message.error("取消每日复盘失败");
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
            {isGenerating ? (
              <Button danger onClick={handleCancelGeneration}>取消任务</Button>
            ) : (
              <Dropdown
                trigger={["click"]}
                menu={{
                  items: [
                    { key: "generate", label: review ? "重新生成复盘" : "生成复盘" },
                    ...(review ? [{ key: "force", label: "强制重新生成（忽略缓存）" }] : []),
                  ],
                  onClick: ({ key }) => {
                    void handleGenerate(key === "force");
                  },
                }}
              >
                <Button type="primary" loading={isGenerating} disabled={isExportingPdf}>
                  {review ? "重新生成" : "生成复盘"} <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} />
                </Button>
              </Dropdown>
            )}
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "pdf", label: "导出为 PDF (.pdf)", icon: <FilePdfOutlined />, disabled: isExportingPdf },
                  { key: "md", label: "导出为 Markdown (.md)", icon: <FileMarkdownOutlined /> },
                  { key: "copy", label: "复制复盘内容", icon: <CopyOutlined /> },
                  { key: "push", label: "推送到群聊", disabled: isExportingPdf },
                ],
                onClick: ({ key }) => {
                  if (key === "pdf") void handleExportPdf();
                  else if (key === "md") handleExportMarkdown();
                  else if (key === "copy") void handleCopyMarkdown();
                  else if (key === "push") setPushModalOpen(true);
                },
              }}
              disabled={!review || isGenerating}
            >
              <Button icon={<DownloadOutlined />} loading={isExportingPdf} aria-label="导出">
                导出 <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} />
              </Button>
            </Dropdown>
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  { key: "today", label: "切换到今日" },
                  { key: "prev", label: "切换到前一日" },
                  { key: "push", label: "推送到群聊", disabled: !review || isExportingPdf },
                ],
                onClick: ({ key }) => {
                  if (key === "today") setDate(dayjs().format("YYYY-MM-DD"));
                  else if (key === "prev") setDate(dayjs().subtract(1, "day").format("YYYY-MM-DD"));
                  else if (key === "push") setPushModalOpen(true);
                },
              }}
            >
              <Button icon={<MoreOutlined />} aria-label="更多操作" />
            </Dropdown>
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
          current={Math.min(generationProgress.done.length, DAILY_REVIEW_STAGES.length - 1)}
          status="running"
          message={generationMessage || "正在汇总市场数据并生成复盘报告"}
          items={buildDailyReviewStepItems(generationProgress)}
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
            {historyItems.length > 3 ? (
              <Input
                size="small"
                prefix={<SearchOutlined style={{ color: "var(--c-text-muted)" }} />}
                placeholder="搜索历史复盘..."
                value={historyFilter}
                onChange={(e) => setHistoryFilter(e.target.value)}
                allowClear
                style={{ marginBottom: 8 }}
              />
            ) : null}
            <ul aria-label="复盘历史记录" style={{ listStyle: "none", margin: 0, padding: 0 }}>
              {filteredHistoryItems.map((item) => (
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
                    <span style={{ display: "block", fontWeight: "var(--c-weight-medium)" }}>{item.title}</span>
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
        <div>
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
            {review.notes?.length ? (
              <Alert
                type="info"
                showIcon
                title="部分辅助数据缺失（不影响复盘结论）"
                description={(
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {review.notes.map((item) => <li key={item}>{item}</li>)}
                  </ul>
                )}
              />
            ) : null}
              <DailyReviewHero
                review={review}
                headline={headline!}
                moodSummary={moodSummary}
                checkAccuracy={checkAccuracy}
              />

              <SectionAnchorNav
                items={sectionItems}
                ariaLabel="复盘章节导航"
              />

              <CollapsibleSection id="review-charts" title="市场图谱" defaultOpen>
            <div className="daily-review-block">
              <DailyReviewCharts snapshot={review.data_snapshot} />
            </div>
              </CollapsibleSection>

              <CollapsibleSection
                id="review-policy"
                title="政策与事件传导"
                summary={sectionSummary("review-policy")}
                open={openSectionId === "review-policy"}
                onOpenChange={(next) => handleSectionToggle("review-policy", next)}
              >
            {review.news_policy_review || review.event_impacts?.length ? (
              <div className="daily-review-block">
                {review.news_policy_review ? (
                  <>
                    <Paragraph>{review.news_policy_review.summary}</Paragraph>
                    {review.news_policy_review.bullets.length ? (
                      <ul className="daily-review-policy-bullets">
                        {review.news_policy_review.bullets.map((item) => <li key={item}>{item}</li>)}
                      </ul>
                    ) : null}
                  </>
                ) : null}
                {review.event_impacts?.length ? (
                  <div className="daily-review-event-grid">
                    {review.event_impacts.map((impact, index) => (
                      <article key={`${impact.event_title}-${index}`} className={`daily-review-event-card is-${impact.direction}`}>
                        <div className="daily-review-event-card__header">
                          <strong>{impact.event_title}</strong>
                          <Space size={4} wrap>
                            <Tag>{eventTypeLabels[impact.event_type]}</Tag>
                            <Tag>{eventDirectionLabels[impact.direction]}</Tag>
                            <Tag>{eventHorizonLabels[impact.horizon]}</Tag>
                            <Tag color={impact.timing === "after" ? "warning" : undefined}>{eventTimingLabels[impact.timing]}</Tag>
                          </Space>
                        </div>
                        <Paragraph><Text strong>影响方向：</Text>{impact.affected_sectors.join("、") || "市场整体"}</Paragraph>
                        <Paragraph><Text strong>传导链：</Text>{impact.transmission_chain || "待盘面验证"}</Paragraph>
                        <Paragraph><Text strong>事实证据：</Text>{impact.evidence || "-"}</Paragraph>
                        <Paragraph><Text strong>盘面验证：</Text>{impact.market_confirmation || "尚未核验"}</Paragraph>
                        {impact.timing === "after" ? (
                          <Paragraph type="warning">该事件发布于复盘日之后，仅用于事后验证，不作为当日交易依据。</Paragraph>
                        ) : null}
                        <Paragraph><Text strong>确认信号：</Text>{impact.confirmation_signals.join("；") || "待观察"}</Paragraph>
                        <Paragraph><Text strong>失效条件：</Text>{impact.invalidation_conditions.join("；") || "待观察"}</Paragraph>
                      </article>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
              </CollapsibleSection>

              <CollapsibleSection
                id="review-sentiment"
                title="情绪周期定位"
                summary={sectionSummary("review-sentiment")}
                open={openSectionId === "review-sentiment"}
                onOpenChange={(next) => handleSectionToggle("review-sentiment", next)}
              >
            {review.sentiment_cycle ? (
              <div className="daily-review-block">
                <Space wrap>
                  <Tag color="processing" style={{ fontSize: "var(--c-font-base)" }}>{review.sentiment_cycle.stage}</Tag>
                  {review.sentiment_cycle.ladder_health ? (
                    <Text type="secondary">梯队健康度：{review.sentiment_cycle.ladder_health}</Text>
                  ) : null}
                </Space>
                {review.sentiment_cycle.evidence?.length ? (
                  <ul style={{ margin: "10px 0 0", paddingLeft: 18 }}>
                    {review.sentiment_cycle.evidence.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}

              </CollapsibleSection>

              <CollapsibleSection
                id="review-scenarios"
                title="明日三情景预案"
                summary={sectionSummary("review-scenarios")}
                open={openSectionId === "review-scenarios"}
                onOpenChange={(next) => handleSectionToggle("review-scenarios", next)}
              >
            {review.scenario_plans?.length ? (
              <div className="daily-review-block">
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
                  {review.scenario_plans.map((scenario) => (
                    <div key={scenario.name} style={{ padding: "var(--c-pad-inset, 7px 12px)", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                      <Text strong>{scenario.name}</Text>
                      <Paragraph style={{ margin: "6px 0 0" }}><Text strong>触发：</Text>{scenario.trigger || "待补充"}</Paragraph>
                      <Paragraph style={{ margin: "4px 0 0" }}><Text strong>应对：</Text>{scenario.playbook || "待补充"}</Paragraph>
                      {scenario.watch_levels?.length ? (
                        <Paragraph type="secondary" style={{ margin: "4px 0 0" }}>观察信号：{scenario.watch_levels.join("；")}</Paragraph>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

              </CollapsibleSection>

              <CollapsibleSection
                id="review-watchlist"
                title="次日观察锚点"
                summary={sectionSummary("review-watchlist")}
                open={openSectionId === "review-watchlist"}
                onOpenChange={(next) => handleSectionToggle("review-watchlist", next)}
              >
            {review.next_day_watchlist?.length ? (
              <div className="daily-review-block">
                <div style={{ display: "flex", flexDirection: "column", gap: 8, width: "100%" }}>
                  {review.next_day_watchlist.map((item) => (
                    <div key={`${item.name}-${item.role}`} style={{ padding: "var(--c-pad-inset, 7px 12px)", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                      <Space wrap>
                        <Text strong>{item.name}</Text>
                        <Tag color="blue">{item.role}</Tag>
                      </Space>
                      <Paragraph style={{ margin: "6px 0 0" }}>{item.reason || "待补充"}</Paragraph>
                      <Paragraph type="secondary" style={{ margin: "4px 0 0" }}>触发：{item.trigger || "待补充"}</Paragraph>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

              </CollapsibleSection>

              <CollapsibleSection
                id="review-key-levels"
                title="关键点位与量能阈值"
                summary={sectionSummary("review-key-levels")}
                open={openSectionId === "review-key-levels"}
                onOpenChange={(next) => handleSectionToggle("review-key-levels", next)}
              >
            {review.key_levels?.length ? (
              <div className="daily-review-block">
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  {review.key_levels.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            ) : null}

              </CollapsibleSection>

              {review.previous_review_check ? (
                <CollapsibleSection
                  id="review-self-check"
                  title="昨日复盘自检"
                  summary={sectionSummary("review-self-check")}
                  open={openSectionId === "review-self-check"}
                  onOpenChange={(next) => handleSectionToggle("review-self-check", next)}
                >
                  <PreviousCheckCard check={review.previous_review_check} accuracy={checkAccuracy} />
                </CollapsibleSection>
              ) : null}

              {review.cycle_trend?.points?.length ? (
                <CollapsibleSection
                  id="review-cycle-trend"
                  title="情绪周期历史趋势"
                  summary={sectionSummary("review-cycle-trend")}
                  open={openSectionId === "review-cycle-trend"}
                  onOpenChange={(next) => handleSectionToggle("review-cycle-trend", next)}
                >
                  <CycleTrendTimeline trend={review.cycle_trend} />
                </CollapsibleSection>
              ) : null}

              <CollapsibleSection
                id="review-data-status"
                title="复盘数据状态"
                summary={sectionSummary("review-data-status")}
                open={openSectionId === "review-data-status"}
                onOpenChange={(next) => handleSectionToggle("review-data-status", next)}
              >
            {review.data_snapshot.source_status ? (
              <div className="daily-review-block">
                <Space wrap>
                  {Object.entries(review.data_snapshot.source_status).map(([name, status]) => (
                    <Tag key={name} color={status.status === "complete" ? "success" : status.status === "partial" ? "warning" : "error"}>
                      {name}：{status.status === "complete" ? "完整" : status.status === "partial" ? "部分" : "不可用"}
                      {status.data_date ? ` (${status.data_date})` : ""}
                    </Tag>
                  ))}
                </Space>
              </div>
            ) : null}
              </CollapsibleSection>

              <CollapsibleSection
                id="review-report"
                title={review.llm_review ? "深度复盘报告" : "机会、风险与策略"}
                summary={sectionSummary("review-report")}
                defaultOpen={!review.llm_review}
                open={openSectionId === "review-report" || undefined}
                onOpenChange={(next) => handleSectionToggle("review-report", next)}
              >
            {review.llm_review ? (
              <Card title="复盘报告" style={{ ...cardStyle, background: c.nestedBg }}>
                <div className="daily-review-markdown">
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkBreaks]}
                    components={{
                      table: ({ children }) => (
                        <div className="daily-review-markdown-table-wrap">
                          <table>{children}</table>
                        </div>
                      ),
                    }}
                  >
                    {renderReviewContent(review.llm_review)}
                  </ReactMarkdown>
                </div>
              </Card>
            ) : (
              <>
                {[
                  review.index_review,
                  review.hotspot_review,
                  review.dragon_tiger_review,
                  review.news_policy_review,
                ].filter((section): section is NonNullable<typeof section> => Boolean(section)).map((section) => (
                  <Card key={section.title} title={section.title} style={cardStyle}>
                    <Paragraph>{section.summary}</Paragraph>
                    <ul>
                      {section.bullets.map((item) => <li key={item}>{item}</li>)}
                    </ul>
                  </Card>
                ))}
                <Card title="机会与风险" style={cardStyle}>
                  <div style={{ display: "grid", gap: 10 }}>
                    <div style={{ padding: "var(--c-pad-inset, 7px 12px)", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-up) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-up)" }}>
                      <Text strong style={{ color: "var(--c-up)" }}><RiseOutlined style={{ marginRight: 6 }} />机会：</Text>
                      <Text style={{ marginLeft: 6 }}>{review.opportunities.join("；") || "-"}</Text>
                    </div>
                    <div style={{ padding: "var(--c-pad-inset, 7px 12px)", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-warning) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-warning)" }}>
                      <Text strong style={{ color: "var(--c-warning)" }}><WarningOutlined style={{ marginRight: 6 }} />风险：</Text>
                      <Text style={{ marginLeft: 6 }}>{review.risk_alerts.join("；") || "-"}</Text>
                    </div>
                    <div style={{ padding: "var(--c-pad-inset, 7px 12px)", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-primary) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-primary)" }}>
                      <Text strong style={{ color: "var(--c-primary)" }}><BulbOutlined style={{ marginRight: 6 }} />策略：</Text>
                      <Text style={{ marginLeft: 6 }}>{review.strategy_notes.join("；") || "-"}</Text>
                    </div>
                  </div>
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
              </CollapsibleSection>
            </Space>
          ) : (
            <Card style={cardStyle}><Paragraph type="secondary">请选择日期后生成复盘。</Paragraph></Card>
          )}
        </div>
      </WorkflowWorkspace>
    </div>
  );
}
