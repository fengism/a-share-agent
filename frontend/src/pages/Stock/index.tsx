import { useEffect } from "react";
import { Button, message, Result } from "antd";
import { Navigate, useLocation, useNavigate, useParams } from "react-router-dom";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useStockInfo,
  useStockIntraday,
  useWatchlist,
} from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { useStyles } from "../../styles/ui";
import { buildStockProfileUrl, parseStockCode } from "../../utils/stockLinks";
import DeferredStockSection from "./DeferredStockSection";
import HKStockPageContent from "./HKStockPageContent";
import StockBusinessIntro from "./StockBusinessIntro";
import StockCharts from "./StockCharts";
import StockHeaderCard from "./StockHeaderCard";
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
          />
        ) : null}
      </SectionDataState>
      <section className="stock-page__overview-grid" aria-label="公司经营与关键指标">
        {/* 关键指标即使数据未到也要占住第一列，否则兄弟卡片会从宽列跳到窄列、整页重排 */}
        <StockMetrics info={infoQuery.data} />
        <StockBusinessIntro code={code} />
      </section>
      <StockCharts code={code} />
      <section id="stock-details" style={{ minWidth: 0, scrollMarginTop: 80 }}>
        <DeferredStockSection label="财务、估值、资金与资讯" minHeight={420}>
          <StockDetailTabs key={code} code={code} />
        </DeferredStockSection>
      </section>
    </main>
  );
}
