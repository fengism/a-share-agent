import { useMemo, useState } from "react";
import {
  BarChartOutlined,
  CompassOutlined,
  FullscreenOutlined,
  GlobalOutlined,
  LineChartOutlined,
  PlusOutlined,
  StarFilled,
} from "@ant-design/icons";
import {
  Button,
  Card,
  message,
  Modal,
  Segmented,
  Space,
  Tag,
  Typography,
} from "antd";
import { useNavigate } from "react-router-dom";
import { useHKStockHistory, useHKStockQuote } from "../../api/queryHooks/hk";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queryHooks/watchlist";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { useColors, useStyles } from "../../styles/ui";
import type { KlineItem } from "../../types/stock";
import StockSectionTitle from "./StockSectionTitle";

const { Title, Text } = Typography;

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null
    ? "-"
    : value.toLocaleString("zh-CN", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });
}

function formatAmount(value: number | null | undefined) {
  if (value == null) return "-";
  if (Math.abs(value) >= 1e8) return `${(value / 1e8).toFixed(2)}亿`;
  if (Math.abs(value) >= 1e4) return `${(value / 1e4).toFixed(1)}万`;
  return formatNumber(value, 0);
}

export default function HKStockPageContent({ code }: { code: string }) {
  const navigate = useNavigate();
  const colors = useColors();
  const { pageContainerStyle, cardStyle } = useStyles();
  const [messageApi, contextHolder] = message.useMessage();

  const [period, setPeriod] = useState<string>("daily");
  const [adjust, setAdjust] = useState<string>("qfq");
  const [expanded, setExpanded] = useState<boolean>(false);

  const quoteQuery = useHKStockQuote(code);
  const historyQuery = useHKStockHistory(code, period, adjust);
  const watchlistQuery = useWatchlist();
  const addWatchlistItem = useAddWatchlistItem();
  const deleteWatchlistItem = useDeleteWatchlistItem();

  const isWatched = Boolean(
    watchlistQuery.data?.items.some(
      (item) => item.stock_code === code && item.market === "hk",
    ),
  );
  const isWatchlistPending = addWatchlistItem.isPending || deleteWatchlistItem.isPending;

  const quote = quoteQuery.data;
  const changePct = quote?.change_pct;
  const dotStateClass =
    changePct == null || changePct === 0
      ? ""
      : changePct > 0
      ? "is-up"
      : "is-down";

  const amplitude =
    quote?.high != null && quote?.low != null && quote?.pre_close != null && quote.pre_close > 0
      ? ((quote.high - quote.low) / quote.pre_close) * 100
      : null;

  const chartData: KlineItem[] = useMemo(() => {
    return (historyQuery.data?.items ?? []).map((item) => ({
      date: item.date,
      open: item.open,
      close: item.close,
      high: item.high,
      low: item.low,
      volume: item.volume,
      amount: item.amount,
      amplitude: item.amplitude ?? null,
      turnover_pct: item.turnover_pct ?? null,
      change_pct: item.change_pct ?? null,
    }));
  }, [historyQuery.data?.items]);

  const handleToggleWatchlist = async () => {
    if (isWatchlistPending) return;
    try {
      if (isWatched) {
        await deleteWatchlistItem.mutateAsync({ stockCode: code, market: "hk" });
        messageApi.success("已移出港股自选");
      } else {
        await addWatchlistItem.mutateAsync({ stock_code: code, market: "hk", note: "" });
        messageApi.success("已加入港股自选");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "自选操作失败，请稍后重试");
    }
  };

  return (
    <main className="stock-page" style={pageContainerStyle}>
      {contextHolder}
      <StockWorkspaceNav code={code} market="hk" />

      {/* ── 顶部行情卡片 ── */}
      <SectionDataState
        isLoading={quoteQuery.isLoading}
        error={quoteQuery.error}
        onRetry={() => quoteQuery.refetch()}
        isEmpty={!quote}
        emptyText="暂无港股实时行情数据"
        errorTitle="港股资料加载失败"
        skeletonRows={5}
        minHeight={200}
      >
        {quote ? (
          <Card className="stock-header-card" style={cardStyle} styles={{ body: { padding: 0 } }}>
            <span className="stock-header-card__glow" aria-hidden="true" />
            <div className="stock-header-card__content">
              <div className="stock-header-card__identity">
                <div className="stock-header-card__eyebrow">
                  <span aria-hidden="true" />
                  港股概览 · 香港联合交易所
                </div>
                <div className="stock-header-card__title-row">
                  <span className="stock-header-card__icon" aria-hidden="true">
                    <GlobalOutlined />
                  </span>
                  <Title level={2}>{quote.name || code}</Title>
                  <Text className="stock-header-card__code">{code}</Text>
                </div>
                <div className="stock-header-card__tags">
                  <Tag color="blue">港股主板</Tag>
                  {quote.english_name && <Tag>{quote.english_name}</Tag>}
                  <Tag>港币 (HKD)</Tag>
                  <Tag>T+0 回转交易</Tag>
                </div>
              </div>

              <div className="stock-header-card__quote">
                <Text type="secondary">
                  <span className={`stock-header-card__quote-dot ${dotStateClass}`.trim()} />
                  最新价
                </Text>
                <strong
                  className={changePct == null || changePct === 0 ? "" : changePct > 0 ? "is-up" : "is-down"}
                  style={{
                    color:
                      changePct == null || changePct === 0
                        ? colors.textPrimary
                        : changePct > 0
                        ? colors.up
                        : colors.down,
                  }}
                >
                  {quote.price == null ? "-" : `HK$${formatNumber(quote.price)}`}
                </strong>
                <small>
                  {quote.change != null && quote.change_pct != null ? (
                    <span style={{ color: changePct && changePct > 0 ? colors.up : colors.down }}>
                      {changePct && changePct > 0 ? "+" : ""}
                      {formatNumber(quote.change)} (
                      {changePct && changePct > 0 ? "+" : ""}
                      {formatNumber(quote.change_pct)}%)
                    </span>
                  ) : (
                    "新浪实时行情"
                  )}
                </small>
              </div>

              <div className="stock-header-card__actions">
                <Button
                  icon={isWatched ? <StarFilled /> : <PlusOutlined />}
                  aria-label={isWatched ? "移出自选" : "加入自选"}
                  loading={isWatchlistPending}
                  onClick={handleToggleWatchlist}
                  style={{ color: isWatched ? colors.warning : colors.primary }}
                >
                  {isWatched ? "已自选" : "加入自选"}
                </Button>
                <Button
                  type="primary"
                  icon={<LineChartOutlined />}
                  aria-label="查看H股大盘市场"
                  onClick={() => navigate("/market?market=hk")}
                >
                  进入 H股市场
                </Button>
              </div>
            </div>
          </Card>
        ) : null}
      </SectionDataState>

      {/* ── 核心指标与规则概览 ── */}
      <section className="stock-page__overview-grid" aria-label="港股关键交易指标与基本资料">
        <Card
          className="stock-section-card stock-metrics-card"
          title={<StockSectionTitle icon={<BarChartOutlined />} title="关键行情指标" description="港股主板盘口与成交明细" />}
          style={cardStyle}
          styles={{ body: { padding: 0 } }}
        >
          <dl className="stock-metrics-grid">
            <div className="stock-metric stock-metric--featured">
              <dt>今开盘</dt>
              <dd>{formatNumber(quote?.open)}</dd>
            </div>
            <div className="stock-metric stock-metric--featured">
              <dt>昨收盘</dt>
              <dd>{formatNumber(quote?.pre_close)}</dd>
            </div>
            <div className="stock-metric">
              <dt>最高价</dt>
              <dd style={{ color: colors.up }}>{formatNumber(quote?.high)}</dd>
            </div>
            <div className="stock-metric">
              <dt>最低价</dt>
              <dd style={{ color: colors.down }}>{formatNumber(quote?.low)}</dd>
            </div>
            <div className="stock-metric">
              <dt>振幅</dt>
              <dd>{amplitude != null ? `${amplitude.toFixed(2)}%` : "-"}</dd>
            </div>
            <div className="stock-metric">
              <dt>成交额</dt>
              <dd>{formatAmount(quote?.amount)} 港元</dd>
            </div>
            <div className="stock-metric">
              <dt>成交量</dt>
              <dd>{formatAmount(quote?.volume)} 股</dd>
            </div>
            <div className="stock-metric">
              <dt>买一价 / 卖一价</dt>
              <dd>{formatNumber(quote?.bid)} / {formatNumber(quote?.ask)}</dd>
            </div>
            <div className="stock-metric">
              <dt>数据更新时间</dt>
              <dd style={{ fontSize: 12 }}>{quote?.updated_at || "实时交易中"}</dd>
            </div>
          </dl>
        </Card>

        <Card
          className="stock-section-card stock-business-intro-card"
          title={<StockSectionTitle icon={<CompassOutlined />} title="港股交易规则" description="香港证券市场交易机制速览" />}
          style={cardStyle}
        >
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.primary}` }}>
              <div style={{ fontSize: 12, color: colors.textSecondary }}>交易机制</div>
              <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>T+0 回转交易 · 无单日涨跌幅限制</div>
            </div>
            <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.accent}` }}>
              <div style={{ fontSize: 12, color: colors.textSecondary }}>交易时间段</div>
              <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>早盘 09:30-12:00 · 午盘 13:00-16:00</div>
            </div>
            <div style={{ padding: "10px 14px", background: colors.nestedBg, borderRadius: 8, borderLeft: `3px solid ${colors.info}` }}>
              <div style={{ fontSize: 12, color: colors.textSecondary }}>结算与交收</div>
              <div style={{ fontWeight: 600, marginTop: 2, color: colors.textPrimary }}>T+2 证券及资金结算 · 港币 (HKD) 报价</div>
            </div>
          </div>
        </Card>
      </section>

      {/* ── 走势与历史行情 K线图 ── */}
      <Card
        className="stock-section-card"
        title={
          <StockSectionTitle
            icon={<LineChartOutlined />}
            title="走势与历史行情"
            description={`${quote?.name || code} 多周期K线与技术走势`}
          />
        }
        extra={
          <Space wrap>
            <Segmented
              aria-label="K线周期"
              options={[
                { label: "日K", value: "daily" },
                { label: "周K", value: "weekly" },
                { label: "月K", value: "monthly" },
              ]}
              value={period}
              onChange={(val) => setPeriod(String(val))}
            />
            <Segmented
              aria-label="复权方式"
              options={[
                { label: "前复权", value: "qfq" },
                { label: "后复权", value: "hfq" },
                { label: "不复权", value: "none" },
              ]}
              value={adjust}
              onChange={(val) => setAdjust(String(val))}
            />
            <Button
              type="text"
              size="small"
              icon={<FullscreenOutlined />}
              aria-label="全屏查看行情"
              onClick={() => setExpanded(true)}
            />
          </Space>
        }
        style={cardStyle}
      >
        <SectionDataState
          isLoading={historyQuery.isLoading}
          error={historyQuery.error}
          onRetry={() => historyQuery.refetch()}
          isEmpty={!chartData.length}
          emptyText="暂无港股历史行情数据"
          minHeight={420}
        >
          <LazyKlineChart
            data={chartData}
            height={440}
            viewKey={`hk-stock-page-${code}-${period}-${adjust}`}
          />
        </SectionDataState>
      </Card>

      {/* ── 全屏K线模态框 ── */}
      <Modal
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width="94vw"
        style={{ top: 20 }}
        destroyOnHidden
        title={`${quote?.name || code}（${code}）· ${period === "daily" ? "日K" : period === "weekly" ? "周K" : "月K"}线全屏`}
      >
        <div style={{ height: "80vh", minHeight: 480 }}>
          <LazyKlineChart
            data={chartData}
            height={window.innerHeight * 0.76}
            viewKey={`hk-stock-modal-${code}-${period}-${adjust}`}
          />
        </div>
      </Modal>
    </main>
  );
}
