import { useCallback, useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, Button, message, Skeleton } from "antd";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  downloadAnalysisPdf,
  downloadAnalysisPdfFromData,
  ensureFundamentalData,
  useAddWatchlistItem,
  useAnalysisHistorySnapshot,
  useAnalysisPageData,
  useDeleteWatchlistItem,
  useStockIntraday,
  useWatchlist,
} from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { loadKlineChart } from "../../charts/klineChartLoader";
import { usePdfExport } from "../../hooks/usePdfExport";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import type { FundamentalExportData, PushRequest } from "../../types/stock";
import AnalysisChartsSection from "./AnalysisChartsSection";
import AnalysisDataStatus from "./AnalysisDataStatus";
import AnalysisHeaderCard from "./AnalysisHeaderCard";
import AnalysisHistoryRail from "../../features/investment-research/AnalysisHistoryRail";
import AnalysisKeyLevels from "./AnalysisKeyLevels";
import AnalysisPanels from "./AnalysisPanels";
import AnalysisStateSection from "./AnalysisStateSection";
import {
  formatAnalysisDate,
  normalizeAnalysisDate,
  parseAnalysisDate,
} from "../../features/investment-research/analysisHistoryUrl";
import { preloadAnalysisPanelModules } from "./analysisPanelLoaders";
import { useAnalysisWorkflowController } from "../../hooks/useAnalysisWorkflowController";
import "./analysis-workspace.css";

