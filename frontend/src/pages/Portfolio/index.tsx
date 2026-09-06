import { useCallback, useRef } from "react";
import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Skeleton, Space, Typography, message } from "antd";
import { usePortfolio } from "../../api/queries";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import QueryErrorState from "../../components/QueryErrorState";
import { useStyles } from "../../styles/ui";
import PortfolioSummaryCards from "./PortfolioSummaryCards";
import PortfolioTables from "./PortfolioTables";
import PortfolioQuoteStatus from "./PortfolioQuoteStatus";
import PortfolioRiskPanel from "./PortfolioRiskPanel";
import TransactionEntryCard, { type TransactionEntryCardHandle } from "./TransactionEntryCard";
import type { PortfolioStockSummary } from "../../types/portfolio";
import { errorMessage, formatTime } from "./portfolioFormatters";

const { Paragraph, Title } = Typography;

export default function PortfolioPage() {
  const transactionEntryRef = useRef<TransactionEntryCardHandle>(null);
  const { cardStyle, pageContainerStyle, pageDescriptionStyle, pageTitleStyle } = useStyles();
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
    transactionEntryRef.current?.startSell(stock);
  }, []);

  return (
    <div style={pageContainerStyle}>
      <div style={{
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 12,
        marginBottom: 20,
      }}>
        <div>
          <div className="u-page-title u-page-title--compact">
            <Title level={3} style={pageTitleStyle}>仓位管理</Title>
          </div>
          <Paragraph style={{ ...pageDescriptionStyle, marginBottom: 0 }}>
            记录买卖交易，按 FIFO 成本自动计算当前持仓、已实现盈亏与综合收益。
          </Paragraph>
        </div>
        <Space wrap>
          <PortfolioQuoteStatus
            quotedAt={quotedAt}
            source={data?.quote_source ?? ""}
            stale={Boolean(data?.quote_stale)}
          />
          <DataRefreshIndicator active={isFetching && !isLoading} label="刷新行情" />
          <Button
            icon={<ReloadOutlined />}
            loading={isFetching}
            onClick={handleRefresh}
          >
            刷新
          </Button>
        </Space>
      </div>

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
          <PortfolioSummaryCards summary={data.summary} />
          <PortfolioRiskPanel risk={data.risk} />
          <TransactionEntryCard ref={transactionEntryRef} stocks={data.stocks} />
          <PortfolioTables
            positions={data.positions}
            stocks={data.stocks}
            transactions={data.transactions}
            closedPositions={data.closed_positions}
            onSell={handleSell}
          />
        </>
      ) : (
        <TransactionEntryCard ref={transactionEntryRef} stocks={[]} />
      )}
    </div>
  );
}
