import { useParams } from "react-router-dom";
import { Spin, Card, Segmented, Space, Typography, Row, Col, Tabs, Button, Alert, message } from "antd";
import { DownloadOutlined, ThunderboltOutlined, StopOutlined } from "@ant-design/icons";
import html2canvas from "html2canvas";
import jsPDF from "jspdf";
import { useStockInfo, useKlineData, useIntradayData, useAnalysisResult, useValuation, usePush } from "../../api/queries";
import PushModal from "../../components/PushModal";
import type { PushRequest } from "../../types/stock";
import { useStyles } from "../../styles/ui";;
import { streamAnalysis } from "../../api/sse";
import type { AnalysisProgress, AnalysisStage } from "../../api/sse";
import KlineChart from "../../charts/KlineChart";
import IntradayChart from "../../charts/IntradayChart";
import FundamentalPanel from "./FundamentalPanel";
import TechnicalPanel from "./TechnicalPanel";
import SentimentPanel from "./SentimentPanel";
import ValuationPanel from "./ValuationPanel";
import AIConclusion from "./AIConclusion";
import AnalysisProgressSteps from "./AnalysisProgressSteps";
import SkeletonAIConclusion from "./SkeletonAIConclusion";
import { useAnalysisStore } from "../../store/analysisStore";
import { useState, useEffect, useCallback, useRef } from "react";
import type { AnalysisResult } from "../../types/stock";

const { Title } = Typography;

