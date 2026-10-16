import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import {
  ApartmentOutlined,
  BulbOutlined,
  CompassOutlined,
  CopyOutlined,
  DeleteOutlined,
  DownOutlined,
  DownloadOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FireOutlined,
  LineChartOutlined,
  RiseOutlined,
  SearchOutlined,
  SwapRightOutlined,
  ThunderboltOutlined,
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
import { streamDailyReview, type DailyReviewProgress } from "../../api/sse";
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
import "./daily-review.css";

const { Title, Paragraph, Text } = Typography;

const eventTypeLabels = {
  policy: "政策",
  macro: "宏观",
  global: "海外",
  industry: "产业",
  market: "市场",
} as const;

const eventDirectionLabels = {
  positive: "偏利好",
  negative: "偏利空",
  mixed: "影响分化",
  neutral: "方向待确认",
} as const;

const eventHorizonLabels = {
  intraday: "日内",
  short_term: "短期",
  medium_term: "中期",
} as const;

const eventTimingLabels = {
  before: "盘前/事前",
  on_date: "复盘日",
  after: "事后验证",
} as const;

function formatDate(value: dayjs.Dayjs | null) {
  return value?.format("YYYY-MM-DD") ?? "";
}

// 复盘自检/趋势里的涨跌幅：后端给的是百分数（如 3.2 表示 +3.20%）。
function formatSignedPct(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}%`;
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

function stringifyReviewValue(value: unknown, depth = 0): string {
  if (value == null) return "";
  if (typeof value === "string") {
    return value.replace(/\\n/g, "\n").trim();
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") {
          return `- ${item.replace(/\\n/g, "\n").trim()}`;
        }
        return `- ${stringifyReviewValue(item, depth + 1)}`;
      })
      .join("\n");
  }
  if (typeof value === "object") {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, item]) => {
        if (typeof item === "string") {
          const itemText = item.replace(/\\n/g, "\n").trim();
          if (itemText.includes("\n")) {
            const lines = itemText.split("\n").map((line) => line.trim()).filter(Boolean);
            return `- **${key}**：\n${lines.map((line) => `  - ${line}`).join("\n")}`;
          }
          return `- **${key}**：${itemText}`;
        }
        return `- **${key}**：\n${stringifyReviewValue(item, depth + 1)}`;
      })
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
  if (!value) return "";
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
    return text.replace(/\\n/g, "\n");
  }
}

function buildDailyReviewMarkdown(review: NonNullable<ReturnType<typeof useDailyReview>["data"]>): string {
  const parts: string[] = [];
  parts.push(`# ${review.title}`);
  parts.push(`> **复盘日期**：${review.date} | **生成时间**：${review.generated_at || "-"} | **质量状态**：${review.quality_status === "degraded" ? "降级" : "完整"}\n`);
  parts.push(`## 市场总览\n\n${review.market_summary}\n`);
  parts.push(`## 市场情绪结论\n\n${buildMoodSummary(review)}\n`);

  if (review.llm_review) {
    parts.push(`## 深度复盘报告\n\n${renderReviewContent(review.llm_review)}\n`);
  } else {
    for (const section of [
      review.index_review,
      review.hotspot_review,
      review.dragon_tiger_review,
      review.news_policy_review,
    ]) {
      if (section?.title) {
        parts.push(`## ${section.title}\n\n${section.summary || ""}\n`);
        if (section.bullets?.length) {
          parts.push(section.bullets.map((b) => `- ${b}`).join("\n"));
        }
        parts.push("\n");
      }
    }
  }

  if (review.opportunities?.length || review.risk_alerts?.length || review.strategy_notes?.length) {
    parts.push("## 机会与风险展望\n");
    if (review.opportunities?.length) {
      parts.push(`- **机会**：${review.opportunities.join("；")}`);
    }
    if (review.risk_alerts?.length) {
      parts.push(`- **风险**：${review.risk_alerts.join("；")}`);
    }
    if (review.strategy_notes?.length) {
      parts.push(`- **策略建议**：${review.strategy_notes.join("；")}`);
    }
    parts.push("");
  }

  if (review.sentiment_cycle) {
    parts.push(`## 情绪周期定位：${review.sentiment_cycle.stage}\n`);
    if (review.sentiment_cycle.ladder_health) {
      parts.push(`- 梯队健康度：${review.sentiment_cycle.ladder_health}`);
    }
    for (const item of review.sentiment_cycle.evidence ?? []) {
      parts.push(`- 依据：${item}`);
    }
    parts.push("");
  }

  if (review.scenario_plans?.length) {
    parts.push("## 明日三情景预案\n");
    for (const scenario of review.scenario_plans) {
      parts.push(`- **${scenario.name}**：触发 ${scenario.trigger || "待补充"}；应对 ${scenario.playbook || "待补充"}`);
      if (scenario.watch_levels?.length) {
        parts.push(`  - 观察信号：${scenario.watch_levels.join("；")}`);
      }
    }
    parts.push("");
  }

  if (review.next_day_watchlist?.length) {
    parts.push("## 次日观察锚点\n");
    parts.push(
      review.next_day_watchlist
        .map((item) => `- **${item.name}**（${item.role}）：${item.reason || "待补充"}；触发 ${item.trigger || "待补充"}`)
        .join("\n"),
    );
    parts.push("");
  }

  if (review.key_levels?.length) {
    parts.push("## 关键点位与量能阈值\n");
    parts.push(review.key_levels.map((item) => `- ${item}`).join("\n"));
    parts.push("");
  }

  const check = review.previous_review_check;
  if (check) {
    parts.push(`## 上一交易日复盘自检（${check.review_date} → ${check.verified_date}）\n`);
    if (check.previous_stage) {
      parts.push(`- 上一交易日周期定位：${check.previous_stage}`);
    }
    if (check.previous_limit_up_count != null && check.limit_up_count != null) {
      parts.push(`- 涨停家数：${check.previous_limit_up_count} → ${check.limit_up_count}`);
    }
    for (const index of check.indices ?? []) {
      if (index.change_pct == null && index.previous_change_pct == null) {
        continue;
      }
      parts.push(`- ${index.name}：${formatSignedPct(index.previous_change_pct)} → ${formatSignedPct(index.change_pct)}`);
    }
    for (const item of check.watchlist ?? []) {
      if (item.missing) {
        parts.push(`- ${item.name}：次日行情缺失`);
        continue;
      }
      const limitUp = item.limit_up ? "，次日涨停" : "";
      parts.push(`- ${item.name}：次日 ${formatSignedPct(item.change_pct)}${limitUp}（${item.hit ? "命中" : "落空"}）`);
    }
    if (check.checked_count) {
      parts.push(`- 观察标的命中率：${check.hit_count}/${check.checked_count}`);
    }
    if (check.note) {
      parts.push(`- 说明：${check.note}`);
    }
    parts.push("");
  }

  const trend = review.cycle_trend;
  if (trend?.points?.length) {
    parts.push("## 情绪周期历史趋势\n");
    for (const point of trend.points.slice(-10)) {
      const bits = [point.date, point.stage || "未定位"];
      if (point.limit_up_count != null) {
        bits.push(`涨停 ${point.limit_up_count} 家`);
      }
      if (point.break_rate != null) {
        bits.push(`炸板率 ${(point.break_rate * 100).toFixed(1)}%`);
      }
      if (point.index_change_pct != null) {
        bits.push(`指数 ${formatSignedPct(point.index_change_pct)}`);
      }
      if (point.next_index_change_pct != null) {
        bits.push(`次日指数 ${formatSignedPct(point.next_index_change_pct)}`);
      }
      if (point.stage_transition) {
        bits.push(point.stage_transition);
      }
      parts.push(`- ${bits.join("；")}`);
    }
    for (const stat of trend.stage_stats ?? []) {
      parts.push(`- 阶段统计：${stat.stage} 出现 ${stat.occurrences} 次`);
    }
    if (trend.note) {
      parts.push(`- 说明：${trend.note}`);
    }
    parts.push("");
  }

  const sourceStatus = review.data_snapshot?.source_status;
  if (sourceStatus && Object.keys(sourceStatus).length) {
    parts.push("## 复盘数据状态\n");
    parts.push(
      Object.entries(sourceStatus)
        .map(([name, status]) => {
          const label = status.status === "complete" ? "完整" : status.status === "partial" ? "部分" : "不可用";
          const dataDate = status.data_date ? `（数据日期 ${status.data_date}）` : "";
          const error = status.error ? ` — ${status.error}` : "";
          return `- ${name}：${label}${dataDate}${error}`;
        })
        .join("\n"),
    );
    parts.push("");
  }

  if (review.warnings?.length) {
    parts.push("## 数据核验警告\n");
    parts.push(review.warnings.map((warning) => `- ⚠️ ${warning}`).join("\n"));
    parts.push("");
  }

  if (review.notes?.length) {
    parts.push("## 数据说明\n");
    parts.push(review.notes.map((note) => `- ${note}`).join("\n"));
    parts.push("");
  }

  return parts.join("\n");
}

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
  const { push, isPushing } = useWorkflowPush();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const [generationMessage, setGenerationMessage] = useState("");
  const [historyFilter, setHistoryFilter] = useState("");
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
            <Space.Compact>
              <Button
                disabled={isGenerating || isExportingPdf}
                onClick={() => setDate(dayjs().format("YYYY-MM-DD"))}
              >
                今日
              </Button>
              <Button
                disabled={isGenerating || isExportingPdf}
                onClick={() => setDate(dayjs().subtract(1, "day").format("YYYY-MM-DD"))}
              >
                前一日
              </Button>
            </Space.Compact>
            <Button type="primary" loading={isGenerating} disabled={isExportingPdf} onClick={() => handleGenerate(false)}>生成复盘</Button>
            <Button loading={isGenerating} disabled={isExportingPdf} onClick={() => handleGenerate(true)}>重新生成</Button>
            {isGenerating && <Button danger onClick={handleCancelGeneration}>取消任务</Button>}
            <Dropdown
              trigger={["click"]}
              menu={{
                items: [
                  {
                    key: "pdf",
                    label: "导出为 PDF (.pdf)",
                    icon: <FilePdfOutlined />,
                    disabled: isExportingPdf,
                  },
                  {
                    key: "md",
                    label: "导出为 Markdown (.md)",
                    icon: <FileMarkdownOutlined />,
                  },
                ],
                onClick: ({ key }) => {
                  if (key === "pdf") {
                    void handleExportPdf();
                  } else if (key === "md") {
                    handleExportMarkdown();
                  }
                },
              }}
              disabled={!review || isGenerating}
            >
              <Button
                icon={<DownloadOutlined />}
                loading={isExportingPdf}
                aria-label="导出"
              >
                导出 <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} />
              </Button>
            </Dropdown>
            <Button icon={<CopyOutlined />} onClick={handleCopyMarkdown} disabled={!review || isGenerating}>复制</Button>
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
              <Card style={{ ...cardStyle, borderLeft: `4px solid ${c.primary}`, background: `linear-gradient(135deg, color-mix(in srgb, ${c.primary} 6%, ${c.cardBg}), ${c.cardBg})` }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
                  <Title level={4} style={{ marginTop: 0, marginBottom: 8 }}>{review.title}</Title>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    <Tag color={review.quality_status === "degraded" ? "warning" : "success"}>质量：{review.quality_status === "degraded" ? "降级" : "完整"}</Tag>
                    <Tag color={review.generation_status === "fallback" ? "warning" : "processing"}>报告：{review.generation_status === "fallback" ? "确定性兜底" : "AI 生成"}</Tag>
                  </div>
                </div>
                <Paragraph style={{ fontSize: "var(--c-font-base)", lineHeight: "var(--c-leading-relaxed)", color: "var(--c-text-primary)" }}>{review.market_summary}</Paragraph>
                <div style={{ margin: "12px 0", padding: "10px 14px", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-primary) 8%, var(--c-card-bg))", border: "1px solid color-mix(in srgb, var(--c-primary) 18%, var(--c-border))" }}>
                  <Text strong style={{ color: "var(--c-primary)" }}>
                    <CompassOutlined style={{ marginRight: 6 }} />
                    市场情绪结论：
                  </Text>
                  <Text style={{ marginLeft: 6 }}>{buildMoodSummary(review)}</Text>
                </div>
                <Space wrap style={{ marginTop: 8 }}>
                  <Tag className="financial-num" style={{ background: `${c.primary}26`, color: c.primary, border: "none", borderRadius: "var(--c-radius-pill)", padding: "2px 10px" }}><LineChartOutlined style={{ marginRight: 4 }} />指数 {review.data_snapshot.indices.length}</Tag>
                  <Tag className="financial-num" style={{ background: `${c.accent}26`, color: c.accent, border: "none", borderRadius: "var(--c-radius-pill)", padding: "2px 10px" }}><FireOutlined style={{ marginRight: 4 }} />热股 {review.data_snapshot.hot_stocks.length}</Tag>
                  <Tag className="financial-num" style={{ background: `${c.accent}26`, color: c.accent, border: "none", borderRadius: "var(--c-radius-pill)", padding: "2px 10px" }}><ThunderboltOutlined style={{ marginRight: 4 }} />概念 {review.data_snapshot.hot_concepts.length}</Tag>
                  <Tag className="financial-num" style={{ background: `${c.down}26`, color: c.down, border: "none", borderRadius: "var(--c-radius-pill)", padding: "2px 10px" }}><ApartmentOutlined style={{ marginRight: 4 }} />行业 {review.data_snapshot.hot_industries.length}</Tag>
                  <Tag className="financial-num" style={{ background: `${c.up}26`, color: c.up, border: "none", borderRadius: "var(--c-radius-pill)", padding: "2px 10px" }}><SwapRightOutlined style={{ marginRight: 4 }} />龙虎榜 {review.data_snapshot.dragon_tiger.length}</Tag>
                </Space>
                <div style={{ marginTop: 12 }}>
                  <Text type="secondary" style={{ fontSize: "var(--c-font-xs)" }}>生成时间：{review.generated_at}</Text>
                </div>
              </Card>
              <Card title="市场数据图谱" style={cardStyle}>
                <DailyReviewCharts snapshot={review.data_snapshot} />
              </Card>
              {review.news_policy_review || review.event_impacts?.length ? (
                <Card title="新闻政策与影响传导" style={cardStyle}>
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
                </Card>
              ) : null}
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
              {review.sentiment_cycle ? (
                <Card title="情绪周期定位" style={cardStyle}>
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
                </Card>
              ) : null}

              {review.scenario_plans?.length ? (
                <Card title="明日三情景预案" style={cardStyle}>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 10 }}>
                    {review.scenario_plans.map((scenario) => (
                      <div key={scenario.name} style={{ padding: "10px 12px", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                        <Text strong>{scenario.name}</Text>
                        <Paragraph style={{ margin: "6px 0 0" }}><Text strong>触发：</Text>{scenario.trigger || "待补充"}</Paragraph>
                        <Paragraph style={{ margin: "4px 0 0" }}><Text strong>应对：</Text>{scenario.playbook || "待补充"}</Paragraph>
                        {scenario.watch_levels?.length ? (
                          <Paragraph type="secondary" style={{ margin: "4px 0 0" }}>观察信号：{scenario.watch_levels.join("；")}</Paragraph>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </Card>
              ) : null}

              {review.next_day_watchlist?.length ? (
                <Card title="次日观察锚点" style={cardStyle}>
                  <Space direction="vertical" style={{ width: "100%" }} size={8}>
                    {review.next_day_watchlist.map((item) => (
                      <div key={`${item.name}-${item.role}`} style={{ padding: "8px 12px", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                        <Space wrap>
                          <Text strong>{item.name}</Text>
                          <Tag color="blue">{item.role}</Tag>
                        </Space>
                        <Paragraph style={{ margin: "6px 0 0" }}>{item.reason || "待补充"}</Paragraph>
                        <Paragraph type="secondary" style={{ margin: "4px 0 0" }}>触发：{item.trigger || "待补充"}</Paragraph>
                      </div>
                    ))}
                  </Space>
                </Card>
              ) : null}

              {review.key_levels?.length ? (
                <Card title="关键点位与量能阈值" style={cardStyle}>
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {review.key_levels.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </Card>
              ) : null}

              {review.previous_review_check ? (
                <Card title="上一交易日复盘自检" style={cardStyle}>
                  <Space wrap style={{ marginBottom: 10 }}>
                    <Text type="secondary">
                      {review.previous_review_check.review_date} 复盘 → {review.previous_review_check.verified_date} 实际表现
                    </Text>
                    {review.previous_review_check.previous_stage ? (
                      <Tag color="purple">昨日周期：{review.previous_review_check.previous_stage}</Tag>
                    ) : null}
                    {review.previous_review_check.checked_count ? (
                      <Tag color="blue">
                        命中 {review.previous_review_check.hit_count}/{review.previous_review_check.checked_count}
                      </Tag>
                    ) : (
                      <Tag>暂无可核验行情</Tag>
                    )}
                    {review.previous_review_check.limit_up_delta != null ? (
                      <Tag color={review.previous_review_check.limit_up_delta >= 0 ? "red" : "green"}>
                        涨停家数 {review.previous_review_check.previous_limit_up_count} →{' '}
                        {review.previous_review_check.limit_up_count}
                      </Tag>
                    ) : null}
                  </Space>
                  <Space direction="vertical" size={8} style={{ width: "100%" }}>
                    {(review.previous_review_check.watchlist ?? []).map((item) => (
                      <div key={`${item.name}-${item.code ?? ""}`} style={{ padding: "8px 12px", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                        <Space wrap>
                          <Text strong>{item.name}</Text>
                          {item.code ? <Text type="secondary">{item.code}</Text> : null}
                          {item.missing ? (
                            <Tag>次日行情缺失</Tag>
                          ) : (
                            <Tag color={item.hit ? "red" : "green"}>{formatSignedPct(item.change_pct)}</Tag>
                          )}
                          {item.limit_up ? <Tag color="volcano">涨停</Tag> : null}
                        </Space>
                      </div>
                    ))}
                    {(review.previous_review_check.indices ?? []).map((item) => (
                      <Text key={`${item.name}-${item.code ?? ""}`} type="secondary">
                        {item.name}：{formatSignedPct(item.previous_change_pct)} → {formatSignedPct(item.change_pct)}
                      </Text>
                    ))}
                  </Space>
                  {review.previous_review_check.note ? (
                    <Paragraph type="secondary" style={{ margin: "10px 0 0" }}>{review.previous_review_check.note}</Paragraph>
                  ) : null}
                </Card>
              ) : null}

              {review.cycle_trend?.points?.length ? (
                <Card title="情绪周期历史趋势" style={cardStyle}>
                  {review.cycle_trend.note ? (
                    <Paragraph type="secondary" style={{ marginTop: 0 }}>{review.cycle_trend.note}</Paragraph>
                  ) : null}
                  <Space wrap>
                    {(review.cycle_trend.points ?? []).slice(-10).map((point) => (
                      <div key={point.date} style={{ padding: "8px 12px", borderRadius: "var(--c-radius-md)", background: c.nestedBg }}>
                        <Space size={4} wrap>
                          <Text strong>{point.stage || "未定位"}</Text>
                          <Text type="secondary">{point.date.slice(5)}</Text>
                          {point.stage_transition ? (
                            <Tag color={point.stage_transition === "升级" ? "red" : point.stage_transition === "降级" ? "green" : "default"}>
                              {point.stage_transition}
                            </Tag>
                          ) : null}
                        </Space>
                        <div>
                          <Text type="secondary">
                            涨停 {point.limit_up_count ?? "-"} 家
                            {point.break_rate != null ? ` ｜ 炸板率 ${(point.break_rate * 100).toFixed(1)}%` : ""}
                            {point.index_change_pct != null ? ` ｜ 指数 ${formatSignedPct(point.index_change_pct)}` : ""}
                            {point.next_index_change_pct != null ? ` ｜ 次日 ${formatSignedPct(point.next_index_change_pct)}` : ""}
                          </Text>
                        </div>
                      </div>
                    ))}
                  </Space>
                  {review.cycle_trend.stage_stats?.length ? (
                    <div style={{ marginTop: 10, display: "grid", gap: 6 }}>
                      {review.cycle_trend.stage_stats.map((stat) => (
                        <Text key={stat.stage} type="secondary">
                          {stat.stage}：出现 {stat.occurrences} 次
                          {stat.next_day_up_ratio != null ? `，次日指数上涨比例 ${(stat.next_day_up_ratio * 100).toFixed(0)}%` : ""}
                          {stat.avg_next_day_index_change_pct != null ? `，平均次日 ${formatSignedPct(stat.avg_next_day_index_change_pct)}` : ""}
                        </Text>
                      ))}
                    </div>
                  ) : null}
                </Card>
              ) : null}

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
                      <div style={{ padding: "10px 14px", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-up) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-up)" }}>
                        <Text strong style={{ color: "var(--c-up)" }}><RiseOutlined style={{ marginRight: 6 }} />机会：</Text>
                        <Text style={{ marginLeft: 6 }}>{review.opportunities.join("；") || "-"}</Text>
                      </div>
                      <div style={{ padding: "10px 14px", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-warning) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-warning)" }}>
                        <Text strong style={{ color: "var(--c-warning)" }}><WarningOutlined style={{ marginRight: 6 }} />风险：</Text>
                        <Text style={{ marginLeft: 6 }}>{review.risk_alerts.join("；") || "-"}</Text>
                      </div>
                      <div style={{ padding: "10px 14px", borderRadius: "var(--c-radius-md)", background: "color-mix(in srgb, var(--c-primary) 8%, var(--c-card-bg))", borderLeft: "3px solid var(--c-primary)" }}>
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
            </Space>
          ) : (
            <Card style={cardStyle}><Paragraph type="secondary">请选择日期后生成复盘。</Paragraph></Card>
          )}
        </div>
      </WorkflowWorkspace>
    </div>
  );
}
