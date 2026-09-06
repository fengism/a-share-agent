import { Card, Typography } from "antd";
import { useCategorizedStockNews } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../styles/ui";
import type { StockNews } from "../../types/stock";

const { Text } = Typography;

function NewsList({ items }: { items: StockNews[] }) {
  const colors = useColors();
  if (items.length === 0) return <div style={{ color: colors.textSecondary }}>暂无相关新闻</div>;
  return (
    <ul className="stock-information-list">
      {items.map((item, index) => (
        <li className="stock-information-list__item" key={`${item.url || item.publish_time}-${index}`}>
          {item.url ? (
            <a className="stock-information-list__title" href={item.url} target="_blank" rel="noreferrer">{item.title}</a>
          ) : (
            <span className="stock-information-list__title">{item.title}</span>
          )}
          <span className="stock-information-list__meta">
            {[item.source, item.publish_time].filter(Boolean).join(" · ") || "-"}
          </span>
        </li>
      ))}
    </ul>
  );
}

export default function StockNewsPanel({ code }: { code: string }) {
  const query = useCategorizedStockNews(code);
  const { cardStyle } = useStyles();
  const eastmoneyNews = query.data?.eastmoney_news ?? [];
  const clsNews = query.data?.cls_news ?? [];

  return (
    <SectionDataState
      isLoading={query.isLoading}
      error={query.error}
      onRetry={() => query.refetch()}
      isEmpty={eastmoneyNews.length + clsNews.length === 0}
      emptyText="暂无相关新闻"
      errorTitle="新闻加载失败"
      minHeight={260}
    >
      <div className="stock-news-grid">
        <Card title={`财联社快讯（${clsNews.length}）`} style={cardStyle} size="small" extra={<Text type="secondary">快讯</Text>}>
          <NewsList items={clsNews} />
        </Card>
        <Card title={`东方财富资讯（${eastmoneyNews.length}）`} style={cardStyle} size="small" extra={<Text type="secondary">资讯</Text>}>
          <NewsList items={eastmoneyNews} />
        </Card>
      </div>
    </SectionDataState>
  );
}
