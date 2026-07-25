import { useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Button, Card, DatePicker, Divider, List, Row, Col, Space, Tag, Typography, message } from "antd";
import ReactMarkdown from "react-markdown";
import dayjs from "dayjs";
// html2canvas & jsPDF are loaded lazily inside handleExportPdf (kept out of the initial bundle)
import { useDailyReview, useDailyReviewHistory, useGenerateDailyReview, usePush } from "../../api/queries";
import PushModal from "../../components/PushModal";
import type { PushRequest } from "../../types/stock";
import { useColors, useStyles } from "../../styles/ui";

const { Title, Paragraph, Text } = Typography;

function formatDate(value: dayjs.Dayjs | null) {
  return value ? value.format("YYYY-MM-DD") : dayjs().format("YYYY-MM-DD");
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
  const [selectedDate, setSelectedDate] = useState(dayjs());
  const date = formatDate(selectedDate);
  const exportRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const { data: history = [] } = useDailyReviewHistory();
  const { data: review } = useDailyReview(date);
  const generateMutation = useGenerateDailyReview();
  const pushMutation = usePush();
  const [pushModalOpen, setPushModalOpen] = useState(false);

  const historyItems = useMemo(() => history, [history]);

  const handleGenerate = async (force = false) => {
    try {
      await generateMutation.mutateAsync({ date, force });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["dailyReviewHistory"] }),
        queryClient.invalidateQueries({ queryKey: ["dailyReview", date] }),
      ]);
      message.success(force ? "已重新生成复盘" : "已生成复盘");
    } catch (error) {
      message.error(`生成失败: ${String(error)}`);
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
    if (!exportRef.current) return;
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
  };

  return (
    <div style={pageContainerStyle}>
      <Space direction="vertical" size={16} style={{ width: "100%" }}>
        <Row justify="space-between" align="middle" gutter={[16, 16]}>
          <Col>
            <Title level={3} style={{ margin: 0 }}>每日复盘</Title>
            <Paragraph type="secondary" style={{ margin: 0 }}>按日期生成并保存市场复盘历史</Paragraph>
          </Col>
          <Col>
            <Space>
              <DatePicker value={selectedDate} onChange={(value) => setSelectedDate(value || dayjs())} />
              <Button type="primary" loading={generateMutation.isPending} onClick={() => handleGenerate(false)}>生成复盘</Button>
              <Button loading={generateMutation.isPending} onClick={() => handleGenerate(true)}>重新生成</Button>
              <Button onClick={handleExportPdf} disabled={!review}>导出 PDF</Button>
              <Button onClick={() => setPushModalOpen(true)} disabled={!review}>推送</Button>
              <PushModal
                open={pushModalOpen}
                type="daily_review"
                date={date}
                onConfirm={handlePush}
                onCancel={() => setPushModalOpen(false)}
                loading={pushMutation.isPending}
              />
            </Space>
          </Col>
        </Row>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={7}>
            <Card title="历史复盘" style={cardStyle}>
              <List
                dataSource={historyItems}
                renderItem={(item) => (
                  <List.Item onClick={() => setSelectedDate(dayjs(item.date))} style={{ cursor: "pointer", background: item.date === date ? c.elevatedBg : undefined, borderLeft: item.date === date ? `3px solid ${c.primary}` : undefined, paddingLeft: item.date === date ? 8 : undefined, borderRadius: 4 }}>
                    <List.Item.Meta title={item.title} description={<Text type="secondary">{item.date}</Text>} />
                  </List.Item>
                )}
              />
            </Card>
          </Col>
          <Col xs={24} lg={17}>
            <div ref={exportRef}>
              {review ? (
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
