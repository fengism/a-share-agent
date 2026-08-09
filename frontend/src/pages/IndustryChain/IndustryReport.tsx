import { lazy, Suspense, useEffect, useState } from "react";
import { ApartmentOutlined, CloudUploadOutlined, FullscreenOutlined, SendOutlined } from "@ant-design/icons";
import { Button, Input, Modal, Popover, Skeleton, Tag, Typography } from "antd";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainChart, IndustryChainResult } from "../../types/stock";
import IndustryResearchSections from "./IndustryResearchSections";
import MarkdownReport from "./MarkdownReport";
import LazyIndustryChart from "./LazyIndustryChart";

const IndustryChart = lazy(() => import("./IndustryChart"));

const { Paragraph, Text } = Typography;

export interface IndustryPushResult {
  url?: string;
  message?: string;
  target?: string;
}

interface IndustryReportProps {
  result: IndustryChainResult;
  activeName: string;
  archiveId: string;
  defaultReceiver?: string;
  isPushing: boolean;
  pushResult: IndustryPushResult | null;
  onPush: (target: "feishu" | "notion", feishuReceiver?: string) => Promise<void>;
}

export default function IndustryReport({
  result,
  activeName,
  archiveId,
  defaultReceiver,
  isPushing,
  pushResult,
  onPush,
}: IndustryReportProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [expandedChart, setExpandedChart] = useState<{ chart: IndustryChainChart; index: number } | null>(null);
  const [feishuReceiver, setFeishuReceiver] = useState(defaultReceiver || "");

  useEffect(() => {
    if (!defaultReceiver) return;
    setFeishuReceiver((current) => current || defaultReceiver);
  }, [defaultReceiver]);

  return (
    <>
      <div style={{ ...cardStyle, padding: "16px 20px", marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", marginBottom: 8, gap: 12 }}>
          <Text strong style={{ color: colors.textPrimary, fontSize: 15, minWidth: 0, overflowWrap: "anywhere" }}>
            <ApartmentOutlined style={{ marginRight: 6 }} />
            {result.name || activeName} 产业链
          </Text>
          <Popover
            trigger="click"
            placement="bottomRight"
            content={(
              <div style={{ width: isNarrow ? "min(280px, 80vw)" : 280 }}>
                <Text style={{ color: colors.textSecondary, fontSize: 12, display: "block", marginBottom: 8 }}>
                  飞书接收人 open_id
                </Text>
                <Input
                  size="small"
                  placeholder={defaultReceiver || "ou_xxx..."}
                  value={feishuReceiver}
                  onChange={(event) => setFeishuReceiver(event.target.value)}
                  disabled={isPushing}
                  id="feishu-receiver-input"
                  style={{ marginBottom: 12 }}
                />
                <Button
                  type="primary"
                  icon={<SendOutlined />}
                  size="small"
                  block
                  loading={isPushing}
                  disabled={!archiveId}
                  onClick={() => onPush("feishu", feishuReceiver.trim())}
                  style={{ marginBottom: 8 }}
                >
                  推送到飞书
                </Button>
                <Button
                  icon={<SendOutlined />}
                  size="small"
                  block
                  loading={isPushing}
                  disabled={!archiveId}
                  onClick={() => onPush("notion")}
                >
                  推送到 Notion
                </Button>
                {!archiveId && (
                  <div style={{ color: colors.textSecondary, fontSize: 12, marginTop: 8 }}>
                    提示：从右侧历史打开的报告可直接推送。
                  </div>
                )}
                {pushResult && (
                  <div style={{ marginTop: 12, padding: 10, background: `${colors.down}1a`, borderRadius: 6 }}>
                    <div style={{ color: colors.down, fontSize: 12, marginBottom: 4 }}>
                      ✓ 已推送到 {pushResult.target === "feishu" ? "飞书" : "Notion"}
                    </div>
                    {pushResult.url && (
                      <a
                        href={pushResult.url}
                        target="_blank"
                        rel="noreferrer"
                        style={{ color: colors.primary, fontSize: 12, wordBreak: "break-all" }}
                      >
                        {pushResult.url}
                      </a>
                    )}
                    {pushResult.message && (
                      <div style={{ color: colors.textSecondary, fontSize: 11, marginTop: 4 }}>{pushResult.message}</div>
                    )}
                  </div>
                )}
              </div>
            )}
          >
            <Button type="primary" icon={<CloudUploadOutlined />} size="small" loading={isPushing} disabled={!archiveId}>
              推送
            </Button>
          </Popover>
        </div>

        {result.summary && (
          <Paragraph style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 12 }}>{result.summary}</Paragraph>
        )}
        {result.aliases && result.aliases.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: result.positioning ? 12 : 0 }}>
            {result.aliases.map((alias) => <Tag key={alias} style={{ margin: 0 }}>{alias}</Tag>)}
          </div>
        )}
        {result.positioning && (
          <div style={{ padding: "10px 12px", borderRadius: 8, borderLeft: `3px solid ${colors.primary}`, background: colors.elevatedBg }}>
            <Text style={{ color: colors.textSecondary, fontSize: 13 }}>{result.positioning}</Text>
          </div>
        )}
      </div>

      <IndustryResearchSections result={result} />

      {result.charts.length > 0 && (
        <div style={{ marginBottom: 16 }}>
          {result.charts.map((chart, index) => {
            const chartHeight = chart.type === "tree"
              ? "clamp(400px, 55vh, 900px)"
              : "clamp(300px, 40vh, 550px)";
            const hasValidOption = Boolean(chart.option && typeof chart.option === "object");
            return (
              <div key={index} style={{ ...cardStyle, padding: "16px 20px", marginBottom: 16 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                  <Text strong style={{ color: colors.textPrimary, fontSize: 14 }}>{chart.title}</Text>
                  {hasValidOption && (
                    <Button
                      type="text"
                      size="small"
                      icon={<FullscreenOutlined />}
                      aria-label={`放大${chart.title}`}
                      onClick={() => setExpandedChart({ chart, index })}
                      style={{ color: colors.textMuted }}
                    />
                  )}
                </div>
                {chart.description && (
                  <Text style={{ color: colors.textSecondary, fontSize: 13, marginBottom: 12, display: "block", lineHeight: 1.6 }}>
                    {chart.description}
                  </Text>
                )}
                {hasValidOption ? (
                  <div style={{ width: "100%", overflow: "auto" }}>
                    <LazyIndustryChart option={chart.option} height={chartHeight} />
                  </div>
                ) : (
                  <div
                    style={{
                      height: chartHeight,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      color: colors.textMuted,
                      fontSize: 13,
                    }}
                  >
                    图表配置不可用
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div style={{ ...cardStyle, padding: "20px 24px" }}>
        <MarkdownReport content={result.llm_review} />
      </div>

      <Modal
        title={expandedChart?.chart.title || ""}
        open={Boolean(expandedChart)}
        onCancel={() => setExpandedChart(null)}
        footer={null}
        width="min(1200px, 92vw)"
        style={{ top: 20 }}
        destroyOnHidden
      >
        {expandedChart && (
          <Suspense
            fallback={(
              <div aria-label="产业链大图加载中" style={{ minHeight: 360, width: "100%" }}>
                <Skeleton.Node active style={{ width: "100%", height: 360 }} />
              </div>
            )}
          >
            <IndustryChart
              option={expandedChart.chart.option}
              height={expandedChart.chart.type === "tree" ? "min(85vh, 1600px)" : "min(70vh, 800px)"}
            />
          </Suspense>
        )}
      </Modal>
    </>
  );
}