export default function Analysis() {
  const colors = useColors();
  const t = useTokens();
  const queryClient = useQueryClient();
  const { pageContainerStyle } = useStyles();
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const dateState = parseAnalysisDate(searchParams.get("date"));
  const historyDate = dateState.date;
  const [messageApi, contextHolder] = message.useMessage();
  const exportRef = useRef<HTMLDivElement>(null);
  const [financialExportData, setFinancialExportData] = useState<FundamentalExportData>();
  const {
    data: pageData,
    isLoading: pageLoading,
    isError: isPageError,
    error: pageError,
    refetch: retryPageData,
  } = useAnalysisPageData(code || "");
  const { data: liveIntradayData } = useStockIntraday(code || "");
  const {
    data: historicalResult,
    isLoading: isHistoricalLoading,
    isError: isHistoricalError,
    error: historicalError,
    refetch: retryHistoricalResult,
  } = useAnalysisHistorySnapshot(code || "", historyDate);
  const { push, isPushing } = useWorkflowPush();
  const watchlist = useWatchlist();
  const addWatchlistItem = useAddWatchlistItem();
  const deleteWatchlistItem = useDeleteWatchlistItem();
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
  const isWatched = Boolean(code && watchlist.data?.items.some((item) => item.stock_code === code));
  const pendingAnalysisRef = useRef(false);

  useEffect(() => {
    if (dateState.kind !== "invalid") return;
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("date");
    setSearchParams(nextParams, { replace: true });
    messageApi.warning("历史日期无效，已返回最新分析");
  }, [dateState.kind, messageApi, searchParams, setSearchParams]);

  useEffect(() => {
    if (!pendingAnalysisRef.current || historyDate) return;
    pendingAnalysisRef.current = false;
    void runAnalysis({ force: true });
  }, [historyDate, runAnalysis]);

  const handleAnalyze = useCallback(async () => {
    if (!code) return;
    if (historyDate) {
      pendingAnalysisRef.current = true;
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete("date");
      setSearchParams(nextParams, { replace: true });
      return;
    }
    await runAnalysis({ force: Boolean(displayResult) });
  }, [code, displayResult, historyDate, runAnalysis, searchParams, setSearchParams]);

  const handleShowLatest = useCallback(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("date");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const handleShowHistory = useCallback(() => {
    navigate("/analysis");
  }, [navigate]);

  const handleOpenResearchReport = useCallback(() => {
    if (!code) return;
    const suffix = historyDate ? `?date=${encodeURIComponent(historyDate)}` : "";
    navigate(`/investment-research/${encodeURIComponent(code)}${suffix}`);
  }, [code, historyDate, navigate]);

  const handlePush = useCallback(async (request: PushRequest) => {
    return Boolean(await push(request));
  }, [push]);

  const handleToggleWatchlist = useCallback(async () => {
    if (!code) return;
    try {
      if (isWatched) {
        await deleteWatchlistItem.mutateAsync(code);
        messageApi.success("已移出自选");
      } else {
        await addWatchlistItem.mutateAsync({ stock_code: code, note: "来自分析工作台" });
        messageApi.success("已加入自选");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "自选操作失败");
    }
  }, [addWatchlistItem, code, deleteWatchlistItem, isWatched, messageApi]);

  const { exportPdf, isExporting: isExportingPdf } = usePdfExport({
    targetRef: exportRef,
    filename: () => {
      const dateText = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      return `${code}-个股研究-${dateText}.pdf`;
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
      const financialPanel = root.querySelector<HTMLElement>("[data-pdf-financial-ready]");
      const revenueBreakdown = root.querySelector<HTMLElement>("[data-pdf-revenue-ready]");
      const keyFinancialMetrics = root.querySelector<HTMLElement>(
        "[data-testid='pdf-key-financial-metrics']",
      );
      const chartHosts = Array.from(root.querySelectorAll<HTMLElement>("[data-pdf-chart]"));
      return financialPanel?.dataset.pdfFinancialReady === "true"
        && revenueBreakdown?.dataset.pdfRevenueReady === "true"
        && Number(revenueBreakdown.dataset.pdfRevenueRowCount) > 0
        && Number(keyFinancialMetrics?.dataset.pdfRowCount) > 0
        && chartHosts.every((host) => host.querySelector("canvas"));
    },
    beforeCapture: async () => {
      await Promise.all([
        preloadAnalysisPanelModules(),
        loadKlineChart(),
      ]);
      if (code) {
        setFinancialExportData(await ensureFundamentalData(queryClient, code));
      }
    },
    onStart: () => {
      setFinancialExportData(undefined);
      messageApi.loading({ content: "正在生成 PDF...", key: "export-pdf" });
    },
    onSuccess: () => {
      setFinancialExportData(undefined);
      messageApi.success({ content: "PDF 导出成功", key: "export-pdf" });
    },
    onError: (error) => {
      setFinancialExportData(undefined);
      console.error("[Analysis] PDF 导出失败", error);
      const detail = error instanceof Error ? `：${error.message}` : "";
      messageApi.error({ content: `PDF 导出失败${detail}`, key: "export-pdf" });
    },
  });

  const reportDate = normalizeAnalysisDate(displayResult?.analysis_date) || historyDate;

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

  if (pageLoading || (historyDate && isHistoricalLoading)) {
    return (
      <div style={pageContainerStyle}>
        <div
          aria-label="分析页面加载中"
          style={{
            minHeight: "calc(100vh - 160px)",
            padding: 24,
            background: colors.cardBg,
            border: `1px solid ${colors.border}`,
            borderRadius: t.radius.lg,
          }}
        >
          <Skeleton active avatar paragraph={{ rows: 14 }} />
        </div>
      </div>
    );
  }

  if (isPageError && !pageData) {
    return (
      <div style={pageContainerStyle}>
        <QueryErrorState error={pageError} onRetry={() => retryPageData()} title="分析页面数据加载失败" />
      </div>
    );
  }

  // Theme CSS variables are injected on <html> by App.tsx (single source of
  // truth, see theme/hooks.ts), so analysis-export.css/markdown.css resolve
  // correctly without a per-page inline injection here.
  return (
    <>
      {contextHolder}
      <div
        ref={exportRef}
        style={{ ...pageContainerStyle }}
        className={`analysis-page${isExportingPdf ? " pdf-exporting" : ""}`}
      >
        <div className="analysis-workspace">
          <AnalysisHistoryRail
            currentCode={code}
            currentDate={normalizeAnalysisDate(displayResult?.analysis_date) || historyDate || undefined}
          />
          <div className="analysis-workspace__header" data-pdf-capture data-pdf-group>
            {code ? <StockWorkspaceNav code={code} /> : null}
            <AnalysisHeaderCard
              code={code}
              pageData={pageData}
              intradayData={liveIntradayData}
              result={displayResult}
              analysisDate={historyDate || undefined}
              isAnalyzing={isAnalyzing}
              isCancelling={isCancelling}
              isPushing={isPushing}
              isWatched={isWatched}
              isWatchlistPending={addWatchlistItem.isPending || deleteWatchlistItem.isPending}
              onToggleWatchlist={handleToggleWatchlist}
              onAnalyze={handleAnalyze}
              onCancel={() => void cancelAnalysis()}
              onExportPdf={handleExportPdf}
              onShowHistory={handleShowHistory}
              onOpenResearchReport={handleOpenResearchReport}
              onPush={handlePush}
            />
          </div>
          <div className="analysis-workspace__main">
            {historyDate && isHistoricalError && (
              <Alert
                type="error"
                showIcon
                title={`历史分析 ${formatAnalysisDate(historyDate)} 加载失败`}
                description={historicalError instanceof Error ? historicalError.message : "请稍后重试"}
                action={(
                  <div style={{ display: "flex", gap: 8 }}>
                    <Button size="small" onClick={() => retryHistoricalResult()}>重试</Button>
                    <Button size="small" type="primary" onClick={handleShowLatest}>返回最新分析</Button>
                  </div>
                )}
                style={{ marginBottom: 16 }}
              />
            )}
            <AnalysisDataStatus pageData={pageData} result={displayResult} />
            <AnalysisKeyLevels
              current={pageData?.key_levels?.current_price}
              support={pageData?.key_levels?.support}
              resistance={pageData?.key_levels?.resistance}
            />
            <AnalysisStateSection
              isAnalyzing={isAnalyzing}
              error={analysisError}
              stages={stages}
              currentStageIndex={currentStageIndex}
              agentProcess={agentProcess}
            />
          </div>
          <div className="analysis-workspace__details">
            <AnalysisChartsSection
              code={code}
              pageData={pageData}
              isExportingPdf={isExportingPdf}
            />
            <AnalysisPanels
              code={code}
              result={displayResult}
              isExportingPdf={isExportingPdf}
              financialExportData={financialExportData}
            />
          </div>
        </div>
      </div>
    </>
  );
}