function formatMarketCap(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(2)}万亿`;
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  return value.toFixed(0);
}

function formatAmountWanYi(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  return `${(value / 1e4).toFixed(2)}万`;
}

export default function Analysis() {
  const { cardStyle, gradientHeaderStyle, pageContainerStyle, sectionCardBodyStyle } = useStyles();
  const { code } = useParams<{ code: string }>();
  const [messageApi, contextHolder] = message.useMessage();
  const exportRef = useRef<HTMLDivElement>(null);
  const [isExportingPdf, setIsExportingPdf] = useState(false);
  const { data: info, isLoading: infoLoading } = useStockInfo(code || "");
  const { data: valuation } = useValuation(code || "");
  const { data: intradayData, isLoading: intradayLoading } = useIntradayData(code || "");
  const [period, setPeriod] = useState<string>("daily");
  const [adjust, setAdjust] = useState<string>("qfq");
  const [activePanelKey, setActivePanelKey] = useState<string>("fundamental");
  const { data: klineData, isLoading: klineLoading } = useKlineData(code || "", period, adjust);
  const { data: cachedResult } = useAnalysisResult(code || "");
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

  const displayResult = analysisResult || cachedResult;
  const latestKline = klineData?.items?.length ? klineData.items[klineData.items.length - 1] : null;

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
      const canvas = await html2canvas(exportRef.current, {
        scale: 2,
        useCORS: true,
        backgroundColor: "#0b1120",
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
  }, [code, messageApi]);

  if (infoLoading) return <Spin size="large" style={{ display: "block", margin: "100px auto" }} />;

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
  ];

  const exportPanelContent = isExportingPdf
    ? panelItems.map((item) => (
        <div key={item.key} className="pdf-section-block" style={{ marginTop: item.key === "fundamental" ? 0 : 20 }}>
          <div className="pdf-section-title" style={{ fontSize: 15, fontWeight: 700, color: "#e5e7eb", marginBottom: 12 }}>
            {item.label}
          </div>
          {item.children}
        </div>
      ))
    : null;

  return (
    <>
      {contextHolder}
      <div ref={exportRef} style={pageContainerStyle} className={isExportingPdf ? "pdf-exporting" : undefined}>
        <style>{`
          .terminal-table-row td {
            font-size: 12px;
            color: #9ca3af;
            padding-top: 8px !important;
            padding-bottom: 8px !important;
            border-bottom: 1px solid #1e293b !important;
          }
          .ant-tabs .ant-tabs-tab {
            padding: 10px 14px;
            border-radius: 8px 8px 0 0;
            color: #9ca3af;
            transition: all 0.2s ease;
          }
          .ant-tabs .ant-tabs-tab:hover {
            color: #3b82f6;
            background: #1a2332;
          }
          .ant-tabs .ant-tabs-tab.ant-tabs-tab-active {
            background: #0f1720;
          }
          .ant-tabs .ant-tabs-tab.ant-tabs-tab-active .ant-tabs-tab-btn {
            color: #3b82f6;
            font-weight: 700;
          }
          .ant-tabs .ant-tabs-ink-bar {
            background: #3b82f6;
            height: 3px;
            border-radius: 999px;
          }
          .pdf-exporting .pdf-hide,
          .pdf-exporting .ant-btn,
          .pdf-exporting .ant-btn-icon,
          .pdf-exporting .ant-segmented,
          .pdf-exporting .ant-tabs-nav,
          .pdf-exporting .ant-alert,
          .pdf-exporting .ant-message,
          .pdf-exporting .ant-card-extra,
          .pdf-exporting .ant-spin,
          .pdf-exporting .ant-spin-spinning {
            display: none !important;
          }
          .pdf-exporting .ant-card {
            box-shadow: none !important;
            border-color: #1e293b !important;
            background: #111827 !important;
          }
          .pdf-exporting {
            max-width: 1100px !important;
            padding: 0 !important;
            background: #0b1120 !important;
            color: #e5e7eb !important;
          }
          .pdf-exporting .ant-card-head {
            min-height: 40px !important;
            padding-inline: 16px !important;
            background: #111827 !important;
            border-bottom-color: #1e293b !important;
          }
          .pdf-exporting .ant-card-body {
            padding-top: 14px !important;
            padding-bottom: 14px !important;
          }
          .pdf-exporting .ant-tag {
            border-color: #1e293b !important;
            background: #1a2332 !important;
            color: #e5e7eb !important;
          }
          .pdf-exporting .pdf-metric-card {
            min-height: 72px !important;
            padding: 10px 12px !important;
          }
          .pdf-exporting .pdf-metric-card-primary {
            min-height: 84px !important;
            padding: 12px 14px !important;
          }
          .pdf-exporting .pdf-section-title {
            padding-bottom: 6px;
            border-bottom: 1px solid #1e293b;
          }
          .pdf-exporting .pdf-list-item {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .pdf-exporting .ant-list-item {
            break-inside: avoid;
            page-break-inside: avoid;
          }
          .pdf-exporting .ant-row,
          .pdf-exporting .ant-col,
          .pdf-exporting .ant-table-wrapper,
          .pdf-exporting .pdf-section-block,
          .pdf-exporting .pdf-avoid-break {
            break-inside: avoid;
            page-break-inside: avoid;
          }
        `}</style>
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
                <Title level={3} style={{ margin: 0, color: "#e5e7eb", letterSpacing: 0.2 }}>
                  {info?.name || code}
                </Title>
                <span style={{ fontSize: 14, color: "#9ca3af", fontWeight: 500 }}>
                  {info?.code}
                </span>
              </div>
              <div style={{ marginTop: 8, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
                {info?.first_industry && (
                  <span style={{ fontSize: 12, color: "#9ca3af", background: "#1a2332", border: "1px solid #1e293b", padding: "3px 10px", borderRadius: 999 }}>
                    {info.first_industry.name}
                  </span>
                )}
                {info?.second_industry && (
                  <span style={{ fontSize: 12, color: "#9ca3af", background: "#1a2332", border: "1px solid #1e293b", padding: "3px 10px", borderRadius: 999 }}>
                    {info.second_industry.name}
                  </span>
                )}
                {priceSnapshot.listingDate && (
                  <span style={{ fontSize: 12, color: "#9ca3af" }}>上市日期 {priceSnapshot.listingDate}</span>
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
                  style={{ borderRadius: 8, height: 42, paddingInline: 24, fontWeight: 600, background: "#3b82f6" }}
                >
                  智能分析
                </Button>
              )}
            </Space>
          </div>

          <div style={{ display: "grid", gap: 14 }}>
            <Row gutter={[14, 14]} align="stretch">
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: "linear-gradient(135deg, #1a0f0f, #2d1518)", border: "1px solid #ead7d5", borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>最新股价</div>
                  <div style={{ fontSize: 32, fontWeight: 800, color: latestKline ? ((latestKline.change_pct ?? 0) > 0 ? "#ef4444" : (latestKline.change_pct ?? 0) < 0 ? "#22c55e" : "#e5e7eb") : "#e5e7eb", letterSpacing: 0.2 }}>
                    {priceSnapshot.latestPrice != null ? `¥${priceSnapshot.latestPrice.toFixed(2)}` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: latestKline && (latestKline.change_pct ?? 0) < 0 ? "linear-gradient(135deg, #0f1a14, #152d1d)" : "linear-gradient(135deg, #1a0f0f, #2d1518)", border: `1px solid ${latestKline && (latestKline.change_pct ?? 0) < 0 ? "#152d1d" : "#2d1518"}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>单日涨跌幅</div>
                  <div style={{ fontSize: 26, fontWeight: 800, color: latestKline ? ((latestKline.change_pct ?? 0) > 0 ? "#ef4444" : (latestKline.change_pct ?? 0) < 0 ? "#22c55e" : "#e5e7eb") : "#e5e7eb" }}>
                    {priceSnapshot.latestChangePct != null ? `${priceSnapshot.latestChangePct > 0 ? "+" : ""}${priceSnapshot.latestChangePct.toFixed(2)}%` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? "linear-gradient(135deg, #1a0f0f, #2d1518)" : "#1a2332", border: `1px solid ${valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? "#2d1518" : "#1e293b"}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>市盈率(TTM)</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: valuationSnapshot.peTtm != null && valuationSnapshot.peTtm > 30 ? "#ef4444" : "#e5e7eb" }}>{valuationSnapshot.peTtm != null ? valuationSnapshot.peTtm.toFixed(2) : "-"}</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div style={{ padding: "14px 16px", background: valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? "linear-gradient(135deg, #1a0f0f, #2d1518)" : "#1a2332", border: `1px solid ${valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? "#2d1518" : "#1e293b"}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>市净率</div>
                  <div style={{ fontSize: 22, fontWeight: 800, color: valuationSnapshot.pb != null && valuationSnapshot.pb > 3 ? "#ef4444" : "#e5e7eb" }}>{valuationSnapshot.pb != null ? valuationSnapshot.pb.toFixed(2) : "-"}</div>
                </div>
              </Col>
            </Row>
            <Row gutter={[14, 14]} align="stretch">
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>成交额</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb" }}>{formatAmountWanYi(latestKline?.amount)}</div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>换手率</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb" }}>
                    {latestKline?.turnover_pct != null ? `${latestKline.turnover_pct.toFixed(2)}%` : info?.turnover_pct != null ? `${info.turnover_pct.toFixed(2)}%` : "-"}
                  </div>
                </div>
              </Col>
              <Col xs={12} md={6}>
                <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
                  <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>总市值</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb" }}>{formatMarketCap(priceSnapshot.marketCap)}</div>
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
          <div className="pdf-avoid-break" style={{ marginBottom: 12, borderLeft: "4px solid transparent", borderImage: "linear-gradient(180deg, #3b82f6, #6366f1) 1", background: "#0f1720", borderRadius: 8, padding: 4 }}>
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
            style={{ ...cardStyle, marginBottom: 12, borderTop: "3px solid #3b82f6",
boxShadow: "0 -1px 8px rgba(59,130,246,0.3)" }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr 1fr", gap: 12 }}>
              <div style={{ padding: "10px 12px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>技术结论</div>
                <div style={{ fontSize: 13, color: "#9ca3af", lineHeight: 1.8 }}>{displayResult.technical.summary}</div>
              </div>
              <div style={{ padding: "10px 12px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>趋势判断</div>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#e5e7eb" }}>{displayResult.technical.trend || "-"}</div>
              </div>
              <div style={{ padding: "10px 12px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 8 }}>
                <div style={{ fontSize: 12, color: "#9ca3af", marginBottom: 6 }}>关键位</div>
                <div style={{ fontSize: 13, color: "#9ca3af", lineHeight: 1.8 }}>
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
            title={<span style={{ fontWeight: 700, color: "#e5e7eb" }}>最新分时图</span>}
            extra={<span style={{ fontSize: 12, color: "#9ca3af" }}>当日分时走势与成交量</span>}
            style={{ ...cardStyle, marginBottom: 14, borderTop: "3px solid #3b82f6",
boxShadow: "0 -1px 8px rgba(59,130,246,0.3)" }}
            styles={{ body: { padding: "12px 16px" } }}
          >
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 12 }}>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10 }}>
                <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>最新价</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#e5e7eb" }}>{intradayData.items[intradayData.items.length - 1]?.price?.toFixed(2) ?? "-"}</div>
              </div>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10 }}>
                <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>分时涨跌幅</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: (intradayData.items[intradayData.items.length - 1]?.change_pct ?? 0) >= 0 ? "#ef4444" : "#22c55e" }}>
                  {intradayData.items[intradayData.items.length - 1]?.change_pct != null ? `${intradayData.items[intradayData.items.length - 1].change_pct! > 0 ? "+" : ""}${intradayData.items[intradayData.items.length - 1].change_pct!.toFixed(2)}%` : "-"}
                </div>
              </div>
              <div className="pdf-metric-card" style={{ padding: "12px 14px", background: "#1a2332", border: "1px solid #1e293b", borderRadius: 10 }}>
                <div style={{ color: "#9ca3af", fontSize: 12, marginBottom: 6 }}>昨收价</div>
                <div style={{ fontSize: 20, fontWeight: 700, color: "#e5e7eb" }}>{intradayData.prev_close != null ? intradayData.prev_close.toFixed(2) : "-"}</div>
              </div>
            </div>
            <IntradayChart data={intradayData.items} prevClose={intradayData.prev_close} />
          </Card>
        ) : intradayLoading ? (
          <Card
            size="small"
            className="pdf-avoid-break"
            title={<span style={{ fontWeight: 700, color: "#e5e7eb" }}>最新分时图</span>}
            style={{ ...cardStyle, marginBottom: 14, borderTop: "3px solid #3b82f6",
boxShadow: "0 -1px 8px rgba(59,130,246,0.3)" }}
            styles={{ body: { padding: "32px 16px", textAlign: "center" } }}
          >
            <Spin />
          </Card>
        ) : null}

        {/* K-line Chart */}
        <Card
          size="small"
          className="pdf-avoid-break"
          title={<span style={{ fontWeight: 700, color: "#e5e7eb" }}>K线图</span>}
          style={{ ...cardStyle, marginBottom: 14, borderTop: "3px solid #3b82f6",
boxShadow: "0 -1px 8px rgba(59,130,246,0.3)" }}
          extra={
            <Space size={10} style={{ background: "#0f1720", border: "1px solid #1e293b", borderRadius: 10, padding: "6px 8px" }}>
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
          {klineLoading ? <Spin /> : klineData && <KlineChart data={klineData.items} />}
        </Card>

        {/* Tabs */}
        <Card
          size="small"
          style={{ ...cardStyle, borderTop: "3px solid #3b82f6",
boxShadow: "0 -1px 8px rgba(59,130,246,0.3)" }}
          styles={{ body: { padding: "10px 16px 14px", background: "#0f1720", borderRadius: 8 } }}
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
              tabBarStyle={{ marginBottom: 18, borderBottom: "1px solid #1e293b", fontWeight: 700 }}
            />
          )}
        </Card>
      </div>
    </>
  );
}
