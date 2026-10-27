/**
 * 个股分析的共享页面管线。
 *
 * `/analysis/:code` 现在承载两个视图（`?view=report` 切换），两者共用同一份
 * 数据获取、工作流控制器与 PDF 导出；此前这些逻辑在两个页面里各写了一遍，
 * 并且已经开始分叉（导出就绪判定、港股时机、请求开关）。
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { message } from "antd";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  downloadAnalysisPdf,
  downloadAnalysisPdfFromData,
  ensureFundamentalData,
  useAnalysisHistorySnapshot,
  useAnalysisPageData,
} from "../../api/queries";
import {
  buildStockValuationUrl,
  normalizeAnalysisDate,
  parseAnalysisDate,
} from "../../features/investment-research/analysisHistoryUrl";
import { useAnalysisWorkflowController } from "../../hooks/useAnalysisWorkflowController";
import { usePdfExport } from "../../hooks/usePdfExport";
import { useColors } from "../../theme/hooks";
import type { FundamentalExportData } from "../../types/stock";
import { buildStockAnalysisUrl, isHkStockCode } from "../../utils/stockLinks";
import { marketDateStamp } from "../../utils/marketTime";
import { preloadAnalysisPanelModules } from "./analysisPanelLoaders";

export type AnalysisViewMode = "workspace" | "report";

type MessageApi = ReturnType<typeof message.useMessage>[0];

export function useAnalysisReportPage({
  code,
  view,
  messageApi,
}: {
  code: string;
  view: AnalysisViewMode;
  messageApi: MessageApi;
}) {
  const queryClient = useQueryClient();
  const colors = useColors();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const dateState = parseAnalysisDate(searchParams.get("date"));
  const historyDate = dateState.date;
  const isHk = isHkStockCode(code);
  const exportRef = useRef<HTMLDivElement>(null);
  const [financialExportData, setFinancialExportData] = useState<FundamentalExportData>();

  // 工作台即使在看历史快照时也需要行情/资料面板；报告阅读视图看历史时不必再拉行情。
  const {
    data: pageData,
    isLoading: pageLoading,
    isError: isPageError,
    error: pageError,
    refetch: retryPage,
  } = useAnalysisPageData(code, { enabled: view === "workspace" || !historyDate });

  const {
    data: historicalResult,
    isLoading: historyLoading,
    isError: isHistoryError,
    error: historyError,
    refetch: retryHistory,
  } = useAnalysisHistorySnapshot(code, historyDate);

  const {
    displayResult,
    isAnalyzing,
    isCancelling,
    analysisError,
    stages,
    currentStageIndex,
    agentProcess,
    runAnalysis,
    cancelAnalysis,
  } = useAnalysisWorkflowController({
    code,
    historyDate,
    cachedResult: pageData?.cached_analysis,
    historicalResult,
    onSuccess: () => messageApi.success("研究完成"),
    onError: (error) => messageApi.error(`研究失败: ${error.message}`),
    onCancelled: (result) => messageApi.info(
      result === "cancelled"
        ? "已停止研究"
        : result === "completed"
          ? "任务已完成，正在刷新结果"
          : "已停止等待，后台共享任务仍在运行",
    ),
  });

  useEffect(() => {
    if (dateState.kind !== "invalid") return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("date");
    setSearchParams(nextParams, { replace: true });
    messageApi.warning("历史日期无效，已返回最新分析");
  }, [dateState.kind, messageApi, searchParams, setSearchParams]);

  const showLatest = useCallback(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("date");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const openValuation = useCallback(() => {
    if (code) navigate(buildStockValuationUrl(code, historyDate));
  }, [code, historyDate, navigate]);

  /** 工作台 → 报告阅读视图。 */
  const openReport = useCallback(() => {
    if (!code) return;
    const params = new URLSearchParams({ view: "report" });
    if (historyDate) params.set("date", historyDate);
    navigate(`${buildStockAnalysisUrl(code)}?${params.toString()}`);
  }, [code, historyDate, navigate]);

  /** 报告阅读视图 → 工作台（定位到研究结论）。 */
  const openWorkspace = useCallback(() => {
    if (!code) return;
    const params = new URLSearchParams({ panel: "research" });
    if (historyDate) params.set("date", historyDate);
    navigate(`${buildStockAnalysisUrl(code)}?${params.toString()}`);
  }, [code, historyDate, navigate]);

  const reportDate = normalizeAnalysisDate(displayResult?.analysis_date) || historyDate;
  const reportName = displayResult?.stock_name || pageData?.stock_info?.name || code;

  const { exportPdf, isExporting } = usePdfExport({
    targetRef: exportRef,
    filename: () => {
      const dateText = reportDate || marketDateStamp().replace(/-/g, "");
      return view === "report"
        ? `${code}-投资研究-${dateText}.pdf`
        : `${code}-个股研究-${dateText}.pdf`;
    },
    backgroundColor: colors.pageBg,
    captureSelector: "[data-pdf-group]",
    sectionSelector: "[data-pdf-capture], [data-pdf-section]",
    preferredScale: 2,
    imageFormat: "PNG",
    pageMargin: 8,
    showPageNumbers: true,
    isCaptureReady: () => {
      const root = exportRef.current;
      if (!root) return false;
      // 图表宿主只在工作台渲染（ChipDistributionPanel）；报告视图没有该节点时
      // every() 对空集合返回 true，因此同一套判定对两个视图都成立。
      const chartHosts = Array.from(root.querySelectorAll<HTMLElement>("[data-pdf-chart]"));
      const chartHostsReady = chartHosts.every((host) => host.querySelector("canvas"));
      if (isHk) return chartHostsReady;
      const financialPanel = root.querySelector<HTMLElement>("[data-pdf-financial-ready]");
      const revenueBreakdown = root.querySelector<HTMLElement>("[data-pdf-revenue-ready]");
      const keyFinancialMetrics = root.querySelector<HTMLElement>(
        "[data-testid='pdf-key-financial-metrics']",
      );
      return financialPanel?.dataset.pdfFinancialReady === "true"
        && revenueBreakdown?.dataset.pdfRevenueReady === "true"
        && Number(revenueBreakdown.dataset.pdfRevenueRowCount) > 0
        && Number(keyFinancialMetrics?.dataset.pdfRowCount) > 0
        && chartHostsReady;
    },
    beforeCapture: async () => {
      // 港股没有 A 股口径财务数据，预加载面板只会触发注定失败的请求
      if (isHk || !code) return;
      await preloadAnalysisPanelModules();
      setFinancialExportData(await ensureFundamentalData(queryClient, code));
    },
    onStart: () => {
      setFinancialExportData(undefined);
      messageApi.loading({ content: "正在生成 PDF...", key: "analysis-pdf" });
    },
    onSuccess: () => {
      setFinancialExportData(undefined);
      messageApi.success({ content: "PDF 导出成功", key: "analysis-pdf" });
    },
    onError: (error) => {
      setFinancialExportData(undefined);
      console.error("[Analysis] PDF 导出失败", error);
      const detail = error instanceof Error ? `：${error.message}` : "";
      messageApi.error({ content: `PDF 导出失败${detail}`, key: "analysis-pdf" });
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
      console.warn("[Analysis] 后端矢量 PDF 导出受阻，切换至客户端增强模式:", backendError);
      await exportPdf();
    }
  }, [code, displayResult, exportPdf, messageApi, reportDate]);

  return {
    code,
    view,
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
    isCancelling,
    analysisError,
    stages,
    currentStageIndex,
    agentProcess,
    runAnalysis,
    cancelAnalysis,
    reportDate,
    reportName,
    exportRef,
    exportPdf,
    isExporting,
    handleExportPdf,
    financialExportData,
    showLatest,
    openValuation,
    openReport,
    openWorkspace,
  };
}

export type AnalysisReportPageState = ReturnType<typeof useAnalysisReportPage>;
