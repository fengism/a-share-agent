import { BankOutlined, FileSearchOutlined, GlobalOutlined, PlusOutlined, StarFilled } from "@ant-design/icons";
import { Button, Card, Tag, Tooltip, Typography } from "antd";
import { useNavigate } from "react-router-dom";
import { useColors, useStyles } from "../../styles/ui";
import type { StockBasicInfo } from "../../types/stock";
import { formatNumberWithSeparators } from "../../utils/format";
import { buildStockAnalysisUrl } from "../../utils/stockLinks";

const { Title, Text } = Typography;

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
}: StockHeaderCardProps) {
  const navigate = useNavigate();
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isHK = market === "hk";
  const shouldShowAnalysis = showAnalysisButton ?? !isHK;
  const industry = info.second_industry?.name || info.first_industry?.name || info.exchange_industry;
  const fullIndustry = [info.first_industry?.name, info.second_industry?.name, info.third_industry?.name].filter(Boolean).join(" / ");
  const dotStateClass = changePct == null || changePct === 0 ? "" : changePct > 0 ? "is-up" : "is-down";

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
                  <Tag key={concept.code || concept.name}>{concept.name}</Tag>
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
    </Card>
  );
}
