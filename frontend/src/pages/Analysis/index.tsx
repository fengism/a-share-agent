import { useParams } from "react-router-dom";
import { Spin, Card, Segmented, Space, Typography, Row, Col, Tabs, Button, Alert, message } from "antd";
import { DownloadOutlined, ThunderboltOutlined, StopOutlined } from "@ant-design/icons";
// html2canvas & jsPDF are loaded lazily inside handleExportPdf (kept out of the initial bundle)
import { useAnalysisPageData, usePush } from "../../api/queries";
import PushModal from "../../components/PushModal";
import type { PushRequest } from "../../types/stock";
import { useColors, useStyles } from "../../theme/hooks";
import { streamAnalysis } from "../../api/sse";
import type { AnalysisProgress, AnalysisStage } from "../../api/sse";
import KlineChart from "../../charts/KlineChart";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import FundamentalPanel from "./FundamentalPanel";
import TechnicalPanel from "./TechnicalPanel";
import SentimentPanel from "./SentimentPanel";
import FundFlowPanel from "./FundFlowPanel";
import ValuationPanel from "./ValuationPanel";
import AIConclusion from "./AIConclusion";
import AnalysisProgressSteps from "./AnalysisProgressSteps";
import SkeletonAIConclusion from "./SkeletonAIConclusion";
import { useAnalysisStore } from "../../store/analysisStore";
import { useState, useEffect, useCallback, useRef } from "react";
import type { AnalysisResult } from "../../types/stock";
import { formatAmountWanYi, formatMarketCap } from "../../utils/format";

const { Title } = Typography;

