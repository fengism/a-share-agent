import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  ApartmentOutlined,
  CloudUploadOutlined,
  CopyOutlined,
  DatabaseOutlined,
  DownOutlined,
  DownloadOutlined,
  FileMarkdownOutlined,
  FilePdfOutlined,
  FileTextOutlined,
  FullscreenOutlined,
  SendOutlined,
} from "@ant-design/icons";
import { Alert, Button, Collapse, Dropdown, Input, message, Modal, Popover, Skeleton, Tag, Typography } from "antd";
import { useQueryClient } from "@tanstack/react-query";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { queryKeys } from "../../api/queryKeys";
import { downloadIndustryChainPdfFromData, useMineIndustryChainAtlas } from "../../api/queryHooks/workflows";
import { useColors, useStyles } from "../../styles/ui";
import type { IndustryChainChart, IndustryChainResult } from "../../types/stock";
import { reportPresentation } from "./reportPresentation";
import { buildIndustryReportMarkdown } from "./industryReportMarkdown";
import IndustryConclusion from "./IndustryConclusion";
import IndustryReportChanges from "./IndustryReportChanges";
import IndustryOpportunityMap from "./IndustryOpportunityMap";
import IndustryEvidenceChecks from "./IndustryEvidenceChecks";
import IndustryResearchTheses from "./IndustryResearchTheses";
import IndustryDecisionResearch from "./IndustryDecisionResearch";
import IndustryResearchSections, { IndustryResearchAudit } from "./IndustryResearchSections";
import MarkdownReport from "./MarkdownReport";
import LazyIndustryChart from "./LazyIndustryChart";
import "./industry-report.css";

const IndustryChart = lazy(() => import("./IndustryChart"));

const { Text } = Typography;

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

function MineToAtlasButton({ name, archiveId }: { name: string; archiveId: string }) {
  const queryClient = useQueryClient();
  const mineMutation = useMineIndustryChainAtlas();
  return (
    <Button
      icon={<DatabaseOutlined />}
      size="small"
      loading={mineMutation.isPending}
      disabled={!archiveId}
      onClick={() => {
        mineMutation.mutate(
          { name, archive_id: archiveId },
          {
            onSuccess: async (chain) => {
              message.success(`已沉淀到知识库：${chain.name}`);
              await queryClient.invalidateQueries({
                queryKey: queryKeys.workflows.industryChainAtlasCatalog,
              });
            },
            onError: (error: Error) => message.error(error.message),
          },
        );
      }}
    >
      沉淀到知识库
    </Button>
  );
}

