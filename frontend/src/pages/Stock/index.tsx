import { Button, message, Result } from "antd";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import {
  useAddWatchlistItem,
  useDeleteWatchlistItem,
  useStockInfo,
  useWatchlist,
} from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import StockWorkspaceNav from "../../features/stock-navigation/StockWorkspaceNav";
import { useStyles } from "../../styles/ui";
import { buildStockProfileUrl, normalizeAshareStockCode } from "../../utils/stockLinks";
import DeferredStockSection from "./DeferredStockSection";
import StockBusinessIntro from "./StockBusinessIntro";
import StockCharts from "./StockCharts";
import StockHeaderCard from "./StockHeaderCard";
import StockFinancialMetrics from "./StockFinancialMetrics";
import StockInformationTabs from "./StockInformationTabs";
import StockMetrics from "./StockMetrics";
import "./stock-page.css";

export default function StockPage() {
  const { code = "" } = useParams<{ code: string }>();
  const routeCode = code.trim();
  const normalizedCode = normalizeAshareStockCode(routeCode);
  const navigate = useNavigate();
  const { pageContainerStyle } = useStyles();

  if (!normalizedCode) {
    return (
      <main className="stock-page" style={pageContainerStyle}>
        <Result
          status="warning"
          title="股票代码无效"
          subTitle="请输入 6 位 A 股代码，例如 600519、SH600519 或 600519.SH。"
          extra={<Button type="primary" onClick={() => navigate("/")}>返回首页</Button>}
        />
      </main>
    );
  }

  if (routeCode !== normalizedCode) {
    return <Navigate replace to={buildStockProfileUrl(normalizedCode)} />;
  }

  return <StockProfileContent code={normalizedCode} />;
}

function StockProfileContent({ code }: { code: string }) {
  const { pageContainerStyle } = useStyles();
  const [messageApi, contextHolder] = message.useMessage();
  const infoQuery = useStockInfo(code);
  const watchlistQuery = useWatchlist();
  const addWatchlistItem = useAddWatchlistItem();
  const deleteWatchlistItem = useDeleteWatchlistItem();
  const isWatched = Boolean(watchlistQuery.data?.items.some(
    (item) => item.stock_code === code && item.market !== "hk",
  ));
  const isWatchlistPending = addWatchlistItem.isPending || deleteWatchlistItem.isPending;

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
          />
        ) : null}
      </SectionDataState>
      <section className="stock-page__overview-grid" aria-label="公司经营与关键指标">
        {infoQuery.data ? <StockMetrics info={infoQuery.data} /> : null}
        <StockBusinessIntro code={code} />
      </section>
      <StockCharts code={code} />
      <DeferredStockSection label="财务指标" minHeight={360}>
        <StockFinancialMetrics code={code} />
      </DeferredStockSection>
      <DeferredStockSection label="资讯与研究" minHeight={420}>
        <StockInformationTabs code={code} />
      </DeferredStockSection>
    </main>
  );
}
