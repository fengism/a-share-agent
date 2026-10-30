import { useState } from "react";
import {
  BankOutlined,
  CopyOutlined,
  FileSearchOutlined,
  GlobalOutlined,
  PlusOutlined,
  ShareAltOutlined,
  StarFilled,
  ThunderboltOutlined,
} from "@ant-design/icons";
import { Button, Card, Tag, Tooltip, Typography, message } from "antd";
import { useNavigate } from "react-router-dom";
import { useColors, useStyles } from "../../styles/ui";
import type { StockBasicInfo } from "../../types/stock";
import { formatNumberWithSeparators } from "../../utils/format";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";
import StockSnapshotModal from "./StockSnapshotModal";

const { Title, Text } = Typography;

export interface StockHeaderTapeData {
  open?: number | null;
  prevClose?: number | null;
  high?: number | null;
  low?: number | null;
  volume?: number | null;
  amount?: number | null;
  amplitude?: number | null;
  fiftyTwoWeekHigh?: number | null;
  fiftyTwoWeekLow?: number | null;
}

interface StockHeaderCardProps {
  info: Partial<StockBasicInfo> & { code: string; name: string };
  isWatched: boolean;
  isWatchlistPending: boolean;
  onToggleWatchlist: () => void;
  changePct?: number | null;
  market?: "cn" | "hk";
  englishName?: string | null;
  changeAmount?: number | null;
  showAnalysisButton?: boolean;
  tape?: StockHeaderTapeData | null;
}

