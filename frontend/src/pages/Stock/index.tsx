import { useEffect, useMemo } from "react";
import { Button, message, Result } from "antd";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useKlineData,
  useStockInfo,
  useStockIntraday,
  useWatchlist,
} from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import SectionAnchorNav from "../../components/SectionAnchorNav";
import { useStyles } from "../../styles/ui";
import { yearsAgoDate } from "../../utils/date";
import { buildStockProfileUrl, parseStockCode } from "../../utils/stockLinks";
import DeferredStockSection from "./DeferredStockSection";
import HKStockPageContent from "./HKStockPageContent";
import StockBusinessIntro from "./StockBusinessIntro";
import StockCharts from "./StockCharts";
import StockHeaderCard, { type StockHeaderTapeData } from "./StockHeaderCard";
import StockDetailTabs from "./StockDetailTabs";
import StockMetrics from "./StockMetrics";
import "./stock-page.css";

export default function StockPage() {
  const { code = "" } = useParams<{ code: string }>();
  const routeCode = code.trim();
  const parsed = parseStockCode(routeCode);
  const navigate = useNavigate();
  const { search, hash } = useLocation();
  const { pageContainerStyle } = useStyles();

  if (!parsed) {
    return (
      <main className="stock-page" style={pageContainerStyle}>
        <Result
          status="warning"
          title="股票代码无效"
          subTitle="请输入 6 位 A 股代码（如 600519、SH600519）或 5 位港股代码（如 00700、HK00700）。"
          extra={<Button type="primary" onClick={() => navigate("/")}>返回首页</Button>}
        />
      </main>
    );
  }

  if (routeCode !== parsed.code) {
    return <Navigate to={`${buildStockProfileUrl(parsed.code)}${search}${hash}`} replace />;
  }

  if (parsed.market === "hk") {
    return <HKStockPageContent code={parsed.code} />;
  }

  return <StockPageContent code={parsed.code} />;
}

