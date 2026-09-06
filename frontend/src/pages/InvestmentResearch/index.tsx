import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  DownloadOutlined,
  FileSearchOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Empty, message, Skeleton, Space, Typography } from "antd";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  downloadAnalysisPdf,
  downloadAnalysisPdfFromData,
  ensureFundamentalData,
  useAnalysisHistorySnapshot,
  useAnalysisPageData,
} from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import AnalysisProgressSteps from "../../components/workflows/AnalysisProgressSteps";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import AnalysisHistoryRail from "../../features/investment-research/AnalysisHistoryRail";
import ResearchFrameworkPanel from "../../features/investment-research/ResearchFrameworkPanel";
import {
  buildAnalysisHistoryUrl,
  formatAnalysisDate,
  normalizeAnalysisDate,
  parseAnalysisDate,
} from "../../features/investment-research/analysisHistoryUrl";
import { useAnalysisWorkflowController } from "../../hooks/useAnalysisWorkflowController";
import { usePdfExport } from "../../hooks/usePdfExport";
import FinancialDataSections from "../../features/investment-research/FinancialDataSections";
import { useColors, useStyles, useTokens } from "../../styles/ui";
import type { FundamentalExportData } from "../../types/stock";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";
import "./investment-research.css";

const { Paragraph, Text, Title } = Typography;

const buildResearchHistoryUrl = (code: string, date: string) => (
  buildAnalysisHistoryUrl(code, date, "/investment-research")
);

