import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChartOutlined,
  CompassOutlined,
  FullscreenOutlined,
  FundProjectionScreenOutlined,
  GlobalOutlined,
  LineChartOutlined,
  PlusOutlined,
  ReloadOutlined,
  StarFilled,
} from "@ant-design/icons";
import {
  Button,
  Card,
  message,
  Modal,
  Segmented,
  Space,
  Switch,
  Tag,
  Typography,
} from "antd";
import { useHKStockHistory, useHKStockQuote } from "../../api/queryHooks/hk";
import { useStockIntraday } from "../../api/queryHooks/stock";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queryHooks/watchlist";
import IndicatorSubCharts from "../../charts/IndicatorSubCharts";
import IntradayChart from "../../charts/IntradayChart";
import LazyKlineChart from "../../charts/LazyKlineChart";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { useColors, useStyles } from "../../styles/ui";
import type { KlineItem } from "../../types/stock";
import { MAX_KLINE_HISTORY_YEARS, yearsAgoDate } from "../../utils/date";
import StockBusinessIntro from "./StockBusinessIntro";
import KeyFinancialMetricsSection from "../../features/investment-research/KeyFinancialMetricsSection";
import RevenueBreakdownSection from "../../features/investment-research/RevenueBreakdownSection";
import HKIndustryComparisonSection from "./HKIndustryComparisonSection";
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

type HKChartView = "intraday" | "kline" | "macd" | "rsi" | "kdj";