function StockPageContent({ code }: { code: string }) {
  const { pageContainerStyle } = useStyles();
  const [messageApi, contextHolder] = message.useMessage();
  const infoQuery = useStockInfo(code);
  const { hash } = useLocation();
  useEffect(() => {
    const targetId = hash === "#stock-details" ? "stock-details" : hash === "#stock-charts" ? "stock-charts" : null;
    if (!targetId) return;
    // Run after the layout resets route scrolling and re-align after info loads.
    const frame = requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  }, [code, hash, infoQuery.isLoading]);
  const intradayQuery = useStockIntraday(code);
  const watchlistQuery = useWatchlist();
  const addWatchlistItem = useAddWatchlistItem();
  const deleteWatchlistItem = useDeleteWatchlistItem();
  const isWatched = Boolean(watchlistQuery.data?.items.some(
    (item) => item.stock_code === code && item.market !== "hk",
  ));
  const isWatchlistPending = addWatchlistItem.isPending || deleteWatchlistItem.isPending;

  const intradayItems = intradayQuery.data?.items;
  const prevClose = intradayQuery.data?.prev_close;
  const latestPrice = (intradayItems && intradayItems.length > 0)
    ? intradayItems[intradayItems.length - 1]?.price
    : infoQuery.data?.current_price;
  const changePct = (prevClose != null && prevClose > 0 && latestPrice != null)
    ? ((latestPrice - prevClose) / prevClose) * 100
    : null;

  const oneYearAgoStr = useMemo(() => yearsAgoDate(1), []);
  const kline1yQuery = useKlineData(code, "daily", "qfq", true, { startDate: oneYearAgoStr }, { liveRefresh: false });
  const fiftyTwoWeekRange = useMemo(() => {
    const items = kline1yQuery.data?.items;
    if (!items || items.length === 0) return null;
    let min = Infinity;
    let max = -Infinity;
    for (const it of items) {
      if (it.low != null && it.low < min) min = it.low;
      if (it.high != null && it.high > max) max = it.high;
    }
    return min < Infinity && max > -Infinity ? { low: min, high: max } : null;
  }, [kline1yQuery.data?.items]);

  const tapeData = useMemo<StockHeaderTapeData | null>(() => {
    if ((!intradayItems || intradayItems.length === 0) && !fiftyTwoWeekRange) return null;
    let high = -Infinity;
    let low = Infinity;
    let totalVolume = 0;
    let totalAmount = 0;
    if (intradayItems && intradayItems.length > 0) {
      for (const item of intradayItems) {
        if (item.price > high) high = item.price;
        if (item.price < low) low = item.price;
        if (item.volume != null) totalVolume += item.volume;
        if (item.amount != null) totalAmount += item.amount;
      }
    }
    const open = intradayItems?.[0]?.price ?? null;
    const amplitude = (prevClose != null && prevClose > 0 && high > -Infinity && low < Infinity)
      ? ((high - low) / prevClose) * 100
      : null;
    return {
      open,
      prevClose: prevClose ?? null,
      high: high > -Infinity ? high : null,
      low: low < Infinity ? low : null,
      volume: totalVolume > 0 ? totalVolume : null,
      amount: totalAmount > 0 ? totalAmount : null,
      amplitude,
      fiftyTwoWeekHigh: fiftyTwoWeekRange?.high ?? null,
      fiftyTwoWeekLow: fiftyTwoWeekRange?.low ?? null,
    };
  }, [intradayItems, prevClose, fiftyTwoWeekRange]);

  const handleToggleWatchlist = async () => {
    if (isWatchlistPending) return;
    try {
      if (isWatched) {
        await deleteWatchlistItem.mutateAsync(code);
        messageApi.success("已移出自选");
      } else {
        await addWatchlistItem.mutateAsync({ stock_code: code, note: "" });
        messageApi.success("已加入自选");
      }
    } catch (error) {
      messageApi.error(error instanceof Error ? error.message : "自选操作失败，请稍后重试");
    }
  };

  return (
    <main className="stock-page" style={pageContainerStyle}>
      {contextHolder}
      <StockWorkspaceNav code={code} />
      <SectionDataState
        isLoading={infoQuery.isLoading}
        error={infoQuery.error}
        onRetry={() => infoQuery.refetch()}
        isEmpty={!infoQuery.data}
        emptyText="暂无股票基础资料"
        errorTitle="股票资料加载失败"
        skeletonRows={5}
        minHeight={260}
      >
        {infoQuery.data ? (
          <StockHeaderCard
            info={infoQuery.data}
            isWatched={isWatched}
            isWatchlistPending={isWatchlistPending}
            onToggleWatchlist={() => { void handleToggleWatchlist(); }}
            changePct={changePct}
            tape={tapeData}
          />
        ) : null}
      </SectionDataState>
      <SectionAnchorNav
        ariaLabel="个股页面导航"
        items={[
          { id: "stock-overview", label: "行情与指标" },
          { id: "stock-chart-section", label: "走势图表" },
          { id: "stock-details", label: "财务与资讯" },
        ]}
        scrollOffset={88}
      />
      <section
        className="stock-page__overview-grid"
        id="stock-overview"
        aria-label="公司经营与关键指标"
        style={{ scrollMarginTop: 88 }}
      >
        {/* 关键指标即使数据未到也要占住第一列，否则兄弟卡片会从宽列跳到窄列、整页重排 */}
        <StockMetrics info={infoQuery.data} />
        <StockBusinessIntro code={code} />
      </section>
      <div id="stock-chart-section" style={{ scrollMarginTop: 88 }}>
        <StockCharts code={code} />
      </div>
      <section id="stock-details" style={{ minWidth: 0, scrollMarginTop: 88 }}>
        <DeferredStockSection label="财务、估值、资金与资讯" minHeight={420}>
          <StockDetailTabs key={code} code={code} />
        </DeferredStockSection>
      </section>
    </main>
  );
}
