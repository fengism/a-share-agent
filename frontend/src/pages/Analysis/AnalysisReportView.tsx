/**
 * 投资研究报告视图（`/analysis/:code?view=report`）。
 *
 * 原 `/investment-research/:code` 页面：只读的专注阅读/打印布局，
 * 保留其专属排版（`.investment-research-report`）与导出行为。
 */

import { useCallback } from "react";
import {
  ArrowLeftOutlined,
  BarChartOutlined,
  DownloadOutlined,
  FileSearchOutlined,
} from "@ant-design/icons";
import { Alert, Button, Card, Empty, Skeleton, Space, Typography } from "antd";
import QueryErrorState from "../../components/QueryErrorState";
import AgentProcessPanel from "../../components/AgentProcessPanel";
import AnalysisProgressSteps from "../../components/workflows/AnalysisProgressSteps";
import WorkflowPageHeader from "../../components/workflows/WorkflowPageHeader";
import WorkflowWorkspace from "../../components/workflows/WorkflowWorkspace";
import AnalysisHistoryRail from "../../features/investment-research/AnalysisHistoryRail";
import AnalysisReportVersions from "../../features/investment-research/AnalysisReportVersions";
import ResearchFrameworkPanel from "../../features/investment-research/ResearchFrameworkPanel";
import FinancialDataSections from "../../features/investment-research/FinancialDataSections";
import { formatAnalysisDate, normalizeAnalysisDate } from "../../features/investment-research/analysisHistoryUrl";
import { useStyles, useTokens } from "../../theme/hooks";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";
import type { AnalysisReportPageState } from "./useAnalysisReportPage";
import "./investment-research.css";

const { Paragraph, Text, Title } = Typography;

export default function AnalysisReportView({ page }: { page: AnalysisReportPageState }) {
  const { pageContainerStyle, cardStyle } = useStyles();
  const t = useTokens();
  const {
    code,
    historyDate,
    isHk,
    pageData,
    pageLoading,
    isPageError,
    pageError,
    retryPage,
    historyLoading,
    isHistoryError,
    historyError,
    retryHistory,
    displayResult,
    isAnalyzing,
    analysisError,
    stages,
    currentStageIndex,
    agentProcess,
    reportDate,
    reportName,
    exportRef,
    isExporting,
    handleExportPdf,
    financialExportData,
    showLatest,
    openValuation,
    openWorkspace,
  } = page;

  // 历史条目链接需要带上 view=report，否则点回历史会掉回工作台。
  const buildResearchHistoryUrl = useCallback((targetCode: string, date: string) => {
    const normalizedDate = normalizeAnalysisDate(date);
    const base = `${buildStockAnalysisUrl(targetCode)}?view=report`;
    return normalizedDate ? `${base}&date=${normalizedDate}` : base;
  }, []);

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
      <Button icon={<BarChartOutlined />} onClick={openWorkspace}>返回个股研究</Button>
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
            <div className="pdf-hide">
              {(isAnalyzing || analysisError || agentProcess.termination) && stages.length > 0 ? (
                <AnalysisProgressSteps
                  stages={stages}
                  currentStageIndex={currentStageIndex}
                  status={analysisError || agentProcess.termination === "failed" ? "error" : agentProcess.termination ?? "running"}
                />
              ) : null}
              <AgentProcessPanel
                plan={agentProcess.plan}
                status={agentProcess.status}
                toolCalls={agentProcess.toolCalls}
                rounds={agentProcess.rounds}
                termination={agentProcess.termination}
                isRunning={isAnalyzing}
              />
            </div>
            {analysisError && !isAnalyzing ? (
              <Alert
                type="error"
                showIcon
                title="个股研究任务失败"
                description={analysisError}
                action={<Button size="small" onClick={openWorkspace}>返回个股研究</Button>}
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

            {(pageLoading || (historyDate && historyLoading)) ? (
              <Card style={cardStyle}>
                <div aria-label="投资研究报告加载中" style={{ minHeight: 420, padding: t.space[4] }}>
                  <Skeleton active paragraph={{ rows: 12 }} />
                </div>
              </Card>
            ) : displayResult ? (
              <div
                ref={exportRef}
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
                  <AnalysisReportVersions analysis={displayResult} />
                  <ResearchFrameworkPanel
                    analysis={displayResult}
                    onOpenValuation={openValuation}
                    forceFullReport={isExporting}
                  />
                </section>
                {isExporting && !isHk ? (
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
  );
}
