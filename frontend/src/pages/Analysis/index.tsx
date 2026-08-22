import { useCallback, useEffect, useRef } from "react";
import { Alert, Button, message, Skeleton } from "antd";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  useAddWatchlistItem,
  useAnalysisHistorySnapshot,
  useAnalysisPageData,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queries";
import { streamAnalysis, type AnalysisProgress, type AnalysisStage } from "../../api/sse";
import QueryErrorState from "../../components/QueryErrorState";
import { usePdfExport } from "../../hooks/usePdfExport";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useAnalysisStore } from "../../store/analysisStore";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import type { AnalysisResult, PushRequest } from "../../types/stock";
import AnalysisChartsSection from "./AnalysisChartsSection";
import AnalysisDataStatus from "./AnalysisDataStatus";
import AnalysisHeaderCard from "./AnalysisHeaderCard";
import AnalysisHistoryRail from "./AnalysisHistoryRail";
import AnalysisContextSummary from "./AnalysisContextSummary";
import AnalysisDecisionBoard from "./AnalysisDecisionBoard";
import AnalysisPanels from "./AnalysisPanels";
import AnalysisStateSection from "./AnalysisStateSection";
import { formatAnalysisDate, normalizeAnalysisDate } from "./analysisHistoryUrl";
import { preloadAnalysisPanelModules } from "./analysisPanelLoaders";
import "./analysis-workspace.css";

export default function Analysis() {
  const colors = useColors();
  const t = useTokens();
  const { pageContainerStyle } = useStyles();
  const { code } = useParams<{ code: string }>();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const historyDate = normalizeAnalysisDate(searchParams.get("date"));
  const [messageApi, contextHolder] = message.useMessage();
  const exportRef = useRef<HTMLDivElement>(null);
  const {
    data: pageData,
    isLoading: pageLoading,
    isError: isPageError,
    error: pageError,
    refetch: retryPageData,
  } = useAnalysisPageData(code || "");
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
  const isAnalyzing = useAnalysisStore((state) => state.isAnalyzing);
  const setIsAnalyzing = useAnalysisStore((state) => state.setIsAnalyzing);
  const analysisResult = useAnalysisStore((state) => state.analysisResult);
  const setAnalysisResult = useAnalysisStore((state) => state.setAnalysisResult);
  const updateAnalysisStage = useAnalysisStore((state) => state.updateAnalysisStage);
  const analysisError = useAnalysisStore((state) => state.analysisError);
  const setAnalysisError = useAnalysisStore((state) => state.setAnalysisError);
  const cancelAnalysis = useAnalysisStore((state) => state.cancelAnalysis);
  const setCancelAnalysis = useAnalysisStore((state) => state.setCancelAnalysis);
  const resetAnalysisProgress = useAnalysisStore((state) => state.resetAnalysisProgress);

  const displayResult = analysisResult || historicalResult || (!historyDate ? pageData?.cached_analysis : null);
  const isWatched = Boolean(code && watchlist.data?.items.some((item) => item.stock_code === code));

  useEffect(() => {
    const state = useAnalysisStore.getState();
    state.cancelAnalysis?.();
    state.setIsAnalyzing(false);
    state.setCancelAnalysis(null);
    state.setAnalysisResult(null);
    state.setAnalysisError(null);
    state.resetAnalysisProgress();
  }, [code, historyDate]);

  useEffect(() => () => {
    cancelAnalysis?.();
  }, [cancelAnalysis]);

  const handleProgress = useCallback((progress: AnalysisProgress) => {
    switch (progress.type) {
      case "stage_started":
        if (progress.stage) updateAnalysisStage(progress.stage as AnalysisStage, progress.total_stages, true);
        break;
      case "stage_completed":
      case "stage_failed":
        if (progress.stage) updateAnalysisStage(progress.stage as AnalysisStage, progress.total_stages);
        break;
      case "complete":
      case "cached":
        if (progress.result) setAnalysisResult(progress.result);
        break;
      case "error":
        setAnalysisError(progress.error || "分析失败");
        break;
    }
  }, [setAnalysisError, setAnalysisResult, updateAnalysisStage]);

  const handleAnalyze = useCallback(async () => {
    if (!code) return;
    if (historyDate) {
      const nextParams = new URLSearchParams(searchParams);
      nextParams.delete("date");
      setSearchParams(nextParams, { replace: true });
    }
    resetAnalysisProgress();
    setAnalysisResult(null);
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const { promise, cancel } = streamAnalysis(code, handleProgress);
      setCancelAnalysis(cancel);
      const result: AnalysisResult = await promise;
      setAnalysisResult(result);
      messageApi.success("分析完成");
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "未知错误";
      setAnalysisError(errorMessage);
      messageApi.error(`分析失败: ${errorMessage}`);
    } finally {
      setIsAnalyzing(false);
      setCancelAnalysis(null);
    }
  }, [code, handleProgress, historyDate, messageApi, resetAnalysisProgress, searchParams, setAnalysisError, setAnalysisResult, setCancelAnalysis, setIsAnalyzing, setSearchParams]);

  const handleShowLatest = useCallback(() => {
    const nextParams = new URLSearchParams(searchParams);
    nextParams.delete("date");
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  const handleShowHistory = useCallback(() => {
    navigate("/analysis");
  }, [navigate]);

  const handleCancelAnalysis = useCallback(() => {
    if (!cancelAnalysis) return;
    cancelAnalysis();
    setIsAnalyzing(false);
    setCancelAnalysis(null);
    messageApi.info("已取消分析");
  }, [cancelAnalysis, messageApi, setCancelAnalysis, setIsAnalyzing]);

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
      return `${code}-分析报告-${dateText}.pdf`;
    },
    backgroundColor: colors.pageBg,
    beforeCapture: preloadAnalysisPanelModules,
    onStart: () => messageApi.loading({ content: "正在生成 PDF...", key: "export-pdf" }),
    onSuccess: () => messageApi.success({ content: "PDF 导出成功", key: "export-pdf" }),
    onError: (error) => {
      console.error("[Analysis] PDF 导出失败", error);
      messageApi.error({ content: "PDF 导出失败", key: "export-pdf" });
    },
  });

  const handleExportPdf = useCallback(async () => {
    if (!code) return;
    await exportPdf();
  }, [code, exportPdf]);

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
          <AnalysisHistoryRail currentCode={code} currentDate={historyDate || undefined} />
          <div className="analysis-workspace__header">
            <AnalysisHeaderCard
              code={code}
              pageData={pageData}
              result={displayResult}
              analysisDate={historyDate || undefined}
              isAnalyzing={isAnalyzing}
              isPushing={isPushing}
              isWatched={isWatched}
              isWatchlistPending={addWatchlistItem.isPending || deleteWatchlistItem.isPending}
              onToggleWatchlist={handleToggleWatchlist}
              onAnalyze={handleAnalyze}
              onCancel={handleCancelAnalysis}
              onExportPdf={handleExportPdf}
              onShowHistory={handleShowHistory}
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
            <AnalysisStateSection
              isAnalyzing={isAnalyzing}
              result={displayResult}
              error={analysisError}
            />
            {displayResult ? <AnalysisDecisionBoard result={displayResult} /> : null}
            <AnalysisContextSummary pageData={pageData} result={displayResult} />
          </div>
          <div className="analysis-workspace__details">
            <AnalysisChartsSection code={code} pageData={pageData} />
            <AnalysisPanels code={code} result={displayResult} isExportingPdf={isExportingPdf} />
          </div>
        </div>
      </div>
    </>
  );
}