export default function StockHeaderCard({
  info,
  isWatched,
  isWatchlistPending,
  onToggleWatchlist,
  changePct,
  market = "cn",
  englishName,
  changeAmount,
  showAnalysisButton,
  tape,
}: StockHeaderCardProps) {
  const navigate = useNavigate();
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [snapshotModalOpen, setSnapshotModalOpen] = useState(false);
  const isHK = market === "hk";
  const shouldShowAnalysis = showAnalysisButton ?? !isHK;
  const industry = info.second_industry?.name || info.first_industry?.name || info.exchange_industry;
  const fullIndustry = [info.first_industry?.name, info.second_industry?.name, info.third_industry?.name].filter(Boolean).join(" / ");
  const dotStateClass = changePct == null || changePct === 0 ? "" : changePct > 0 ? "is-up" : "is-down";

  const formatAmountText = (val?: number | null) => {
    if (val == null || !Number.isFinite(val)) return "-";
    if (Math.abs(val) >= 1e8) return `${(val / 1e8).toFixed(2)}亿`;
    if (Math.abs(val) >= 1e4) return `${(val / 1e4).toFixed(1)}万`;
    return formatNumberWithSeparators(val, 0);
  };

  const handleCopy = () => {
    const text = `${info.code} ${info.name || ""}`.trim();
    void navigator.clipboard.writeText(text);
    void message.success(`已复制 ${text}`);
  };

  return (
    <Card className="stock-header-card" style={cardStyle} styles={{ body: { padding: 0 } }}>
      <span className="stock-header-card__glow" aria-hidden="true" />
      <div className="stock-header-card__content">
        <div className="stock-header-card__identity">
          <div className="stock-header-card__eyebrow">
            <span aria-hidden="true" />
            {isHK ? "港股概览 · 香港联合交易所" : "公司概览"}
          </div>
          <div className="stock-header-card__title-row">
            <span className="stock-header-card__icon" aria-hidden="true">
              {isHK ? <GlobalOutlined /> : <BankOutlined />}
            </span>
            <Title level={2}>{info.name || info.code}</Title>
            <Text className="stock-header-card__code">{info.code}</Text>
            <Tooltip title="复制股票代码与名称">
              <Button
                type="text"
                size="small"
                icon={<CopyOutlined style={{ fontSize: 13 }} />}
                aria-label="复制股票代码"
                onClick={handleCopy}
                style={{ color: "var(--c-text-secondary)" }}
              />
            </Tooltip>
          </div>
          <div className="stock-header-card__tags">
            {isHK ? (
              <>
                <Tag color="blue">港股主板</Tag>
                {englishName && <Tag>{englishName}</Tag>}
                <Tag>港币 (HKD)</Tag>
                <Tag>T+0 回转交易</Tag>
              </>
            ) : (
              <>
                {industry ? (
                  <Tooltip title={fullIndustry ? `申万行业: ${fullIndustry}` : industry}>
                    <Tag>{industry}</Tag>
                  </Tooltip>
                ) : null}
                {(info.concepts ?? []).slice(0, 6).map((concept) => (
                  <Tag
                    key={concept.code || concept.name}
                    style={{ cursor: "pointer" }}
                    onClick={() => navigate(`/concept?concept=${encodeURIComponent(concept.name)}`)}
                  >
                    {concept.name}
                  </Tag>
                ))}
                {(info.concepts ?? []).length > 6 && (
                  <Tooltip title={(info.concepts ?? []).slice(6).map((c) => c.name).join(" · ")}>
                    <Tag style={{ cursor: "pointer" }}>+{(info.concepts ?? []).length - 6}</Tag>
                  </Tooltip>
                )}
              </>
            )}
          </div>
        </div>
        <div className="stock-header-card__quote">
          <Text type="secondary"><span className={`stock-header-card__quote-dot ${dotStateClass}`.trim()} />最新价</Text>
          <strong
            className={changePct == null || changePct === 0 ? "" : changePct > 0 ? "is-up" : "is-down"}
            style={{
              color: changePct == null || changePct === 0
                ? colors.textPrimary
                : changePct > 0
                ? colors.up
                : colors.down,
            }}
          >
            {info.current_price == null
              ? "-"
              : isHK
              ? `HK$${formatNumberWithSeparators(info.current_price)}`
              : `¥${info.current_price.toFixed(2)}`}
          </strong>
          <small>
            {isHK ? (
              changeAmount != null && changePct != null ? (
                <span style={{ color: changePct > 0 ? colors.up : colors.down }}>
                  {changePct > 0 ? "+" : ""}
                  {formatNumberWithSeparators(changeAmount)} (
                  {changePct > 0 ? "+" : ""}
                  {formatNumberWithSeparators(changePct)}%)
                </span>
              ) : (
                "新浪实时行情"
              )
            ) : changePct != null ? (
              <span style={{ color: changePct > 0 ? colors.up : changePct < 0 ? colors.down : colors.textSecondary }}>
                {changePct > 0 ? `+${changePct.toFixed(2)}%` : `${changePct.toFixed(2)}%`}
                {info.turnover_pct != null ? ` · 换手 ${info.turnover_pct.toFixed(2)}%` : ""}
              </span>
            ) : info.turnover_pct != null ? (
              `换手 ${info.turnover_pct.toFixed(2)}%`
            ) : (
              "行情快照"
            )}
          </small>
          {tape ? (
            <div className="stock-header-card__tape">
              <span title="今开盘">今开 {tape.open != null ? formatNumberWithSeparators(tape.open) : "-"}</span>
              <span title="最高价" style={{ color: tape.high != null && tape.prevClose != null && tape.high > tape.prevClose ? colors.up : undefined }}>
                最高 {tape.high != null ? formatNumberWithSeparators(tape.high) : "-"}
              </span>
              <span title="最低价" style={{ color: tape.low != null && tape.prevClose != null && tape.low < tape.prevClose ? colors.down : undefined }}>
                最低 {tape.low != null ? formatNumberWithSeparators(tape.low) : "-"}
              </span>
              {tape.amplitude != null ? (
                <span title="日内振幅">振幅 {tape.amplitude.toFixed(2)}%</span>
              ) : null}
              {tape.amount != null ? (
                <span title="成交总额">成交额 {formatAmountText(tape.amount)}</span>
              ) : null}
              {tape.fiftyTwoWeekLow != null && tape.fiftyTwoWeekHigh != null && tape.fiftyTwoWeekHigh > tape.fiftyTwoWeekLow ? (
                <Tooltip
                  title={`52周最高: ${formatNumberWithSeparators(tape.fiftyTwoWeekHigh)} · 52周最低: ${formatNumberWithSeparators(tape.fiftyTwoWeekLow)}${info.current_price != null ? ` · 当前位阶: ${Math.round(((info.current_price - tape.fiftyTwoWeekLow) / (tape.fiftyTwoWeekHigh - tape.fiftyTwoWeekLow)) * 100)}%` : ""}`}
                >
                  <span
                    className="stock-header-card__range52"
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "1px 6px",
                      background: "rgba(128, 128, 128, 0.08)",
                      borderRadius: 3,
                    }}
                  >
                    <span style={{ opacity: 0.85 }}>52周</span>
                    <span>{formatNumberWithSeparators(tape.fiftyTwoWeekLow)}</span>
                    <span
                      style={{
                        display: "inline-block",
                        width: 36,
                        height: 4,
                        background: "var(--c-border)",
                        borderRadius: 2,
                        position: "relative",
                        overflow: "hidden",
                        verticalAlign: "middle",
                      }}
                    >
                      {info.current_price != null ? (
                        <span
                          style={{
                            position: "absolute",
                            left: 0,
                            top: 0,
                            bottom: 0,
                            width: `${Math.max(0, Math.min(100, ((info.current_price - tape.fiftyTwoWeekLow) / (tape.fiftyTwoWeekHigh - tape.fiftyTwoWeekLow)) * 100))}%`,
                            background: colors.primary,
                            borderRadius: 2,
                          }}
                        />
                      ) : null}
                    </span>
                    <span>{formatNumberWithSeparators(tape.fiftyTwoWeekHigh)}</span>
                  </span>
                </Tooltip>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="stock-header-card__actions">
          <Button
            icon={isWatched ? <StarFilled /> : <PlusOutlined />}
            aria-label={isWatched ? "移出自选" : "加入自选"}
            loading={isWatchlistPending}
            onClick={onToggleWatchlist}
            style={{ color: isWatched ? colors.warning : colors.primary }}
          >
            {isWatched ? "已自选" : "加入自选"}
          </Button>
          <Button
            icon={<ShareAltOutlined />}
            aria-label="导出个股速览卡片"
            onClick={() => setSnapshotModalOpen(true)}
          >
            分享卡片
          </Button>
          {!isHK && (
            <Button
              icon={<ThunderboltOutlined />}
              aria-label="发起量化回测"
              onClick={() => navigate(`/quant?panel=setup&codes=${info.code}`)}
            >
              量化回测
            </Button>
          )}
          {shouldShowAnalysis && (
            <Button
              type="primary"
              icon={<FileSearchOutlined />}
              aria-label="进入 AI 分析"
              onClick={() => navigate(buildStockAnalysisUrl(info.code))}
            >
              进入 AI 分析
            </Button>
          )}
        </div>
      </div>
      <StockSnapshotModal
        open={snapshotModalOpen}
        onClose={() => setSnapshotModalOpen(false)}
        info={info}
        market={market}
        englishName={englishName}
        changePct={changePct}
        tape={tape}
      />
    </Card>
  );
}
