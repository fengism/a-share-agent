import { useState } from "react";
import { DownOutlined, ProfileOutlined, UpOutlined } from "@ant-design/icons";
import { Button, Card, Typography } from "antd";
import { useStockBusinessIntro } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

const { Text } = Typography;

export default function StockBusinessIntro({ code }: { code: string }) {
  const query = useStockBusinessIntro(code);
  const { cardStyle } = useStyles();
  const [expanded, setExpanded] = useState(false);
  const items = Object.entries(query.data?.items ?? {}).filter(([, value]) => Boolean(value));

  const visibleItems = expanded || items.length <= 4 ? items : items.slice(0, 3);

  return (
    <Card
      className="stock-section-card stock-business-card"
      title={<StockSectionTitle icon={<ProfileOutlined />} title="主营业务" description="公司经营范围与核心产品" />}
      extra={
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          {items.length > 4 ? (
            <Button
              type="link"
              size="small"
              icon={expanded ? <UpOutlined /> : <DownOutlined />}
              onClick={() => setExpanded((prev) => !prev)}
              style={{ padding: 0 }}
            >
              {expanded ? "收起" : `展开更多 (${items.length - 3})`}
            </Button>
          ) : null}
          {query.data?.source ? <Text type="secondary">来源：{query.data.source.toUpperCase()}</Text> : null}
        </div>
      }
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
          {visibleItems.map(([label, value]) => (
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
