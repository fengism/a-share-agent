import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { message, Skeleton } from "antd";
import { useParams } from "react-router-dom";
import { useAnalysisPageData, usePush } from "../../api/queries";
import { streamAnalysis, type AnalysisProgress, type AnalysisStage } from "../../api/sse";
import QueryErrorState from "../../components/QueryErrorState";
import { useAnalysisStore } from "../../store/analysisStore";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisResult, PushRequest } from "../../types/stock";
import AnalysisChartsSection from "./AnalysisChartsSection";
import AnalysisHeaderCard from "./AnalysisHeaderCard";
import AnalysisPanels from "./AnalysisPanels";
import AnalysisStateSection from "./AnalysisStateSection";
import { preloadAnalysisPanelModules } from "./analysisPanelLoaders";

export default function Analysis() {
  const colors = useColors();
  const { pageContainerStyle } = useStyles();
  const { code } = useParams<{ code: string }>();
  const [messageApi, contextHolder] = message.useMessage();
  const exportRef = useRef<HTMLDivElement>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const {
    data: pageData,
    isLoading: pageLoading,
    isError: isPageError,
    error: pageError,
    refetch: retryPageData,
  } = useAnalysisPageData(code || "");
  const pushMutation = usePush();
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

  const displayResult = analysisResult || pageData?.cached_analysis;

  useEffect(() => () => {
    cancelAnalysis?.();
  }, [cancelAnalysis]);

  const handleProgress = useCallback((progress: AnalysisProgress) => {
    switch (progress.type) {
      case "stage_started":
        if (progress.stage) updateAnalysisStage(progress.stage as AnalysisStage, true);
        break;
      case "stage_completed":
      case "stage_failed":
        if (progress.stage) updateAnalysisStage(progress.stage as AnalysisStage);
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
    resetAnalysisProgress();
    setAnalysisResult(null);
    setIsAnalyzing(true);
    setAnalysisError(null);

    try {
      const { promise, cancel } = streamAnalysis(code, handleProgress);
      setCancelAnalysis(() => cancel);
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
  }, [code, handleProgress, messageApi, resetAnalysisProgress, setAnalysisError, setAnalysisResult, setCancelAnalysis, setIsAnalyzing]);

  const handleCancelAnalysis = useCallback(() => {
    if (!cancelAnalysis) return;
    cancelAnalysis();
    setIsAnalyzing(false);
    setCancelAnalysis(null);
    messageApi.info("已取消分析");
  }, [cancelAnalysis, messageApi, setCancelAnalysis, setIsAnalyzing]);

  const handlePush = useCallback(async (request: PushRequest) => {
    try {
      const result = await pushMutation.mutateAsync(request);
      if (result.target === "notion") {
        messageApi.success(
          <span>
            已转存 Notion：<a href={result.url} target="_blank" rel="noreferrer">{result.title}</a>
          </span>,
        );
      } else {
        messageApi.success(`已推送到飞书：${result.message || result.title}`);
      }
    } catch (error) {
      messageApi.error(`推送失败: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [messageApi, pushMutation]);

  const handleExportPdf = useCallback(async () => {
    if (!exportRef.current || !code) return;
    try {
      await preloadAnalysisPanelModules();
      setIsExportingPdf(true);
      messageApi.loading({ content: "正在生成 PDF...", key: "export-pdf" });
      await new Promise((resolve) => requestAnimationFrame(() => resolve(null)));
      const [{ default: html2canvas }, { default: jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(exportRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: colors.pageBg,
      });
      const imageData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imageHeight = canvas.height * pageWidth / canvas.width;
      let heightLeft = imageHeight;
      let position = 0;

      pdf.addImage(imageData, "PNG", 0, position, pageWidth, imageHeight);
      heightLeft -= pageHeight;
      while (heightLeft > 0) {
        position = heightLeft - imageHeight;
        pdf.addPage();
        pdf.addImage(imageData, "PNG", 0, position, pageWidth, imageHeight);
        heightLeft -= pageHeight;
      }

      const dateText = new Date().toISOString().slice(0, 10).replace(/-/g, "");
      pdf.save(`${code}-分析报告-${dateText}.pdf`);
      messageApi.success({ content: "PDF 导出成功", key: "export-pdf" });
    } catch (error) {
      console.error("[Analysis] PDF 导出失败", error);
      messageApi.error({ content: "PDF 导出失败", key: "export-pdf" });
    } finally {
      setIsExportingPdf(false);
    }
  }, [code, colors.pageBg, messageApi]);

  if (pageLoading) {
    return (
      <div style={pageContainerStyle}>
        <div
          aria-label="分析页面加载中"
          style={{
            minHeight: "calc(100vh - 160px)",
            padding: 24,
            background: colors.cardBg,
            border: `1px solid ${colors.border}`,
            borderRadius: 10,
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

  const cssVariables = {
    "--theme-page-bg": colors.pageBg,
    "--theme-card-bg": colors.cardBg,
    "--theme-elevated-bg": colors.elevatedBg,
    "--theme-nested-bg": colors.nestedBg,
    "--theme-border": colors.border,
    "--theme-text-primary": colors.textPrimary,
    "--theme-text-secondary": colors.textSecondary,
    "--theme-primary": colors.primary,
  } as CSSProperties;

  return (
    <>
      {contextHolder}
      <div
        ref={exportRef}
        style={{ ...pageContainerStyle, ...cssVariables }}
        className={isExportingPdf ? "pdf-exporting" : undefined}
      >
        <AnalysisHeaderCard
          code={code}
          pageData={pageData}
          result={displayResult}
          isAnalyzing={isAnalyzing}
          isPushing={pushMutation.isPending}
          onAnalyze={handleAnalyze}
          onCancel={handleCancelAnalysis}
          onExportPdf={handleExportPdf}
          onPush={handlePush}
        />
        <AnalysisStateSection
          isAnalyzing={isAnalyzing}
          result={displayResult}
          error={analysisError}
        />
        <AnalysisChartsSection code={code} pageData={pageData} />
        <AnalysisPanels code={code} result={displayResult} isExportingPdf={isExportingPdf} />
      </div>
    </>
  );
}
