/**
 * 个股研究工作台视图（`/analysis/:code` 默认视图）。
 *
 * 只负责渲染与工作台特有的交互（触发/取消分析、推送、自选、导出 Markdown）；
 * 数据获取、工作流与 PDF 导出由 useAnalysisReportPage 提供。
 */

import { useCallback, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { Alert, Button, Skeleton, message } from "antd";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queries";
import QueryErrorState from "../../components/QueryErrorState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import AnalysisHistoryRail from "../../features/investment-research/AnalysisHistoryRail";
import {
  formatAnalysisDate,
  normalizeAnalysisDate,
} from "../../features/investment-research/analysisHistoryUrl";
import { useWorkflowPush } from "../../hooks/useWorkflowPush";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import type { PushRequest } from "../../types/stock";
import AnalysisDataStatus from "./AnalysisDataStatus";
import AnalysisHeaderCard from "./AnalysisHeaderCard";
import AnalysisKeyLevels from "./AnalysisKeyLevels";
import AnalysisPanels from "./AnalysisPanels";
import AnalysisResultSection from "./AnalysisResultSection";
import AnalysisStateSection from "./AnalysisStateSection";
import { buildAnalysisMarkdown } from "./analysisMarkdown";
import type { AnalysisReportPageState } from "./useAnalysisReportPage";
import "./analysis-workspace.css";

type MessageApi = ReturnType<typeof message.useMessage>[0];

export default function AnalysisWorkspaceView({
  page,
  messageApi,
}: {
  page: AnalysisReportPageState;
  messageApi: MessageApi;
}) {
  const { pageContainerStyle } = useStyles();
  const colors = useColors();
  const t = useTokens();
  const navigate = useNavigate();
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
    isCancelling,
    analysisError,
    stages,
    currentStageIndex,
    agentProcess,
    runAnalysis,
    cancelAnalysis,
    exportRef,
    isExporting,
    handleExportPdf,
    financialExportData,
    showLatest,
    openValuation,
    openReport,
  } = page;

  const { push, isPushing } = useWorkflowPush();
  const watchlist = useWatchlist();
  const addWatchlistItem = useAddWatchlistItem();
  const deleteWatchlistItem = useDeleteWatchlistItem();
  const isWatched = Boolean(code && watchlist.data?.items.some((item) => item.stock_code === code));
  const pendingAnalysisRef = useRef(false);

  useEffect(() => {
    if (!pendingAnalysisRef.current || historyDate) return;
    pendingAnalysisRef.current = false;
    void runAnalysis({ force: true });
  }, [historyDate, runAnalysis]);

  const handleAnalyze = useCallback(async () => {
    if (!code) return;
    if (historyDate) {
      pendingAnalysisRef.current = true;
      showLatest();
      return;
    }
    await runAnalysis({ force: Boolean(displayResult) });
  }, [code, displayResult, historyDate, runAnalysis, showLatest]);

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

  const handleExportMarkdown = useCallback(() => {
    if (!displayResult) return;
    const content = buildAnalysisMarkdown(displayResult, pageData?.stock_info);
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    if (typeof URL.createObjectURL === "function") {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      const fileCode = displayResult.stock_code || code || "stock";
      const fileDate = normalizeAnalysisDate(displayResult.analysis_date) || historyDate || new Date().toISOString().slice(0, 10);
      a.download = `投研报告_${fileCode}_${fileDate}.md`;
      a.click();
      URL.revokeObjectURL?.(url);
    }
    messageApi.success("Markdown 投研报告已导出");
  }, [code, displayResult, historyDate, messageApi, pageData?.stock_info]);

  if (pageLoading || (historyDate && historyLoading)) {
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
        <QueryErrorState error={pageError} onRetry={() => retryPage()} title="分析页面数据加载失败" />
      </div>
    );
  }

  const intradayItems = pageData?.intraday?.items ?? [];
  const latestPrice = intradayItems[intradayItems.length - 1]?.price ?? pageData?.stock_info?.current_price;
  const useReportPrice = Boolean(historyDate) || latestPrice == null;

  return (
    <div
      ref={exportRef}
      style={{ ...pageContainerStyle }}
      className={`analysis-page${isExporting ? " pdf-exporting" : ""}`}
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
            intradayData={pageData?.intraday}
            result={displayResult}
            analysisDate={historyDate || undefined}
            isAnalyzing={isAnalyzing}
            isCancelling={isCancelling}
            isPushing={isPushing}
            isWatched={isWatched}
            isWatchlistPending={addWatchlistItem.isPending || deleteWatchlistItem.isPending}
            isExportingPdf={isExporting}
            onToggleWatchlist={handleToggleWatchlist}
            onAnalyze={handleAnalyze}
            onCancel={() => void cancelAnalysis()}
            onExportPdf={handleExportPdf}
            onExportMarkdown={handleExportMarkdown}
            onShowHistory={() => navigate("/analysis")}
            onOpenResearchReport={openReport}
            onPush={handlePush}
          />
        </div>
        <div className="analysis-workspace__main">
          {historyDate && isHistoryError && (
            <Alert
              type="error"
              showIcon
              title={`历史分析 ${formatAnalysisDate(historyDate)} 加载失败`}
              description={historyError instanceof Error ? historyError.message : "请稍后重试"}
              action={(
                <div style={{ display: "flex", gap: 8 }}>
                  <Button size="small" onClick={() => retryHistory()}>重试</Button>
                  <Button size="small" type="primary" onClick={showLatest}>返回最新分析</Button>
                </div>
              )}
              style={{ marginBottom: 16 }}
            />
          )}
          <AnalysisDataStatus pageData={pageData} result={displayResult} />
          <AnalysisKeyLevels
            current={useReportPrice ? displayResult?.current_price : latestPrice}
            currentLabel={useReportPrice && displayResult ? "分析时价格" : "当前价"}
            support={displayResult?.technical?.support_level}
            resistance={displayResult?.technical?.resistance_level}
          />
          <AnalysisStateSection
            isAnalyzing={isAnalyzing}
            error={analysisError}
            stages={stages}
            currentStageIndex={currentStageIndex}
            agentProcess={agentProcess}
          />
        </div>
        <AnalysisPanels
          code={code}
          result={displayResult}
          isExportingPdf={isExporting && !isHk}
          financialExportData={financialExportData}
        />
        <AnalysisResultSection
          result={displayResult}
          isExportingPdf={isExporting}
          onOpenValuation={openValuation}
        />
      </div>
    </div>
  );
}
