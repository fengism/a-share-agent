import { useEffect } from "react";
import { message } from "antd";
import { useLocation } from "react-router-dom";
import { useHKStockQuote } from "../../api/queryHooks/hk";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useWatchlist,
} from "../../api/queryHooks/watchlist";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { useStyles } from "../../styles/ui";
import DeferredStockSection from "./DeferredStockSection";
import HKTradingRulesCard from "./HKTradingRulesCard";
import StockBusinessIntro from "./StockBusinessIntro";
import StockCharts from "./StockCharts";
import StockDetailTabs from "./StockDetailTabs";
import StockHeaderCard from "./StockHeaderCard";
import StockMetrics from "./StockMetrics";

export default function HKStockPageContent({ code }: { code: string }) {
  const { pageContainerStyle } = useStyles();
  const [messageApi, contextHolder] = message.useMessage();
  const { hash } = useLocation();

  const quoteQuery = useHKStockQuote(code);

  useEffect(() => {
    const targetId = hash === "#stock-details" ? "stock-details" : hash === "#stock-charts" ? "stock-charts" : null;
    if (!targetId) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(targetId)?.scrollIntoView({ block: "start" });
    });
    return () => cancelAnimationFrame(frame);
  }, [code, hash, quoteQuery.isLoading]);
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

  const headerInfo = {
    code: quote?.code || code,
    name: quote?.name || code,
    current_price: quote?.price ?? null,
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
        errorTitle="港股行情加载失败"
        skeletonRows={5}
        minHeight={260}
      >
        {quote ? (
          <StockHeaderCard
            info={headerInfo}
            isWatched={isWatched}
            isWatchlistPending={isWatchlistPending}
            onToggleWatchlist={handleToggleWatchlist}
            changePct={quote.change_pct}
            changeAmount={quote.change}
            englishName={quote.english_name}
            market="hk"
            showAnalysisButton={false}
          />
        ) : null}
      </SectionDataState>

      {/* ── 关键行情指标与港股交易规则 ── */}
      <section className="stock-page__overview-grid" aria-label="关键行情与交易规则">
        <StockMetrics market="hk" hkQuote={quote} />
        <HKTradingRulesCard />
      </section>

      {/* 主营业务独立成卡 */}
      <StockBusinessIntro code={code} />

      {/* ── 走势与历史行情 分时/K线/指标图 ── */}
      <StockCharts code={code} market="hk" name={quote?.name} />

      {/* ── 财务、估值与同业、资讯 ── */}
      <section id="stock-details" style={{ minWidth: 0, scrollMarginTop: 80 }}>
        <DeferredStockSection label="财务、估值与资讯" minHeight={420}>
          <StockDetailTabs key={code} code={code} market="hk" />
        </DeferredStockSection>
      </section>
    </main>
  );
}