export default function InvestmentResearch() {
  const queryClient = useQueryClient();
  const { code = "" } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const dateState = parseAnalysisDate(searchParams.get("date"));
  const historyDate = dateState.date;
  const [messageApi, contextHolder] = message.useMessage();
  const reportRef = useRef<HTMLDivElement>(null);
  const [financialExportData, setFinancialExportData] = useState<FundamentalExportData>();
  const colors = useColors();
  const t = useTokens();
  const { pageContainerStyle, cardStyle } = useStyles();

  const {
    data: pageData,
    isLoading: isPageLoading,
    isError: isPageError,
    error: pageError,
    refetch: retryPage,
  } = useAnalysisPageData(code, { enabled: !historyDate });
  const {
    data: historicalResult,
    isLoading: isHistoryLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: retryHistory,
  } = useAnalysisHistorySnapshot(code, historyDate);
  const {
    displayResult,
    isAnalyzing,
    analysisError,
    stages,
    currentStageIndex,
    agentProcess,
  } = useAnalysisWorkflowController({
    code,
    historyDate,
    cachedResult: pageData?.cached_analysis,
    historicalResult,
    preferredRoute: "investment-research",
  });

  useEffect(() => {
    if (dateState.kind !== "invalid") return;
    const next = new URLSearchParams(searchParams);
    next.delete("date");
    setSearchParams(next, { replace: true });
    messageApi.warning("历史日期无效，已返回最新研究");
  }, [dateState.kind, messageApi, searchParams, setSearchParams]);

  const showLatest = useCallback(() => {
    const next = new URLSearchParams(searchParams);
    next.delete("date");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  const openResearchWorkspace = useCallback(() => {
    if (!code) return;
    const params = new URLSearchParams();
    if (historyDate) params.set("date", historyDate);
    params.set("panel", "research");
    navigate(`${buildStockAnalysisUrl(code)}?${params.toString()}`);
  }, [code, historyDate, navigate]);

  const openValuation = useCallback(() => {
    if (!code) return;
    const params = new URLSearchParams();
    if (historyDate) params.set("date", historyDate);
    params.set("panel", "valuation");
    navigate(`${buildStockAnalysisUrl(code)}?${params.toString()}`);
  }, [code, historyDate, navigate]);

  const reportDate = normalizeAnalysisDate(displayResult?.analysis_date) || historyDate;
  const reportName = displayResult?.stock_name || pageData?.stock_info?.name || code;
  const { exportPdf, isExporting } = usePdfExport({
    targetRef: reportRef,
    filename: () => `${code}-投资研究-${reportDate || new Date().toISOString().slice(0, 10).replace(/-/g, "")}.pdf`,
    backgroundColor: colors.pageBg,
    captureSelector: "[data-pdf-group]",
    sectionSelector: "[data-pdf-capture], [data-pdf-section]",
    preferredScale: 2,
    imageFormat: "PNG",
    pageMargin: 8,
    showPageNumbers: true,
    beforeCapture: async () => {
      if (code) {
        setFinancialExportData(await ensureFundamentalData(queryClient, code));
      }
    },
    isCaptureReady: () => {
      const root = reportRef.current;
      if (!root) return false;
      const financialPanel = root.querySelector<HTMLElement>("[data-pdf-financial-ready]");
      const revenueBreakdown = root.querySelector<HTMLElement>("[data-pdf-revenue-ready]");
      const keyFinancialMetrics = root.querySelector<HTMLElement>(
        "[data-testid='pdf-key-financial-metrics']",
      );
      return financialPanel?.dataset.pdfFinancialReady === "true"
        && revenueBreakdown?.dataset.pdfRevenueReady === "true"
        && Number(revenueBreakdown.dataset.pdfRevenueRowCount) > 0
        && Number(keyFinancialMetrics?.dataset.pdfRowCount) > 0;
    },
    onStart: () => {
      setFinancialExportData(undefined);
      messageApi.loading({ content: "正在生成 PDF...", key: "research-pdf" });
    },
    onSuccess: () => {
      setFinancialExportData(undefined);
      messageApi.success({ content: "PDF 导出成功", key: "research-pdf" });
    },
    onError: (error) => {
      setFinancialExportData(undefined);
      console.error("[InvestmentResearch] PDF 导出失败", error);
      const detail = error instanceof Error ? `：${error.message}` : "";
      messageApi.error({ content: `PDF 导出失败${detail}`, key: "research-pdf" });
    },
  });

  const handleExportPdf = useCallback(async () => {
    if (!code) return;
    const hide = messageApi.loading("正在生成纯矢量投研 PDF 研报...", 0);
    try {
      if (displayResult) {
        await downloadAnalysisPdfFromData(displayResult);
      } else {
        await downloadAnalysisPdf(code, reportDate || undefined);
      }
      hide();
      messageApi.success("PDF 研报已生成并开始下载");
    } catch (backendError) {
      hide();
      console.warn("[InvestmentResearch] 后端矢量 PDF 导出受阻，切换至客户端增强模式:", backendError);
      await exportPdf();
    }
  }, [code, displayResult, exportPdf, messageApi, reportDate]);

  const historyRail = code ? (
    <AnalysisHistoryRail
      currentCode={code}
      currentDate={reportDate || undefined}
      buildHistoryUrl={buildResearchHistoryUrl}
      allHistoryTarget="/analysis"
      embedded
    />
  ) : null;

  const headerActions = code ? (
    <Space wrap>
      {historyDate ? (
        <Button icon={<ArrowLeftOutlined />} onClick={showLatest}>返回最新</Button>
      ) : null}
      <Button icon={<BarChartOutlined />} onClick={openResearchWorkspace}>返回个股研究</Button>
      <Button
        icon={<DownloadOutlined />}
        loading={isExporting}
        disabled={!displayResult || isAnalyzing}
        onClick={() => void handleExportPdf()}
      >
        导出 PDF
      </Button>
    </Space>
  ) : null;

  return (
    <>
      {contextHolder}
      <div style={pageContainerStyle} className="investment-research-page">
        <WorkflowPageHeader
          title="投资研究报告"
          description="聚焦生意、护城河、管理层、风险与估值情景的专注阅读视图。"
          icon={<FileSearchOutlined />}
          actions={headerActions}
        />
        <WorkflowWorkspace
          historyTitle="最近投资研究"
          historyButtonLabel="研究历史"
          historyVersion={`${code}:${historyDate}`}
          history={historyRail}
        >
          {code ? (
            <div className="investment-research-content">
              {isAnalyzing && stages.length > 0 ? (
                <AnalysisProgressSteps
                  stages={stages}
                  currentStageIndex={currentStageIndex}
                  status="running"
                />
              ) : null}
              <AgentProcessPanel
                plan={agentProcess.plan}
                status={agentProcess.status}
                toolCalls={agentProcess.toolCalls}
                isRunning={isAnalyzing}
              />
              {analysisError && !isAnalyzing ? (
                <Alert
                  type="error"
                  showIcon
                  title="个股研究任务失败"
                  description={analysisError}
                  action={<Button size="small" onClick={openResearchWorkspace}>返回个股研究</Button>}
                />
              ) : null}
              {historyDate && isHistoryError ? (
                <Alert
                  type="error"
                  showIcon
                  title={`历史报告 ${formatAnalysisDate(historyDate)} 加载失败`}
                  description={historyError instanceof Error ? historyError.message : "请稍后重试"}
                  action={(
                    <Space wrap>
                      <Button size="small" onClick={() => retryHistory()}>重试</Button>
                      <Button size="small" type="primary" onClick={showLatest}>返回最新</Button>
                    </Space>
                  )}
                />
              ) : null}
              {!historyDate && isPageError && !pageData ? (
                <QueryErrorState error={pageError} onRetry={() => retryPage()} title="股票资料加载失败" />
              ) : null}

              {(isPageLoading || (historyDate && isHistoryLoading)) ? (
                <Card style={cardStyle}>
                  <div aria-label="投资研究报告加载中" style={{ minHeight: 420, padding: t.space[4] }}>
                    <Skeleton active paragraph={{ rows: 12 }} />
                  </div>
                </Card>
              ) : displayResult ? (
                <div
                  ref={reportRef}
                  className={`investment-research-report stock-research-report${isExporting ? " pdf-exporting" : ""}`}
                >
                  <header className="investment-research-report__header" data-pdf-group>
                    <span>INVESTMENT RESEARCH</span>
                    <Title level={2}>{reportName}</Title>
                    <div>
                      <Text>{code}</Text>
                      <Text type="secondary">
                        {historyDate ? "历史快照" : "最新报告"} · {formatAnalysisDate(reportDate)}
                      </Text>
                      {displayResult.prompt_trace?.generated_at ? (
                        <Text type="secondary">生成于 {displayResult.prompt_trace.generated_at}</Text>
                      ) : null}
                      {displayResult.prompt_trace?.prompt_version ? (
                        <Text type="secondary">Prompt {displayResult.prompt_trace.prompt_version}</Text>
                      ) : null}
                      {displayResult.prompt_trace?.model ? (
                        <Text type="secondary">模型 {displayResult.prompt_trace.model}</Text>
                      ) : null}
                    </div>
                  </header>
                  <section data-pdf-group>
                    <ResearchFrameworkPanel
                      analysis={displayResult}
                      onOpenValuation={openValuation}
                      forceFullReport={isExporting}
                    />
                  </section>
                  {isExporting ? (
                    <section className="investment-research-report__financial" data-pdf-capture>
                      <Title level={3} data-pdf-group>营收构成与关键财务指标</Title>
                      <FinancialDataSections
                        code={code}
                        isExportingPdf
                        exportData={financialExportData}
                      />
                    </section>
                  ) : null}
                </div>
              ) : !isPageError && !isHistoryError ? (
                <Card style={cardStyle}>
                  <div className="investment-research-no-report">
                    <Empty
                      image={Empty.PRESENTED_IMAGE_SIMPLE}
                      description="尚无投资研究报告"
                    />
                    <Paragraph type="secondary">请返回个股研究生成完整分析。</Paragraph>
                  </div>
                </Card>
              ) : null}
            </div>
          ) : null}
        </WorkflowWorkspace>
      </div>
    </>
  );
}