export default function Analysis() {
  const c = useColors();
  const { cardStyle, gradientHeaderStyle, pageContainerStyle, sectionCardBodyStyle } = useStyles();
  const { code } = useParams<{ code: string }>();
  const [messageApi, contextHolder] = message.useMessage();
  const exportRef = useRef<HTMLDivElement>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const { data: pageData, isLoading: pageLoading } = useAnalysisPageData(code || "");
  const [period, setPeriod] = useState<string>("daily");
  const [adjust, setAdjust] = useState<string>("qfq");
  const [activePanelKey, setActivePanelKey] = useState<string>("fundamental");
  const exportNotionMutation = usePush();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const {
    isAnalyzing,
    setIsAnalyzing,
    analysisResult,
    setAnalysisResult,
    analysisStages,
    currentStageIndex,
    updateAnalysisStage,
    analysisError,
    setAnalysisError,
    cancelAnalysis,
    setCancelAnalysis,
    resetAnalysisProgress,
  } = useAnalysisStore();

  const displayResult = analysisResult || pageData?.cached_analysis;
  const latestKline = pageData?.kline?.items?.length ? pageData.kline.items[pageData.kline.items.length - 1] : null;

  const info = pageData?.stock_info;
  const intradayData = pageData?.intraday;
  const klineData = pageData?.kline;
  const valuation = pageData?.valuation;

  const priceSnapshot = {
    latestPrice: latestKline?.close ?? null,
    latestChangePct: latestKline?.change_pct ?? null,
    marketCap: info?.market_cap ?? null,
    listingDate: info?.listing_date ?? null,
  };

  const valuationSnapshot = {
    peTtm: typeof valuation?.pe_ttm === "number" ? valuation.pe_ttm : null,
    pb: typeof valuation?.pb === "number" ? valuation.pb : null,
  };

  useEffect(() => {
    return () => {
      if (cancelAnalysis) {
        cancelAnalysis();
      }
    };
  }, [cancelAnalysis]);

  const handleProgress = useCallback((progress: AnalysisProgress) => {
    switch (progress.type) {
      case "stage_started": {
        if (progress.stage) {
          updateAnalysisStage(progress.stage as AnalysisStage, true);
        }
        break;
      }
      case "stage_completed":
      case "stage_failed": {
        if (progress.stage) {
          updateAnalysisStage(progress.stage as AnalysisStage);
        }
        break;
      }
      case "complete":
      case "cached": {
        if (progress.result) {
          setAnalysisResult(progress.result);
        }
        break;
      }
      case "error": {
        setAnalysisError(progress.error || "分析失败");
        break;
      }
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
    } catch (e: unknown) {
      const errMsg = e instanceof Error ? e.message : "未知错误";
      setAnalysisError(errMsg);
      messageApi.error(`分析失败: ${errMsg}`);
    } finally {
      setIsAnalyzing(false);
      setCancelAnalysis(null);
    }
  }, [code, handleProgress, messageApi, resetAnalysisProgress, setAnalysisError, setAnalysisResult, setCancelAnalysis, setIsAnalyzing]);

  const handleCancelAnalysis = useCallback(() => {
    if (cancelAnalysis) {
      cancelAnalysis();
      setIsAnalyzing(false);
      setCancelAnalysis(null);
      messageApi.info("已取消分析");
    }
  }, [cancelAnalysis, messageApi, setCancelAnalysis, setIsAnalyzing]);

  const handlePeriodChange = (v: string) => {
    setPeriod(v);
  };

  const handleAdjustChange = (v: string) => {
    setAdjust(v);
  };

  const handlePush = useCallback(async (req: PushRequest) => {
    try {
      const result = await exportNotionMutation.mutateAsync(req);
      if (result.target === "notion") {
        messageApi.success(
          <span>
            已转存 Notion：<a href={result.url} target="_blank" rel="noreferrer">{result.title}</a>
          </span>
        );
      } else {
        messageApi.success(`已推送到飞书：${result.message || result.title}`);
      }
    } catch (error) {
      messageApi.error(`推送失败: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setPushModalOpen(false);
    }
  }, [exportNotionMutation, messageApi]);

  const handleExportPdf = useCallback(async () => {
    if (!exportRef.current || !code) return;
    try {
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
        backgroundColor: c.pageBg,
      });
      const imgData = canvas.toDataURL("image/png");
      const pdf = new jsPDF("p", "mm", "a4");
      const pageWidth = pdf.internal.pageSize.getWidth();
      const pageHeight = pdf.internal.pageSize.getHeight();
      const imgWidth = pageWidth;
      const imgHeight = canvas.height * imgWidth / canvas.width;

      let heightLeft = imgHeight;
      let position = 0;

      pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
      heightLeft -= pageHeight;

      while (heightLeft > 0) {
        position = heightLeft - imgHeight;
        pdf.addPage();
        pdf.addImage(imgData, "PNG", 0, position, imgWidth, imgHeight);
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
  }, [code, messageApi, c.pageBg]);

  if (pageLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

  // CSS custom properties for the <style> block to reference
  const cssVars = {
    "--theme-page-bg": c.pageBg,
    "--theme-card-bg": c.cardBg,
    "--theme-elevated-bg": c.elevatedBg,
    "--theme-nested-bg": c.nestedBg,
    "--theme-border": c.border,
    "--theme-text-primary": c.textPrimary,
    "--theme-text-secondary": c.textSecondary,
    "--theme-primary": c.primary,
  } as React.CSSProperties;

  const panelItems = [
    {
      key: "fundamental",
      label: "基本面",
      children: code ? <FundamentalPanel code={code} analysis={displayResult} /> : null,
    },
    {
      key: "technical",
      label: "技术面",
      children: code ? <TechnicalPanel code={code} analysis={displayResult} /> : null,
    },
    {
      key: "valuation",
      label: "估值面",
      children: code ? <ValuationPanel code={code} analysis={displayResult} /> : null,
    },
    {
      key: "sentiment",
      label: "情绪面",
      children: code ? <SentimentPanel code={code} analysis={displayResult} /> : null,
    },
    {
      key: "fundflow",
      label: "资金流向",
      children: code ? <FundFlowPanel code={code} /> : null,
    },
  ];

  const exportPanelContent = isExportingPdf
    ? panelItems.map((item) => (
        <div key={item.key} className="pdf-section-block" style={{ marginTop: item.key === "fundamental" ? 0 : 20 }}>
          <div className="pdf-section-title" style={{ fontSize: 15, fontWeight: 700, color: c.textPrimary, marginBottom: 12 }}>
            {item.label}
          </div>
          {item.children}
        </div>
      ))
    : null;

  const upColor = c.up;
  const downColor = c.down;
  const changeColor = latestKline ? ((latestKline.change_pct ?? 0) > 0 ? upColor : (latestKline.change_pct ?? 0) < 0 ? downColor : c.textPrimary) : c.textPrimary;
  const isDown = latestKline && (latestKline.change_pct ?? 0) < 0;

  return (
    <>
      {contextHolder}
      <div ref={exportRef} style={{ ...pageContainerStyle, ...cssVars }} className={isExportingPdf ? "pdf-exporting" : undefined}>
        <div
          style={{
            ...cardStyle,
            ...gradientHeaderStyle,
            marginBottom: 20,
            padding: "22px 24px 18px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 16, marginBottom: 14 }}>
            <div>
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
                <Title level={3} style={{ margin: 0, color: c.textPrimary, letterSpacing: 0.2 }}>
                  {info?.name || code}
                </Title>
                <span style={{ fontSize: 14, color: c.textSecondary, fontWeight: 500 }}>
                  {info?.code}
                </span>
              </div>
              <div style={{ marginTop: 8, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                {info?.first_industry && (
                  <span style={{ fontSize: 12, color: c.textSecondary, background: c.elevatedBg, border: `1px solid ${c.border}`, padding: "3px 10px", borderRadius: 999 }}>
                    {info.first_industry.name}
                  </span>
                )}
                {info?.second_industry && (
                  <span style={{ fontSize: 12, color: c.textSecondary, background: c.elevatedBg, border: `1px solid ${c.border}`, padding: "3px 10px", borderRadius: 999 }}>
                    {info.second_industry.name}
                  </span>
                )}
                {priceSnapshot.listingDate && (
                  <span style={{ fontSize: 12, color: c.textSecondary }}>上市日期 {priceSnapshot.listingDate}</span>
                )}
              </div>
            </div>
            <Space size={10} className="pdf-hide">
              <Button
                size="large"
                icon={<DownloadOutlined />}
                onClick={handleExportPdf}
                disabled={!displayResult}
                style={{ borderRadius: 8, height: 42, fontWeight: 600 }}
              >
                导出 PDF
              </Button>
              <Button
                size="large"
                onClick={() => setPushModalOpen(true)}
                disabled={!displayResult}
                style={{ borderRadius: 8, height: 42, fontWeight: 600 }}
              >
                推送
              </Button>
              <PushModal
                open={pushModalOpen}
                type="analysis"
                code={code}
                onConfirm={handlePush}
                onCancel={() => setPushModalOpen(false)}
                loading={exportNotionMutation.isPending}
              />
              {isAnalyzing ? (
                <Button size="large" danger icon={<StopOutlined />} onClick={handleCancelAnalysis} style={{ borderRadius: 8, height: 42, fontWeight: 600 }}>
                  取消分析
                </Button>
              ) : (
                <Button
                  type="primary"
                  size="large"
                  icon={<ThunderboltOutlined />}
                  onClick={handleAnalyze}
                  style={{ borderRadius: 8, height: 42, paddingInline: 24, fontWeight: 600 }}
                >
                  智能分析
                </Button>
              )}
            </Space>
          </div>

          <div style={{ display: "grid", gap: 14 }}>
            <Row gutter={[14, 14]} align="stretch">
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: isDown ? c.downCardGradient : c.upCardGradient, border: `1px solid ${isDown ? `${c.down}40` : `${c.up}40`}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>最新股价</div>
                  <div style={{ fontSize: 32, fontWeight: 800, color: changeColor, letterSpacing: 0.2 }}>
                    {priceSnapshot.latestPrice != null ? `¥${priceSnapshot.latestPrice.toFixed(2)}` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: isDown ? c.downCardGradient : c.upCardGradient, border: `1px solid ${isDown ? `${c.down}40` : `${c.up}40`}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>单日涨跌幅</div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: changeColor }}>
                    {priceSnapshot.latestChangePct != null ? `${priceSnapshot.latestChangePct > 0 ? "+" : ""}${priceSnapshot.latestChangePct.toFixed(2)}%` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? c.upCardGradient : c.elevatedBg, border: `1px solid ${valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? `${c.up}40` : c.border}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>市盈率(TTM)</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? c.up : c.textPrimary }}>{valuationSnapshot.peTtm != null ? valuationSnapshot.peTtm.toFixed(2) : "-"}</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div style={{ padding: "14px 16px", background: valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? c.upCardGradient : c.elevatedBg, border: `1px solid ${valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? `${c.up}40` : c.border}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>市净率</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? c.up : c.textPrimary }}>{valuationSnapshot.pb != null ? valuationSnapshot.pb.toFixed(2) : "-"}</div>
                </div>
              </Col>
            </Row>
            <Row gutter={[14, 14]} align="stretch">
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>成交额</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>{formatAmountWanYi(latestKline?.amount)}</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>换手率</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>
                    {latestKline?.turnover_pct != null ? `${latestKline.turnover_pct.toFixed(2)}%` : info?.turnover_pct != null ? `${info.turnover_pct.toFixed(2)}%` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>总市值</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>{formatMarketCap(priceSnapshot.marketCap)}</div>
                </div>
              </Col>
            </Row>
          </div>
        </div>

        {/* Progress Steps */}
        {isAnalyzing && (
          <Card
            size="small"
            style={{ ...cardStyle, marginBottom: 16 }}
            styles={{ body: sectionCardBodyStyle }}
          >
            <AnalysisProgressSteps stages={analysisStages} currentStageIndex={currentStageIndex} />
          </Card>
        )}

        {/* AI Conclusion or Skeleton */}
        {(displayResult || isAnalyzing) && (
          <div className="pdf-avoid-break" style={{ marginBottom: 12, borderLeft: "4px solid transparent", borderImage: `linear-gradient(180deg, ${c.primary}, ${c.accent}) 1`, background: c.nestedBg, borderRadius: 8, padding: 4 }}>
            {displayResult ? <AIConclusion result={displayResult} /> : <SkeletonAIConclusion />}
          </div>
        )}

        {/* Error */}
        {analysisError && !isAnalyzing && (
          <Alert
            message={`分析失败: ${analysisError}`}
            type="error"
            showIcon
            closable
            style={{ marginBottom: 16, borderRadius: 8 }}
          />
        )}

        {displayResult?.technical && (
          <Card
            size="small"
            className="pdf-avoid-break"
            style={{ ...cardStyle, marginBottom: 12, borderTop: `3px solid ${c.primary}`, boxShadow: `0 -1px 8px ${c.primary}4d` }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 12 }}>
              <div style={{ padding: "10px 12px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: c.textSecondary, marginBottom: 6 }}>技术结论</div>
                <div style={{ fontSize: 13, color: c.textSecondary, lineHeight: 1.8 }}>{displayResult.technical.summary}</div>
              </div>
              <div style={{ padding: "10px 12px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: c.textSecondary, marginBottom: 6 }}>趋势判断</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: c.textPrimary }}>{displayResult.technical.trend || "-"}</div>
              </div>
              <div style={{ padding: "10px 12px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: c.textSecondary, marginBottom: 6 }}>关键位</div>
                <div style={{ fontSize: 13, color: c.textSecondary, lineHeight: 1.8 }}>
                  支撑 {displayResult.technical.support_level?.toFixed(2) ?? "-"} / 压力 {displayResult.technical.resistance_level?.toFixed(2) ?? "-"}
                </div>
              </div>
            </div>
          </Card>
        )}

        {intradayData?.items?.length ? (
          <Card
            size="small"
            className="pdf-avoid-break"
            title={<span style={{ fontWeight: 700, color: c.textPrimary }}>最新分时图</span>}
            extra={<span style={{ fontSize: 12, color: c.textSecondary }}>当日分时走势与成交量</span>}
            style={{ ...cardStyle, marginBottom: 14, borderTop: `3px solid ${c.primary}`, boxShadow: `0 -1px 8px ${c.primary}4d` }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 12 }}>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10 }}>
                <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>最新价</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: c.textPrimary }}>{intradayData.items[intradayData.items.length - 1]?.price?.toFixed(2) ?? "-"}</div>
              </div>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10 }}>
                <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>分时涨跌幅</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: (intradayData.items[intradayData.items.length - 1]?.change_pct ?? 0) >= 0 ? c.up : c.down }}>
                  {intradayData.items[intradayData.items.length - 1]?.change_pct != null ? `${intradayData.items[intradayData.items.length - 1].change_pct! > 0 ? "+" : ""}${intradayData.items[intradayData.items.length - 1].change_pct!.toFixed(2)}%` : "-"}
                </div>
              </div>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: c.elevatedBg, border: `1px solid ${c.border}`, borderRadius: 10 }}>
                <div style={{ color: c.textSecondary, fontSize: 12, marginBottom: 6 }}>昨收价</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: c.textPrimary }}>{intradayData.prev_close != null ? intradayData.prev_close.toFixed(2) : "-"}</div>
              </div>
            </div>
            <IntradayChart data={intradayData.items} prevClose={intradayData.prev_close} />
          </Card>
        ) : pageLoading ? (
          <Card
            size="small"
            className="pdf-avoid-break"
            title={<span style={{ fontWeight: 700, color: c.textPrimary }}>最新分时图</span>}
            style={{ ...cardStyle, marginBottom: 14, borderTop: `3px solid ${c.primary}`, boxShadow: `0 -1px 8px ${c.primary}4d` }}
            styles={{ body: { padding: "32px 16px", textAlign: "center" } }}
          >
            <Spin />
          </Card>
        ) : null}

        {/* K-line Chart */}
        <Card
          size="small"
          className="pdf-avoid-break"
          title={<span style={{ fontWeight: 700, color: c.textPrimary }}>K线图</span>}
          style={{ ...cardStyle, marginBottom: 14, borderTop: `3px solid ${c.primary}`, boxShadow: `0 -1px 8px ${c.primary}4d` }}
          extra={
            <Space size={10} style={{ background: c.nestedBg, border: `1px solid ${c.border}`, borderRadius: 10, padding: "6px 8px" }}>
              <Segmented
                options={[
                  { label: "日K", value: "daily" },
                  { label: "周K", value: "weekly" },
                  { label: "月K", value: "monthly" },
                ]}
                value={period}
                onChange={handlePeriodChange}
              />
              <Segmented
                options={[
                  { label: "前复权", value: "qfq" },
                  { label: "后复权", value: "hfq" },
                  { label: "不复权", value: "" },
                ]}
                value={adjust}
                onChange={handleAdjustChange}
              />
            </Space>
          }
        >
          {pageLoading ? <Spin /> : klineData && <KlineChart data={klineData.items} />}
        </Card>

        {/* Indicator sub-charts */}
        {code && !pageLoading && (
          <Card size="small" style={{ ...cardStyle, marginTop: 16 }} styles={{ body: { padding: "12px 16px" } }}>
            <IndicatorSubCharts code={code} />
          </Card>
        )}

        {/* Tabs */}
        <Card
          size="small"
          style={{ ...cardStyle, borderTop: `3px solid ${c.primary}`, boxShadow: `0 -1px 8px ${c.primary}4d` }}
          styles={{ body: { padding: "10px 16px 14px", background: c.nestedBg, borderRadius: 8 } }}
        >
          {isExportingPdf ? (
            <div>
              {exportPanelContent}
            </div>
          ) : (
            <Tabs
              items={panelItems}
              activeKey={activePanelKey}
              onChange={setActivePanelKey}
              size="large"
              tabBarStyle={{ marginBottom: 18, borderBottom: `1px solid ${c.border}`, fontWeight: 700 }}
            />
          )}
        </Card>
      </div>
    </>
  );
}