export default function HKStockPageContent({ code }: { code: string }) {
  const colors = useColors();
  const { pageContainerStyle, cardStyle } = useStyles();
  const [messageApi, contextHolder] = message.useMessage();

  const [activeView, setActiveView] = useState<HKChartView>("intraday");
  const [showAvgLine, setShowAvgLine] = useState(true);
  const [showPrevClose, setShowPrevClose] = useState(true);
  const [period, setPeriod] = useState<string>("daily");
  const [adjust, setAdjust] = useState<string>("qfq");
  const [expanded, setExpanded] = useState<boolean>(false);
  const [historyYears, setHistoryYears] = useState(1);

  const startDate = useMemo(() => yearsAgoDate(historyYears), [historyYears]);
  const historyLimitReached = historyYears >= MAX_KLINE_HISTORY_YEARS;

  useEffect(() => {
    setHistoryYears(1);
  }, [code, period]);

  const handleReachLeftEdge = useCallback(() => {
    setHistoryYears((years) => Math.min(years + 1, MAX_KLINE_HISTORY_YEARS));
  }, []);

  const quoteQuery = useHKStockQuote(code);
  const historyQuery = useHKStockHistory(code, period, adjust, startDate);
  const intradayQuery = useStockIntraday(code);
  const intradayItems = intradayQuery.data?.items ?? [];
  const latestIntradayTime = intradayItems.length > 0 ? intradayItems[intradayItems.length - 1].time : null;
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
              <dt>市盈率 (TTM)</dt>
              <dd>{quote?.pe_ttm != null ? quote.pe_ttm.toFixed(2) : "-"}</dd>
            </div>
            <div className="stock-metric">
              <dt>市净率</dt>
              <dd>{quote?.pb != null ? quote.pb.toFixed(2) : "-"}</dd>
            </div>
            <div className="stock-metric">
              <dt>总市值</dt>
              <dd>{quote?.market_cap != null ? `${formatAmount(quote.market_cap)} 港元` : "-"}</dd>
            </div>
            <div className="stock-metric">
              <dt>流通市值</dt>
              <dd>{quote?.float_market_cap != null ? `${formatAmount(quote.float_market_cap)} 港元` : "-"}</dd>
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

      {/* 与 A 股页对齐：主营业务独立成卡，不塞进上面的两列栅格（那会把
          「港股交易规则」挤到下一行留白）。首次访问即触发抓取并落库。 */}
      <StockBusinessIntro code={code} />

      {/* 港股营收构成：同花顺 F10 主营构成分析，仅占比无金额 */}
      <RevenueBreakdownSection code={code} />

      {/* 港股财务报表：同花顺 F10 最近四个报告期，金额保留公司原始披露币种。 */}
      <Card
        data-testid="hk-financial-data"
        className="stock-section-card stock-financial-card"
        title={(
          <StockSectionTitle
            icon={<BarChartOutlined />}
            title="财务数据"
            description="同花顺 F10 · 最近四个报告期 · 金额按公司原始披露币种"
          />
        )}
        style={cardStyle}
      >
        <KeyFinancialMetricsSection code={code} showHeader={false} />
      </Card>

      {/* 港股行业地位与同业对比：同花顺 F10 行业对比 */}
      <HKIndustryComparisonSection code={code} />

      {/* ── 走势与历史行情 分时/K线/指标图 ── */}
      <Card
        className="stock-section-card"
        title={
          <StockSectionTitle
            icon={
              activeView === "intraday"
                ? <BarChartOutlined />
                : activeView === "kline"
                ? <LineChartOutlined />
                : <FundProjectionScreenOutlined />
            }
            title={
              activeView === "intraday"
                ? "分时走势"
                : activeView === "kline"
                ? "走势与历史行情"
                : `${activeView.toUpperCase()} 技术指标`
            }
            description={`${quote?.name || code} ${
              activeView === "intraday"
                ? "当日分时与成交走势"
                : activeView === "kline"
                ? "多周期K线与技术走势"
                : `${activeView.toUpperCase()} 动量与趋势分析`
            }`}
          />
        }
        extra={
          <Space wrap>
            <Segmented
              aria-label="走势类型"
              options={[
                { label: "分时", value: "intraday" },
                { label: "K线", value: "kline" },
                { label: "MACD", value: "macd" },
                { label: "RSI", value: "rsi" },
                { label: "KDJ", value: "kdj" },
              ]}
              value={activeView}
              onChange={(val) => setActiveView(val as HKChartView)}
            />
            {activeView === "kline" && (
              <>
                <Segmented
                  aria-label="K线周期"
                  options={[
                    { label: "日K", value: "daily" },
                    { label: "周K", value: "weekly" },
                    { label: "月K", value: "monthly" },
                    { label: "年K", value: "annual" },
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
              </>
            )}
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
        {activeView === "intraday" ? (
          <>
            <div className="stock-chart-toolbar" style={{ justifyContent: "space-between", marginBottom: 12, display: "flex", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: "12px", color: "var(--c-text-secondary)" }}>
                {latestIntradayTime && (
                  <span>
                    数据时间: <strong style={{ color: "var(--c-text-primary)", fontFamily: "var(--c-font-mono)" }}>{latestIntradayTime}</strong>
                  </span>
                )}
                {intradayQuery.isFetching && <span style={{ color: "var(--c-primary)" }}>刷新中...</span>}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px" }}>
                  均价线
                  <Switch aria-label="均价线" size="small" checked={showAvgLine} onChange={setShowAvgLine} />
                </label>
                <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, fontSize: "12px" }}>
                  昨收线
                  <Switch aria-label="昨收线" size="small" checked={showPrevClose} onChange={setShowPrevClose} />
                </label>
                <Button
                  size="small"
                  type="text"
                  icon={<ReloadOutlined spin={intradayQuery.isFetching} />}
                  onClick={() => intradayQuery.refetch()}
                  title="刷新分时数据"
                  style={{ color: "var(--c-text-secondary)" }}
                >
                  刷新
                </Button>
              </div>
            </div>
            <SectionDataState
              isLoading={intradayQuery.isLoading}
              error={intradayQuery.error}
              onRetry={() => intradayQuery.refetch()}
              isEmpty={!intradayItems.length}
              emptyText="暂无港股分时行情数据"
              minHeight={420}
            >
              <IntradayChart
                data={intradayItems}
                prevClose={intradayQuery.data?.prev_close}
                height={440}
                viewKey={`hk-intraday-${code}`}
                showAvgLine={showAvgLine}
                showPrevCloseLine={showPrevClose}
                market="hk"
              />
            </SectionDataState>
          </>
        ) : activeView === "kline" ? (
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
              onReachLeftEdge={handleReachLeftEdge}
              historyLimitReached={historyLimitReached}
            />
          </SectionDataState>
        ) : (
          <div className="stock-macd-panel" style={{ minHeight: 436 }}>
            <IndicatorSubCharts
              code={code}
              types={["macd", "rsi", "kdj"]}
              activeType={activeView}
              onTypeChange={(type) => setActiveView(type as HKChartView)}
              period={period}
              onPeriodChange={setPeriod}
              startDate={startDate}
              historyYears={historyYears}
              onReachLeftEdge={handleReachLeftEdge}
              historyLimitReached={historyLimitReached}
              height={340}
            />
          </div>
        )}
      </Card>

      {/* ── 全屏模态框 ── */}
      <Modal
        open={expanded}
        onCancel={() => setExpanded(false)}
        footer={null}
        width="94vw"
        style={{ top: 20 }}
        destroyOnHidden
        title={`${quote?.name || code}（${code}）· ${
          activeView === "intraday"
            ? "分时图全屏"
            : activeView === "kline"
            ? (period === "daily" ? "日K" : period === "weekly" ? "周K" : period === "monthly" ? "月K" : "年K") + "线全屏"
            : `${activeView.toUpperCase()} 技术副图全屏`
        }`}
      >
        <div style={{ height: "80vh", minHeight: 480 }}>
          {activeView === "intraday" ? (
            <IntradayChart
              data={intradayItems}
              prevClose={intradayQuery.data?.prev_close}
              height={window.innerHeight * 0.76}
              viewKey={`hk-intraday-modal-${code}`}
              showAvgLine={showAvgLine}
              showPrevCloseLine={showPrevClose}
              market="hk"
            />
          ) : activeView === "kline" ? (
            <LazyKlineChart
              data={chartData}
              height={window.innerHeight * 0.76}
              viewKey={`hk-stock-modal-${code}-${period}-${adjust}`}
              onReachLeftEdge={handleReachLeftEdge}
              historyLimitReached={historyLimitReached}
            />
          ) : (
            <div className="stock-macd-panel" style={{ minHeight: 600 }}>
              <IndicatorSubCharts
                code={code}
                types={["macd", "rsi", "kdj"]}
                activeType={activeView}
                onTypeChange={(type) => setActiveView(type as HKChartView)}
                period={period}
                onPeriodChange={setPeriod}
                startDate={startDate}
                historyYears={historyYears}
                onReachLeftEdge={handleReachLeftEdge}
                historyLimitReached={historyLimitReached}
                height={580}
              />
            </div>
          )}
        </div>
      </Modal>
    </main>
  );
}
