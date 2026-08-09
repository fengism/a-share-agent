import { useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { DeleteOutlined } from "@ant-design/icons";
import { Button, Card, DatePicker, Divider, List, Row, Col, message, Popconfirm, Skeleton, Space, Tag, Typography } from "antd";
import ReactMarkdown from "react-markdown";
import dayjs from "dayjs";
// html2canvas & jsPDF are loaded lazily inside handleExportPdf (kept out of the initial bundle)
import { useDailyReview, useDeleteDailyReview, useGenerateDailyReview, useInfiniteDailyReviewHistory, usePush } from "../../api/queries";
import { ApiError } from "../../api/client";
import PushModal from "../../components/PushModal";
import QueryErrorState from "../../components/QueryErrorState";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import type { PushRequest } from "../../types/stock";
import { useColors, useStyles } from "../../styles/ui";

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
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [selectedDate, setSelectedDate] = useState<dayjs.Dayjs | null>(dayjs());
  const date = formatDate(selectedDate);
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
  const generateMutation = useGenerateDailyReview();
  const deleteMutation = useDeleteDailyReview();
  const pushMutation = usePush();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const historyItems = historyPages?.pages.flat() ?? [];

  const handleGenerate = async (force = false) => {
    if (!date) {
      message.warning("请先选择复盘日期");
      return;
    }
    try {
      await generateMutation.mutateAsync({ date, force });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReviewHistoryRoot }),
        queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReview(date) }),
      ]);
      message.success(force ? "已重新生成复盘" : "已生成复盘");
    } catch (error) {
      message.error(`生成失败: ${String(error)}`);
    }
  };

  const handleDelete = async (deleteDate: string) => {
    try {
      await deleteMutation.mutateAsync(deleteDate);
      queryClient.removeQueries({ queryKey: queryKeys.workflows.dailyReview(deleteDate), exact: true });
      if (deleteDate === date) {
        const nextItem = historyItems.find((item) => item.date !== deleteDate);
        setSelectedDate(nextItem ? dayjs(nextItem.date) : null);
      }
      await queryClient.invalidateQueries({ queryKey: queryKeys.workflows.dailyReviewHistoryRoot });
      message.success("复盘记录已删除");
    } catch (deleteError) {
      message.error(deleteError instanceof Error ? deleteError.message : "删除复盘记录失败");
    }
  };

  const handlePush = async (req: PushRequest) => {
    try {
      const result = await pushMutation.mutateAsync(req);
      if (result.target === "notion") {
        message.success(
          <span>
            已转存 Notion：<a href={result.url} target="_blank" rel="noreferrer">{result.title}</a>
          </span>
        );
      } else {
        message.success(`已推送到飞书：${result.message || result.title}`);
      }
    } catch (error) {
      message.error(`推送失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setPushModalOpen(false);
    }
  };

  const handleExportPdf = async () => {
    if (!exportRef.current || !review || isExportingPdf) return;
    setIsExportingPdf(true);
    message.loading({ content: "正在生成 PDF...", key: "daily-review-export" });
    try {
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(exportRef.current, { scale: 2, useCORS: true, backgroundColor: c.pageBg });
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = 210;
      const pageHeight = 297;
      const imgWidth = pageWidth;
      const imgHeight = (canvas.height * imgWidth) / canvas.width;
      let heightLeft = imgHeight;
      let position = 0;
      const imgData = canvas.toDataURL("image/png");

      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;
      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
        heightLeft -= pageHeight;
      }
      pdf.save(`每日复盘-${date}.pdf`);
      message.success({ content: "PDF 导出成功", key: "daily-review-export" });
    } catch (error) {
      console.error("[DailyReview] PDF 导出失败", error);
      message.error({ content: "PDF 导出失败，请稍后重试", key: "daily-review-export" });
    } finally {
      setIsExportingPdf(false);
    }
  };

  return (
    <div style={pageContainerStyle}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col>
            <Title level={3} style={{ margin: 0 }}>每日复盘</Title>
            <Paragraph type="secondary" style={{ margin: 0 }}>按日期生成并保存市场复盘历史</Paragraph>
          </Col>
          <Col style={{ width: isNarrow ? "100%" : undefined }}>
            <div
              style={{
                display: "grid",
                gridTemplateColumns: isNarrow ? "repeat(2, minmax(0, 1fr))" : "repeat(5, max-content)",
                gap: 8,
                justifyContent: isNarrow ? "stretch" : "end",
              }}
            >
              <DatePicker
                value={selectedDate}
                disabled={generateMutation.isPending || isExportingPdf}
                onChange={setSelectedDate}
                style={{ width: "100%", gridColumn: isNarrow ? "1 / -1" : undefined }}
              />
              <Button block={isNarrow} type="primary" loading={generateMutation.isPending} disabled={isExportingPdf} onClick={() => handleGenerate(false)}>生成复盘</Button>
              <Button block={isNarrow} loading={generateMutation.isPending} disabled={isExportingPdf} onClick={() => handleGenerate(true)}>重新生成</Button>
              <Button block={isNarrow} loading={isExportingPdf} onClick={handleExportPdf} disabled={!review || generateMutation.isPending}>导出 PDF</Button>
              <Button block={isNarrow} onClick={() => setPushModalOpen(true)} disabled={!review || generateMutation.isPending || isExportingPdf}>推送</Button>
              <PushModal
                open={pushModalOpen}
                type="daily_review"
                date={date}
                onConfirm={handlePush}
                onCancel={() => setPushModalOpen(false)}
                loading={pushMutation.isPending}
              />
            </div>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={7}>
            <Card title="历史复盘" style={cardStyle}>
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
                <List
                  dataSource={historyItems}
                  footer={hasNextPage ? (
                    <Button block loading={isFetchingNextPage} onClick={() => fetchNextPage()}>
                      加载更多
                    </Button>
                  ) : null}
                  renderItem={(item) => (
                    <List.Item style={{ display: "flex", alignItems: "center", gap: 4, padding: 0 }}>
                      <button
                        type="button"
                        onClick={() => setSelectedDate(dayjs(item.date))}
                        aria-pressed={item.date === date}
                        style={{
                          flex: 1,
                          minWidth: 0,
                          textAlign: "left",
                          padding: "12px 8px",
                          cursor: "pointer",
                          background: item.date === date ? c.elevatedBg : "transparent",
                          border: 0,
                          borderLeft: item.date === date ? `3px solid ${c.primary}` : "3px solid transparent",
                          borderRadius: 4,
                        }}
                      >
                        <List.Item.Meta title={item.title} description={<Text type="secondary">{item.date}</Text>} />
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
                    </List.Item>
                  )}
                />
              </SectionDataState>
            </Card>
          </Col>
          <Col xs={24} lg={17}>
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
                <Space direction="vertical" size={16} style={{ width: "100%" }}>
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
                  </Card>
                  {review.llm_review ? (
                    <Card title="AI 复盘报告" style={{ ...cardStyle, background: c.nestedBg }}>
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
          </Col>
        </Row>
      </Space>
    </div>
  );
}
