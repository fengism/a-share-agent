import { useState, type CSSProperties, type ReactNode } from "react";
import {
  DownloadOutlined,
  FileSearchOutlined,
  HistoryOutlined,
  PlusOutlined,
  SendOutlined,
  StarFilled,
  StopOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Tag, Tooltip, Typography } from "antd";
import PushModal from "../../components/PushModal";
import { useColors, useStyles } from "../../theme/hooks";
import type { AnalysisPageData, AnalysisResult, IntradayData, PushRequest } from "../../types/stock";
import { formatAmountWanYi, formatMarketCap } from "../../utils/format";

const { Title } = Typography;

function StockMetric({
  label,
  value,
  emphasis = false,
  color,
}: {
  label: string;
  value: ReactNode;
  emphasis?: boolean;
  color?: string;
}) {
  return (
    <div
      className={`analysis-header-card__metric${emphasis ? " is-emphasis" : ""}`}
      style={{ "--analysis-metric-color": color } as CSSProperties}
    >
      <span>{label}</span>
      <strong className="financial-num">{value}</strong>
    </div>
  );
}

interface AnalysisHeaderCardProps {
  code?: string;
  pageData?: AnalysisPageData;
  intradayData?: IntradayData | null;
  result: AnalysisResult | null | undefined;
  analysisDate?: string;
  isAnalyzing: boolean;
  isCancelling?: boolean;
  isPushing: boolean;
  isWatched: boolean;
  isWatchlistPending: boolean;
  onToggleWatchlist: () => void;
  onAnalyze: () => void;
  onCancel: () => void;
  onExportPdf: () => void;
  onShowHistory: () => void;
  onOpenResearchReport: () => void;
  onPush: (request: PushRequest) => Promise<boolean>;
}

export default function AnalysisHeaderCard({
  code,
  pageData,
  intradayData,
  result,
  analysisDate,
  isAnalyzing,
  isCancelling = false,
  isPushing,
  isWatched,
  isWatchlistPending,
  onToggleWatchlist,
  onAnalyze,
  onCancel,
  onExportPdf,
  onShowHistory,
  onOpenResearchReport,
  onPush,
}: AnalysisHeaderCardProps) {
  const colors = useColors();
  const { cardStyle, gradientHeaderStyle } = useStyles();
  const [pushModalOpen, setPushModalOpen] = useState(false);
  const info = pageData?.stock_info;
  const valuation = pageData?.valuation;
  const klineItems = pageData?.kline?.items ?? [];
  const latestKline = klineItems.length > 0 ? klineItems[klineItems.length - 1] : null;
  const liveIntradayItems = intradayData?.items ?? [];
  const activeIntraday = liveIntradayItems.length > 0 ? intradayData : pageData?.intraday;
  const activeIntradayItems = activeIntraday?.items ?? [];
  const latestIntraday = activeIntradayItems.length > 0
    ? activeIntradayItems[activeIntradayItems.length - 1]
    : null;
  const latestPrice = latestIntraday?.price ?? latestKline?.close ?? null;
  const latestChangePct = latestIntraday?.change_pct
    ?? (
      latestIntraday?.price != null && activeIntraday?.prev_close
        ? (latestIntraday.price - activeIntraday.prev_close) / activeIntraday.prev_close * 100
        : latestKline?.change_pct
    )
    ?? null;
  const marketCap = info?.market_cap ?? null;
  const peTtm = typeof valuation?.pe_ttm === "number" ? valuation.pe_ttm : null;
  const pb = typeof valuation?.pb === "number" ? valuation.pb : null;
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
      style={{ ...cardStyle, ...gradientHeaderStyle }}
    >
      <div className="analysis-header-card__top">
        <div className="analysis-header-card__identity">
          <div className="analysis-header-card__title-row">
            <Title level={3} style={{ margin: 0, color: colors.textPrimary }}>
              {info?.name || code}
            </Title>
            <span className="analysis-header-card__code">{info?.code}</span>
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
              aria-label="研究历史"
              onClick={onShowHistory}
            >
              研究历史
            </Button>
            {result ? (
              <Button
                type="link"
                size="small"
                icon={<FileSearchOutlined />}
                className="pdf-hide"
                aria-label="打开报告模式"
                onClick={onOpenResearchReport}
              >
                报告模式
              </Button>
            ) : null}
          </div>
          <div className="analysis-header-card__meta">
            {info?.exchange_industry && (
              <span>交易所行业 · {info.exchange_industry}</span>
            )}
            {(info?.first_industry || info?.second_industry || info?.third_industry) && (
              <span>
                申万行业 · {[info.first_industry?.name, info.second_industry?.name, info.third_industry?.name].filter(Boolean).join(" / ")}
              </span>
            )}
            {info?.listing_date && (
              <span>上市日期 {info.listing_date}</span>
            )}
          </div>
          {info?.concepts && info.concepts.length > 0 && (
            <div className="analysis-header-card__concepts" style={{ marginTop: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
              {info.concepts.slice(0, 6).map((c) => (
                <Tag key={c.code || c.name} style={{ margin: 0, fontSize: "var(--c-font-xs)" }}>{c.name}</Tag>
              ))}
              {info.concepts.length > 6 && (
                <Tooltip title={info.concepts.slice(6).map((c) => c.name).join(" · ")}>
                  <Tag style={{ margin: 0, fontSize: "var(--c-font-xs)", cursor: "pointer" }}>+{info.concepts.length - 6}</Tag>
                </Tooltip>
              )}
            </div>
          )}
        </div>
        <div className="analysis-header-card__actions pdf-hide">
          <Button
            icon={<DownloadOutlined />}
            onClick={onExportPdf}
            disabled={!result}
          >
            导出 PDF
          </Button>
          <Button
            icon={<SendOutlined />}
            aria-label="推送"
            onClick={() => setPushModalOpen(true)}
            disabled={!result}
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
              danger
              icon={<StopOutlined />}
              loading={isCancelling}
              disabled={isCancelling}
              aria-label={isCancelling ? "正在停止研究" : "停止研究"}
              onClick={onCancel}
            >
              {isCancelling ? "正在停止" : "停止研究"}
            </Button>
          ) : (
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              aria-label={result ? "更新研究" : "开始研究"}
              onClick={onAnalyze}
            >
              {result ? "更新研究" : "开始研究"}
            </Button>
          )}
        </div>
      </div>

      <div className="analysis-header-card__metrics" aria-label="股票行情摘要">
        <StockMetric
          label="最新股价"
          value={latestPrice != null ? `¥${latestPrice.toFixed(2)}` : "-"}
          emphasis
          color={changeColor}
        />
        <StockMetric
          label="单日涨跌"
          value={latestChangePct != null ? `${latestChangePct > 0 ? "+" : ""}${latestChangePct.toFixed(2)}%` : "-"}
          emphasis
          color={changeColor}
        />
        <StockMetric label="市盈率 TTM" value={peTtm != null ? peTtm.toFixed(2) : "-"} />
        <StockMetric label="市净率" value={pb != null ? pb.toFixed(2) : "-"} />
        <StockMetric label="成交额" value={formatAmountWanYi(latestKline?.amount)} />
        <StockMetric
          label="换手率"
          value={
            latestKline?.turnover_pct != null
              ? `${latestKline.turnover_pct.toFixed(2)}%`
              : info?.turnover_pct != null
                ? `${info.turnover_pct.toFixed(2)}%`
                : "-"
          }
        />
        <StockMetric label="总市值" value={formatMarketCap(marketCap)} />
      </div>
    </div>
  );
}
