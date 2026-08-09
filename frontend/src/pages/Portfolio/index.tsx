import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Card, Skeleton, Space, Tag, Typography, message } from "antd";
import { usePortfolio } from "../../api/queries";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import QueryErrorState from "../../components/QueryErrorState";
import { useColors, useStyles } from "../../styles/ui";
import AddPositionCard from "./AddPositionCard";
import PortfolioSummaryCards from "./PortfolioSummaryCards";
import PortfolioTables from "./PortfolioTables";
import { errorMessage, formatTime } from "./portfolioFormatters";

const { Paragraph, Text, Title } = Typography;

export default function PortfolioPage() {
  const colors = useColors();
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
          <Title level={3} style={pageTitleStyle}>仓位管理</Title>
          <Paragraph style={{ ...pageDescriptionStyle, marginBottom: 0 }}>
            记录每笔买入，按实时行情自动计算持仓市值、浮动盈亏与账户汇总。
          </Paragraph>
        </div>
        <Space wrap>
          <Tag color="blue">30 秒自动刷新</Tag>
          <Text style={{ color: colors.textMuted, fontSize: 12 }}>行情时间：{quotedAt}</Text>
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

      <AddPositionCard />

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
          <PortfolioTables positions={data.positions} stocks={data.stocks} />
        </>
      ) : null}
    </div>
  );
}