export default function IndustryReport({
  result: rawResult,
  activeName,
  archiveId,
  defaultReceiver,
  isPushing,
  pushResult,
  onPush,
}: IndustryReportProps) {
  const result = useMemo(() => reportPresentation(rawResult), [rawResult]);
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [expandedChart, setExpandedChart] = useState<{ chart: IndustryChainChart; index: number } | null>(null);
  const [feishuReceiver, setFeishuReceiver] = useState(defaultReceiver || "");
  const [isExportingPdf, setIsExportingPdf] = useState(false);

  const handleExportPdf = async () => {
    try {
      setIsExportingPdf(true);
      message.loading({ content: "正在生成产业链 PDF 研报...", key: "export-industry-pdf" });
      await downloadIndustryChainPdfFromData(rawResult);
      message.success({ content: "产业链 PDF 研报导出成功", key: "export-industry-pdf" });
    } catch (err: unknown) {
      const detail = err instanceof Error ? `: ${err.message}` : "";
      message.error({ content: `PDF 导出失败${detail}`, key: "export-industry-pdf" });
    } finally {
      setIsExportingPdf(false);
    }
  };

  const handleExportMarkdown = () => {
    const content = buildIndustryReportMarkdown(rawResult, activeName);
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const downloadName = (rawResult.name || activeName || "产业链").replace(/[/\\?%*:|"<>]/g, "_");
      a.download = `产业链投研报告_${downloadName}_${new Date().toISOString().slice(0, 10)}.md`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
    message.success("Markdown 研报已导出");
  };

  const handleCopyMarkdown = async () => {
    const content = buildIndustryReportMarkdown(rawResult, activeName);
    try {
      await navigator.clipboard.writeText(content);
      message.success("产业链研报已复制到剪贴板");
    } catch {
      message.error("复制失败，请手动选择");
    }
  };
  const scope = result.research_scope;
  const topicResolution = result.topic_resolution;
  const reportName = topicResolution?.normalized_name || result.name || activeName;
  const possibleTopics = topicResolution?.possible_topics ?? [];
  const scopeSummary = scope && Object.keys(scope).length > 0
    ? [
      { china: "中国", global: "全球", china_and_global: "中国与全球" }[scope.region] || scope.region,
      scope.start_date && scope.end_date ? `${scope.start_date} 至 ${scope.end_date}` : "",
      scope.company_scope === "a_share" ? "A 股公司" : scope.company_scope === "all_public" ? "全部公开公司" : "",
    ].filter(Boolean).join(" · ")
    : "";
  const hasChain = result.upstream.length > 0 || result.midstream.length > 0 || result.downstream.length > 0;
  const driverInsights = result.driver_insights ?? [];
  const riskInsights = result.risk_insights ?? [];
  const detailModuleCount = [
    Boolean(result.market_metrics?.length),
    Boolean(result.competition?.length),
    hasChain,
    Boolean(result.technology_routes?.length),
    Boolean(result.trends?.length),
    Boolean(result.capital_moves?.length),
    Boolean(driverInsights.length || result.drivers.length),
    Boolean(riskInsights.length || result.risks.length),
    Boolean(result.key_events?.length),
    Boolean(result.key_stocks.length),
    ...result.charts.map(() => true),
  ].filter(Boolean).length;
  const judgmentItemCount = 1
    + Math.min(result.market_metrics?.length ?? 0, 3)
    + Math.min(driverInsights.length || result.drivers.length, 3)
    + Math.min(riskInsights.length || result.risks.length, 3)
    + Math.min(result.key_stocks.length, 4);
  const auditItemCount = Object.keys(result.coverage ?? {}).length
    + (result.missing_evidence?.length ?? 0)
    + (result.conflicts?.length ?? 0)
    + (result.sources?.length ?? 0)
    + (result.evidence_catalog?.length ?? 0);

  useEffect(() => {
    if (!defaultReceiver) return;
    setFeishuReceiver((current) => current || defaultReceiver);
  }, [defaultReceiver]);

  return (
    <>
      <div className="industry-report__header">
        <div className="industry-report__title-row">
          <Text className="industry-report__title" strong style={{ color: colors.textPrimary, fontSize: "var(--c-font-lg)" }}>
            <ApartmentOutlined style={{ marginRight: 6 }} />
            {reportName} 产业链
          </Text>
          <div className="industry-report__actions">
            <Popover
              trigger="click"
              placement="bottomRight"
              content={(
                <div style={{ width: isNarrow ? "min(280px, 80vw)" : 280 }}>
                  <Text style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)", display: "block", marginBottom: 8 }}>
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
                    <div style={{ color: colors.textSecondary, fontSize: "var(--c-font-sm)", marginTop: 8 }}>
                      提示：从右侧历史打开的报告可直接推送。
                    </div>
                  )}
                  {pushResult && (
                    <div style={{ marginTop: 12, padding: 10, background: `${colors.down}1a`, borderRadius: 6 }}>
                      <div style={{ color: colors.down, fontSize: "var(--c-font-sm)", marginBottom: 4 }}>
                        ✓ 已推送到 {pushResult.target === "feishu" ? "飞书" : "Notion"}
                      </div>
                      {pushResult.url && (
                        <a
                          href={pushResult.url}
                          target="_blank"
                          rel="noreferrer"
                          style={{ color: colors.primary, fontSize: "var(--c-font-sm)", wordBreak: "break-all" }}
                        >
                          {pushResult.url}
                        </a>
                      )}
                      {pushResult.message && (
                        <div style={{ color: colors.textSecondary, fontSize: "var(--c-font-xs)", marginTop: 4 }}>{pushResult.message}</div>
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
            >
              <Button
                icon={<DownloadOutlined />}
                size="small"
                loading={isExportingPdf}
                aria-label="导出"
              >
                导出 <DownOutlined style={{ fontSize: 10, marginLeft: 2 }} />
              </Button>
            </Dropdown>
            <Button
              icon={<CopyOutlined />}
              size="small"
              onClick={handleCopyMarkdown}
              aria-label="复制研报"
            >
              复制
            </Button>
            <MineToAtlasButton name={activeName} archiveId={archiveId} />
          </div>
        </div>

        <div className="industry-report__meta">
          {result.aliases && result.aliases.length > 0 && (
            <div className="industry-report__aliases" style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {result.aliases.map((alias) => <Tag key={alias} className="industry-report__wrap-tag" style={{ margin: 0 }}>{alias}</Tag>)}
            </div>
          )}
          {scopeSummary && <Text className="industry-report__scope-summary" type="secondary">研究范围：{scopeSummary}</Text>}
        </div>
      </div>

      {(topicResolution?.boundary_note || possibleTopics.length > 1) && (
        <Alert
          type={possibleTopics.length > 1 ? "warning" : "info"}
          showIcon
          className="industry-report__topic-resolution"
          title={possibleTopics.length > 1 ? "研究主题存在多种口径" : "本次研究口径"}
          description={(
            <div>
              {topicResolution?.boundary_note && <p>{topicResolution.boundary_note}</p>}
              {possibleTopics.length > 1 && (
                <div className="industry-report__topic-options">
                  <span>候选主题：</span>
                  {possibleTopics.map((topic) => <Tag key={topic}>{topic}</Tag>)}
                </div>
              )}
            </div>
          )}
        />
      )}

      {(result.quality_status === "degraded" || result.archive_status === "failed" || Boolean(result.warnings?.length)) && (
        <Alert
          className="industry-report__alert"
          type={result.archive_status === "failed" ? "error" : "warning"}
          showIcon
          title={result.archive_status === "failed" ? "报告未保存" : "报告存在质量提示"}
          description={result.warnings?.length ? (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {result.warnings.map((warning) => <li className="industry-report__warning" key={warning}>{warning}</li>)}
            </ul>
          ) : "部分结构化内容未能完整生成，请结合原始来源谨慎使用。"}
          style={{ marginBottom: 16 }}
        />
      )}

      <nav className="industry-report__chapter-nav" aria-label="报告章节导航">
        <a href="#industry-judgment" aria-label={`01 产业研判 ${judgmentItemCount} 项要点`}>
          <b>01</b><span>产业研判</span><small>{judgmentItemCount} 项</small>
        </a>
        <a href="#industry-detail" aria-label={`02 详细分析 ${detailModuleCount} 个模块`}>
          <b>02</b><span>详细分析</span><small>{detailModuleCount} 个模块</small>
        </a>
        <a href="#industry-audit" aria-label={`03 研究依据 ${auditItemCount} 项依据`}>
          <b>03</b><span>研究依据</span><small>{auditItemCount} 项</small>
        </a>
        {result.llm_review && (
          <a href="#industry-full-report" aria-label="04 完整正文 1 篇">
            <b>04</b><span>完整正文</span><small>1 篇</small>
          </a>
        )}
      </nav>

      <IndustryConclusion result={result} />

      <IndustryResearchTheses result={result} />

      <IndustryReportChanges changes={result.changes} />

      <IndustryOpportunityMap opportunities={result.opportunities} />

      <section id="industry-detail" className="industry-report__section" aria-labelledby="industry-detail-heading">
        <header className="industry-report__section-heading">
          <span>02</span>
          <h2 id="industry-detail-heading">详细分析</h2>
          <small>{detailModuleCount} 个模块</small>
        </header>

        <IndustryDecisionResearch key={result.archive_id || result.name} result={result} />
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
                    <Text strong style={{ color: colors.textPrimary, fontSize: "var(--c-font-base)" }}>{chart.title}</Text>
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
                    <Text style={{ color: colors.textSecondary, fontSize: "var(--c-font-md)", marginBottom: 12, display: "block", lineHeight: "var(--c-leading-normal)" }}>
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
                        fontSize: "var(--c-font-md)",
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
      </section>

      <section id="industry-audit" className="industry-report__section" aria-labelledby="industry-audit-heading">
        <header className="industry-report__section-heading">
          <span>03</span>
          <h2 id="industry-audit-heading">研究依据</h2>
          <small>{auditItemCount} 项依据</small>
        </header>
        <IndustryEvidenceChecks result={result} />
        <IndustryResearchAudit result={result} />
      </section>

      {result.llm_review && (
        <div id="industry-full-report" className="industry-report__full-report-anchor">
          <Collapse
            className="industry-report__full-report"
            items={[{
              key: "full-report",
              label: <span><FileTextOutlined />04 · 完整研究正文</span>,
              children: <MarkdownReport content={result.llm_review} />,
            }]}
          />
        </div>
      )}

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
