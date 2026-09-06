import { Card, Table, Tag, Typography } from "antd";
import type { TableProps } from "antd";
import { useStockReports } from "../../api/queries";
import type { StockResearchReport } from "../../types/stock";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens, useStyles, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";

interface Props {
  code: string;
}

const { Text } = Typography;

const POSITIVE_RATINGS = ["买入", "增持", "推荐", "强烈推荐", "优于大市", "跑赢行业", "看好"];
const NEGATIVE_RATINGS = ["减持", "卖出", "回避", "中性偏空", "跑输行业"];

function ratingColor(rating: string): SemanticTagColor | null {
  if (POSITIVE_RATINGS.some((word) => rating.includes(word))) return "up";
  if (NEGATIVE_RATINGS.some((word) => rating.includes(word))) return "down";
  if (rating) return "info";
  return null;
}

const columns: TableProps<StockResearchReport>["columns"] = [
  { title: "日期", dataIndex: "date", key: "date", width: 100 },
  {
    title: "评级",
    dataIndex: "rating",
    key: "rating",
    width: 90,
    render: (rating: string) =>
      rating ? <Tag style={semanticTagStyle(ratingColor(rating) ?? "info")}>{rating}</Tag> : "-",
  },
  {
    title: "目标价",
    dataIndex: "goal_price",
    key: "goal_price",
    width: 90,
    align: "right",
    render: (value: number | null) => (value != null ? value.toFixed(2) : "-"),
  },
  { title: "券商", dataIndex: "org", key: "org", width: 110, ellipsis: true },
  {
    title: "研报标题",
    dataIndex: "title",
    key: "title",
    render: (title: string, item) =>
      item.url ? (
        <a href={item.url} target="_blank" rel="noreferrer">
          {title}
        </a>
      ) : (
        title
      ),
  },
];

export default function ResearchReportsPanel({ code }: Props) {
  const c = useColors();
  const t = useTokens();
  const { cardStyle, sectionHeaderStyle } = useStyles();
  const reportsQuery = useStockReports(code);
  const data = reportsQuery.data;
  const items = data?.items ?? [];

  return (
    <SectionDataState
      isLoading={reportsQuery.isLoading}
      error={reportsQuery.error}
      onRetry={() => reportsQuery.refetch()}
      errorTitle="研报数据加载失败"
      skeletonRows={6}
      minHeight={280}
      isEmpty={!reportsQuery.isLoading && items.length === 0}
      emptyText="最近半年暂无研报数据"
    >
      <div style={{ display: "grid", gap: t.space[4] }}>
        <div style={sectionHeaderStyle}>
          <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>研报评级</Text>
          <Text type="secondary" style={{ fontSize: t.font.sm }}>
            券商调研评级跟踪 · 最近 {data?.months ?? 6} 个月 {data?.total_count ? `共 ${data.total_count} 份` : ""}
          </Text>
        </div>
        <Card
          size="small"
          title={`研报列表（${data?.total_count ?? 0} 份）`}
          extra={<Text type="secondary">来源：新浪财经</Text>}
          style={{ ...cardStyle }}
          styles={{ body: { padding: t.space[4] } }}
        >
          <Table<StockResearchReport>
            size="small"
            rowKey="id"
            columns={columns}
            dataSource={items}
            pagination={{ pageSize: 10, size: "small", showSizeChanger: false, hideOnSinglePage: true }}
          />
        </Card>
      </div>
    </SectionDataState>
  );
}
