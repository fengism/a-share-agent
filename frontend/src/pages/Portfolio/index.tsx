import { useCallback, useRef, useState } from "react";
import { PlusOutlined, ReloadOutlined, SettingOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Drawer, Modal, Skeleton, Space, message } from "antd";
import { usePortfolio } from "../../api/queries";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import PageShell, { PageHeader } from "../../components/page/PageShell";
import QueryErrorState from "../../components/QueryErrorState";
import { useStyles } from "../../styles/ui";
import PortfolioSummaryCards from "./PortfolioSummaryCards";
import PortfolioTables from "./PortfolioTables";
import PortfolioTradeKline from "./PortfolioTradeKline";
import PortfolioQuoteStatus from "./PortfolioQuoteStatus";
import PortfolioRiskPanel from "./PortfolioRiskPanel";
import PortfolioEquityCurve from "./PortfolioEquityCurve";
import PortfolioSettingsCard from "./PortfolioSettingsCard";
import TransactionEntryCard, { type TransactionEntryCardHandle } from "./TransactionEntryCard";
import type { PortfolioStockSummary, PortfolioTrimSuggestion } from "../../types/portfolio";
import { errorMessage, formatTime } from "./portfolioFormatters";
import "./portfolio.css";

export default function PortfolioPage() {
  const transactionEntryRef = useRef<TransactionEntryCardHandle>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isTransactionDrawerOpen, setIsTransactionDrawerOpen] = useState(false);
  const [klineStockCode, setKlineStockCode] = useState<string | undefined>(undefined);
  const { cardStyle } = useStyles();

  const {
    data,
    error,
    isError,
    isFetching,
    isLoading,
    refetch,
  } = usePortfolio();

  const handleRefresh = async () => {
    const result = await refetch();
    if (result.isError) message.error(`刷新失败：${errorMessage(result.error)}`);
  };

  const quotedAt = data?.quoted_at ? formatTime(data.quoted_at) : "尚未获取";

  const handleSell = useCallback((stock: PortfolioStockSummary) => {
    setIsTransactionDrawerOpen(true);
    setTimeout(() => {
      transactionEntryRef.current?.startSell(stock);
    }, 0);
  }, []);

  const handleViewKline = useCallback((stockCode: string) => {
    setKlineStockCode(stockCode);
    const el = document.getElementById("portfolio-trade-kline");
    el?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const handleTrimSuggestion = useCallback((suggestion: PortfolioTrimSuggestion) => {
    const stock = data?.stocks.find((item) => item.stock_code === suggestion.stock_code);
    if (!stock) {
      message.warning("未找到对应持仓，请刷新后重试");
      return;
    }
    setIsTransactionDrawerOpen(true);
    setTimeout(() => {
      transactionEntryRef.current?.startSell(stock, suggestion.suggested_shares);
    }, 0);
  }, [data?.stocks]);

  return (
    <PageShell>
      <PageHeader
        title="仓位管理"
        description="记录买卖交易，按 FIFO 成本自动计算当前持仓、已实现盈亏与综合收益。"
        actions={(
        <Space wrap>
          <PortfolioQuoteStatus
            quotedAt={quotedAt}
            source={data?.quote_source ?? ""}
            stale={Boolean(data?.quote_stale)}
          />
          <DataRefreshIndicator active={isFetching && !isLoading} label="刷新行情" />
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setIsTransactionDrawerOpen(true)}
          >
            记录交易
          </Button>
          <Button
            icon={<SettingOutlined />}
            onClick={() => setIsSettingsOpen(true)}
          >
            账户设置
          </Button>
          <Button
            icon={<ReloadOutlined />}
            loading={isFetching}
            onClick={handleRefresh}
          >
            刷新
          </Button>
        </Space>
        )}
      />

      {isError && !data ? (
        <Card style={{ ...cardStyle, marginBottom: 16 }}>
          <QueryErrorState error={error} onRetry={() => refetch()} title="持仓数据加载失败" />
        </Card>
      ) : null}

      {isError && data ? (
        <Alert
          type="warning"
          showIcon
          title="实时行情刷新失败，当前展示上一次数据"
          description={errorMessage(error)}
          style={{ marginBottom: 16 }}
        />
      ) : null}

      {isLoading ? (
        <Card style={{ ...cardStyle, marginBottom: 16 }}>
          <Skeleton active paragraph={{ rows: 3 }} />
        </Card>
      ) : data ? (
        <>
          <PortfolioSummaryCards
            summary={data.summary}
            stocks={data.stocks}
            onOpenSettings={() => setIsSettingsOpen(true)}
          />
          <PortfolioEquityCurve />
          <PortfolioRiskPanel risk={data.risk} onUseSuggestion={handleTrimSuggestion} />
          <PortfolioTables
            positions={data.positions}
            stocks={data.stocks}
            transactions={data.transactions}
            closedPositions={data.closed_positions}
            onSell={handleSell}
            onViewKline={handleViewKline}
          />
          <PortfolioTradeKline
            stocks={data.stocks}
            transactions={data.transactions}
            selectedStockCode={klineStockCode}
          />
        </>
      ) : null}

      {/* 记录交易流水抽屉（适配移动端与桌面端） */}
      <Drawer
        title="记录交易流水"
        open={isTransactionDrawerOpen}
        onClose={() => setIsTransactionDrawerOpen(false)}
        width={560}
        destroyOnClose={false}
      >
        <TransactionEntryCard
          ref={transactionEntryRef}
          stocks={data?.stocks ?? []}
          isDrawer
          onSuccess={() => setIsTransactionDrawerOpen(false)}
        />
      </Drawer>

      {/* 账户与风控设置弹窗 */}
      {data?.settings ? (
        <Modal
          title={<span><SettingOutlined style={{ marginRight: 6 }} />账户与风控设置</span>}
          open={isSettingsOpen}
          onCancel={() => setIsSettingsOpen(false)}
          footer={null}
          destroyOnClose={false}
        >
          <PortfolioSettingsCard
            settings={data.settings}
            isModal
            onSaved={() => setIsSettingsOpen(false)}
          />
        </Modal>
      ) : null}
    </PageShell>
  );
}
