import { useState } from "react";
import { DownloadOutlined, StopOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { Button, Col, Row, Typography } from "antd";
import PushModal from "../../components/PushModal";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisPageData, AnalysisResult, PushRequest } from "../../types/stock";
import { formatAmountWanYi, formatMarketCap } from "../../utils/format";

const { Title } = Typography;

interface AnalysisHeaderCardProps {
  code?: string;
  pageData?: AnalysisPageData;
  result: AnalysisResult | null | undefined;
  isAnalyzing: boolean;
  isPushing: boolean;
  onAnalyze: () => void;
  onCancel: () => void;
  onExportPdf: () => void;
  onPush: (request: PushRequest) => Promise<void>;
}

export default function AnalysisHeaderCard({
  code,
  pageData,
  result,
  isAnalyzing,
  isPushing,
  onAnalyze,
  onCancel,
  onExportPdf,
  onPush,
}: AnalysisHeaderCardProps) {
  const colors = useColors();
  const { cardStyle, gradientHeaderStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const info = pageData?.stock_info;
  const valuation = pageData?.valuation;
  const klineItems = pageData?.kline?.items ?? [];
  const latestKline = klineItems.length > 0 ? klineItems[klineItems.length - 1] : null;
  const latestPrice = latestKline?.close ?? null;
  const latestChangePct = latestKline?.change_pct ?? null;
  const marketCap = info?.market_cap ?? null;
  const peTtm = typeof valuation?.pe_ttm === "number" ? valuation.pe_ttm : null;
  const pb = typeof valuation?.pb === "number" ? valuation.pb : null;
  const isDown = (latestChangePct ?? 0) < 0;
  const changeColor = latestChangePct == null
    ? colors.textPrimary
    : latestChangePct > 0
      ? colors.up
      : latestChangePct < 0
        ? colors.down
        : colors.textPrimary;

  const handlePush = async (request: PushRequest) => {
    await onPush(request);
    setPushModalOpen(false);
  };

  return (
    <div style={{ ...cardStyle, ...gradientHeaderStyle, marginBottom: 20, padding: "22px 24px 18px" }}>
      <div
        style={{
          display: "flex",
          flexDirection: isNarrow ? "column" : "row",
          justifyContent: "space-between",
          alignItems: isNarrow ? "stretch" : "flex-start",
          gap: 16,
          marginBottom: 14,
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10, flexWrap: "wrap" }}>
            <Title level={3} style={{ margin: 0, color: colors.textPrimary, letterSpacing: 0.2 }}>
              {info?.name || code}
            </Title>
            <span style={{ fontSize: 14, color: colors.textSecondary, fontWeight: 500 }}>{info?.code}</span>
          </div>
          <div style={{ marginTop: 8, display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
            {info?.first_industry && (
              <span style={{ fontSize: 12, color: colors.textSecondary, background: colors.elevatedBg, border: `1px solid ${colors.border}`, padding: "3px 10px", borderRadius: 999 }}>
                {info.first_industry.name}
              </span>
            )}
            {info?.second_industry && (
              <span style={{ fontSize: 12, color: colors.textSecondary, background: colors.elevatedBg, border: `1px solid ${colors.border}`, padding: "3px 10px", borderRadius: 999 }}>
                {info.second_industry.name}
              </span>
            )}
            {info?.listing_date && (
              <span style={{ fontSize: 12, color: colors.textSecondary }}>上市日期 {info.listing_date}</span>
            )}
          </div>
        </div>
        <div
          className="pdf-hide"
          style={{
            display: "grid",
            gridTemplateColumns: isNarrow ? "repeat(2, minmax(0, 1fr))" : "repeat(3, max-content)",
            gap: 10,
            width: isNarrow ? "100%" : undefined,
          }}
        >
          <Button
            block={isNarrow}
            size="large"
            icon={<DownloadOutlined />}
            onClick={onExportPdf}
            disabled={!result}
            style={{ borderRadius: 8, height: 42, fontWeight: 600 }}
          >
            导出 PDF
          </Button>
          <Button
            block={isNarrow}
            size="large"
            onClick={() => setPushModalOpen(true)}
            disabled={!result}
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
            loading={isPushing}
          />
          {isAnalyzing ? (
            <Button
              block={isNarrow}
              size="large"
              danger
              icon={<StopOutlined />}
              onClick={onCancel}
              style={{ borderRadius: 8, height: 42, fontWeight: 600, gridColumn: isNarrow ? "1 / -1" : undefined }}
            >
              取消分析
            </Button>
          ) : (
            <Button
              block={isNarrow}
              type="primary"
              size="large"
              icon={<ThunderboltOutlined />}
              onClick={onAnalyze}
              style={{ borderRadius: 8, height: 42, paddingInline: 24, fontWeight: 600, gridColumn: isNarrow ? "1 / -1" : undefined }}
            >
              智能分析
            </Button>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gap: 14 }}>
        <Row gutter={[14, 14]} align="stretch">
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: isDown ? colors.downCardGradient : colors.upCardGradient, border: `1px solid ${isDown ? `${colors.down}40` : `${colors.up}40`}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>最新股价</div>
              <div style={{ fontSize: 32, fontWeight: 800, color: changeColor, letterSpacing: 0.2 }}>
                {latestPrice != null ? `¥${latestPrice.toFixed(2)}` : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: isDown ? colors.downCardGradient : colors.upCardGradient, border: `1px solid ${isDown ? `${colors.down}40` : `${colors.up}40`}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>单日涨跌幅</div>
              <div style={{ fontSize: 26, fontWeight: 800, color: changeColor }}>
                {latestChangePct != null ? `${latestChangePct > 0 ? "+" : ""}${latestChangePct.toFixed(2)}%` : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: "14px 16px", background: peTtm != null && peTtm > 30 ? colors.upCardGradient : colors.elevatedBg, border: `1px solid ${peTtm != null && peTtm > 30 ? `${colors.up}40` : colors.border}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>市盈率(TTM)</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: peTtm != null && peTtm > 30 ? colors.up : colors.textPrimary }}>
                {peTtm != null ? peTtm.toFixed(2) : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div style={{ padding: "14px 16px", background: pb != null && pb > 3 ? colors.upCardGradient : colors.elevatedBg, border: `1px solid ${pb != null && pb > 3 ? `${colors.up}40` : colors.border}`, borderRadius: 10, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>市净率</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: pb != null && pb > 3 ? colors.up : colors.textPrimary }}>
                {pb != null ? pb.toFixed(2) : "-"}
              </div>
            </div>
          </Col>
        </Row>
        <Row gutter={[14, 14]} align="stretch">
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>成交额</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary }}>{formatAmountWanYi(latestKline?.amount)}</div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>换手率</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary }}>
                {latestKline?.turnover_pct != null
                  ? `${latestKline.turnover_pct.toFixed(2)}%`
                  : info?.turnover_pct != null
                    ? `${info.turnover_pct.toFixed(2)}%`
                    : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: "12px 14px", background: colors.elevatedBg, border: `1px solid ${colors.border}`, borderRadius: 10, minHeight: 82, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: 12, marginBottom: 6 }}>总市值</div>
              <div style={{ fontSize: 18, fontWeight: 700, color: colors.textPrimary }}>{formatMarketCap(marketCap)}</div>
            </div>
          </Col>
        </Row>
      </div>
    </div>
  );
}
