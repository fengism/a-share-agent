import { useState } from "react";
import {
  DownloadOutlined,
  HistoryOutlined,
  PlusOutlined,
  StarFilled,
  StopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Col, Row, Typography } from "antd";
import PushModal from "../../components/PushModal";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import type { AnalysisPageData, AnalysisResult, PushRequest } from "../../types/stock";
import { formatAmountWanYi, formatMarketCap } from "../../utils/format";

const { Title } = Typography;

interface AnalysisHeaderCardProps {
  code?: string;
  pageData?: AnalysisPageData;
  result: AnalysisResult | null | undefined;
  analysisDate?: string;
  isAnalyzing: boolean;
  isPushing: boolean;
  isWatched: boolean;
  isWatchlistPending: boolean;
  onToggleWatchlist: () => void;
  onAnalyze: () => void;
  onCancel: () => void;
  onExportPdf: () => void;
  onShowHistory: () => void;
  onPush: (request: PushRequest) => Promise<boolean>;
}

export default function AnalysisHeaderCard({
  code,
  pageData,
  result,
  analysisDate,
  isAnalyzing,
  isPushing,
  isWatched,
  isWatchlistPending,
  onToggleWatchlist,
  onAnalyze,
  onCancel,
  onExportPdf,
  onShowHistory,
  onPush,
}: AnalysisHeaderCardProps) {
  const colors = useColors();
  const t = useTokens();
  const { cardStyle, gradientHeaderStyle, rowGutter } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 1040px)");
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
    const succeeded = await onPush(request);
    if (succeeded) setPushModalOpen(false);
    return succeeded;
  };

  return (
    <div
      className="analysis-header-card"
      style={{ ...cardStyle, ...gradientHeaderStyle, padding: `${t.space[6]} ${t.space[6]} ${t.space[5]}` }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: isNarrow ? "column" : "row",
          justifyContent: "space-between",
          alignItems: isNarrow ? "stretch" : "flex-start",
          gap: t.space[4],
          marginBottom: t.space[4],
        }}
      >
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: t.space[3], flexWrap: "wrap" }}>
            <Title level={3} style={{ margin: 0, color: colors.textPrimary, letterSpacing: 0.2 }}>
              {info?.name || code}
            </Title>
            <span style={{ fontSize: t.font.base, color: colors.textSecondary, fontWeight: Number(t.weight.medium) }}>{info?.code}</span>
            <Button
              type={isWatched ? "default" : "text"}
              size="small"
              icon={isWatched ? <StarFilled /> : <PlusOutlined />}
              className="pdf-hide"
              aria-label={isWatched ? "移出自选" : "加入自选"}
              loading={isWatchlistPending}
              onClick={onToggleWatchlist}
              style={{ color: isWatched ? colors.warning : colors.primary }}
            >
              {isWatched ? "已自选" : "加入自选"}
            </Button>
            <Button
              type="link"
              size="small"
              icon={<HistoryOutlined />}
              className="pdf-hide"
              aria-label="分析历史"
              onClick={onShowHistory}
              style={{ paddingInline: 0 }}
            >
              分析历史
            </Button>
          </div>
          <div style={{ marginTop: t.space[2], display: "flex", gap: t.space[3], flexWrap: "wrap", alignItems: "center" }}>
            {info?.exchange_industry && (
              <span style={{ fontSize: t.font.sm, color: colors.textSecondary, background: colors.hoverBg, border: `1px solid ${colors.border}`, padding: `${t.space[1]} ${t.space[3]}`, borderRadius: t.radius.pill }}>
                交易所行业 · {info.exchange_industry}
              </span>
            )}
            {info?.first_industry && (
              <span style={{ fontSize: t.font.sm, color: colors.textSecondary, background: colors.hoverBg, border: `1px solid ${colors.border}`, padding: `${t.space[1]} ${t.space[3]}`, borderRadius: t.radius.pill }}>
                {info.first_industry.name}
              </span>
            )}
            {info?.second_industry && (
              <span style={{ fontSize: t.font.sm, color: colors.textSecondary, background: colors.hoverBg, border: `1px solid ${colors.border}`, padding: `${t.space[1]} ${t.space[3]}`, borderRadius: t.radius.pill }}>
                {info.second_industry.name}
              </span>
            )}
            {info?.listing_date && (
              <span style={{ fontSize: t.font.sm, color: colors.textSecondary }}>上市日期 {info.listing_date}</span>
            )}
          </div>
        </div>
        <div
          className="pdf-hide"
          style={{
            display: "grid",
            gridTemplateColumns: isNarrow ? "repeat(2, minmax(0, 1fr))" : "repeat(3, max-content)",
            gap: t.space[3],
            width: isNarrow ? "100%" : undefined,
          }}
        >
          <Button
            block={isNarrow}
            size="large"
            icon={<DownloadOutlined />}
            onClick={onExportPdf}
            disabled={!result}
            style={{ borderRadius: t.radius.md, height: 42, fontWeight: Number(t.weight.semibold) }}
          >
            导出 PDF
          </Button>
          <Button
            block={isNarrow}
            size="large"
            onClick={() => setPushModalOpen(true)}
            disabled={!result}
            style={{ borderRadius: t.radius.md, height: 42, fontWeight: Number(t.weight.semibold) }}
          >
            推送
          </Button>
          <PushModal
            open={pushModalOpen}
            type="analysis"
            code={code}
            date={analysisDate}
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
              style={{ borderRadius: t.radius.md, height: 42, fontWeight: Number(t.weight.semibold), gridColumn: isNarrow ? "1 / -1" : undefined }}
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
              style={{ borderRadius: t.radius.md, height: 42, paddingInline: t.space[6], fontWeight: Number(t.weight.semibold), gridColumn: isNarrow ? "1 / -1" : undefined }}
            >
              智能分析
            </Button>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gap: t.space[4] }}>
        <Row gutter={[rowGutter, rowGutter]} align="stretch">
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: `${t.space[3]} ${t.space[4]}`, background: isDown ? colors.downCardGradient : colors.upCardGradient, border: `1px solid ${isDown ? `${colors.down}40` : `${colors.up}40`}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>最新股价</div>
              <div style={{ fontSize: t.font.display, fontWeight: Number(t.weight.heavy), color: changeColor, letterSpacing: 0.2 }}>
                {latestPrice != null ? `¥${latestPrice.toFixed(2)}` : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: `${t.space[3]} ${t.space[4]}`, background: isDown ? colors.downCardGradient : colors.upCardGradient, border: `1px solid ${isDown ? `${colors.down}40` : `${colors.up}40`}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>单日涨跌幅</div>
              <div style={{ fontSize: t.font["3xl"], fontWeight: Number(t.weight.heavy), color: changeColor }}>
                {latestChangePct != null ? `${latestChangePct > 0 ? "+" : ""}${latestChangePct.toFixed(2)}%` : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card pdf-metric-card-primary" style={{ padding: `${t.space[3]} ${t.space[4]}`, background: peTtm != null && peTtm > 30 ? colors.upCardGradient : colors.hoverBg, border: `1px solid ${peTtm != null && peTtm > 30 ? `${colors.up}40` : colors.border}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>市盈率(TTM)</div>
              <div style={{ fontSize: t.font["2xl"], fontWeight: Number(t.weight.heavy), color: peTtm != null && peTtm > 30 ? colors.up : colors.textPrimary }}>
                {peTtm != null ? peTtm.toFixed(2) : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div style={{ padding: `${t.space[3]} ${t.space[4]}`, background: pb != null && pb > 3 ? colors.upCardGradient : colors.hoverBg, border: `1px solid ${pb != null && pb > 3 ? `${colors.up}40` : colors.border}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>市净率</div>
              <div style={{ fontSize: t.font["2xl"], fontWeight: Number(t.weight.heavy), color: pb != null && pb > 3 ? colors.up : colors.textPrimary }}>
                {pb != null ? pb.toFixed(2) : "-"}
              </div>
            </div>
          </Col>
        </Row>
        <Row gutter={[rowGutter, rowGutter]} align="stretch">
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: `${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>成交额</div>
              <div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.bold), color: colors.textPrimary }}>{formatAmountWanYi(latestKline?.amount)}</div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: `${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>换手率</div>
              <div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.bold), color: colors.textPrimary }}>
                {latestKline?.turnover_pct != null
                  ? `${latestKline.turnover_pct.toFixed(2)}%`
                  : info?.turnover_pct != null
                    ? `${info.turnover_pct.toFixed(2)}%`
                    : "-"}
              </div>
            </div>
          </Col>
          <Col xs={12} md={6}>
            <div className="pdf-metric-card" style={{ padding: `${t.space[3]}`, background: colors.hoverBg, border: `1px solid ${colors.border}`, borderRadius: t.radius.lg, minHeight: 96, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
              <div style={{ color: colors.textSecondary, fontSize: t.font.sm, marginBottom: t.space[2] }}>总市值</div>
              <div style={{ fontSize: t.font.xl, fontWeight: Number(t.weight.bold), color: colors.textPrimary }}>{formatMarketCap(marketCap)}</div>
            </div>
          </Col>
        </Row>
      </div>
    </div>
  );
}
