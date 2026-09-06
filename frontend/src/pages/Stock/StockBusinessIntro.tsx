import { ProfileOutlined } from "@ant-design/icons";
import { Card, Typography } from "antd";
import { useStockBusinessIntro } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

const { Text } = Typography;

export default function StockBusinessIntro({ code }: { code: string }) {
  const query = useStockBusinessIntro(code);
  const { cardStyle } = useStyles();
  const items = Object.entries(query.data?.items ?? {}).filter(([, value]) => Boolean(value));

  return (
    <Card
      className="stock-section-card stock-business-card"
      title={<StockSectionTitle icon={<ProfileOutlined />} title="主营业务" description="公司经营范围与核心产品" />}
      extra={query.data?.source ? <Text type="secondary">来源：{query.data.source.toUpperCase()}</Text> : null}
      style={cardStyle}
    >
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={items.length === 0}
        emptyText="暂无主营业务资料"
        errorTitle="主营业务加载失败"
        minHeight={140}
      >
        <div className="stock-business-intro">
          {items.map(([label, value]) => (
            <article className="stock-business-intro__item" key={label}>
              <span>{label}</span>
              <p>{value}</p>
            </article>
          ))}
        </div>
      </SectionDataState>
    </Card>
  );
}
