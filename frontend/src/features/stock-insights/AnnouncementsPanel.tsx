import { useState } from "react";
import { Card, Pagination, Tag, Typography } from "antd";
import { useStockBulletins } from "../../api/queries";
import type { StockBulletin } from "../../types/stock";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens, useStyles, semanticTagStyle } from "../../theme/hooks";
import type { SemanticTagColor } from "../../theme/hooks";

interface Props {
  code: string;
}

const { Text } = Typography;

const BULLETIN_PAGE_SIZE = 10;

function bulletinTypeColor(type: string): SemanticTagColor {
  if (type.includes("定期") || type.includes("财报")) return "primary";
  if (type.includes("临时")) return "warning";
  return "info";
}

function BulletinItem({ item }: { item: StockBulletin }) {
  const c = useColors();
  const t = useTokens();
  const metaParts = [item.date, item.origin].filter(Boolean).join(" | ");
  return (
    <li className="analysis-detail-list__item">
      <span className="analysis-detail-list__title">
        {item.url ? (
          <a href={item.url} target="_blank" rel="noreferrer" style={{ color: c.textPrimary }}>
            {item.title}
          </a>
        ) : (
          item.title
        )}
        {item.pdf_url && (
          <a href={item.pdf_url} target="_blank" rel="noreferrer" style={{ marginLeft: t.space[2], fontSize: t.font.sm }}>
            PDF
          </a>
        )}
      </span>
      <span className="analysis-detail-list__meta">
        {item.type && (
          <Tag style={{ ...semanticTagStyle(bulletinTypeColor(item.type)), marginInlineEnd: t.space[2] }}>
            {item.type}
          </Tag>
        )}
        {item.type2 && <Text type="secondary" style={{ fontSize: t.font.sm }}>{item.type2}</Text>}
        {metaParts ? <span>{item.type2 ? " | " : ""}{metaParts}</span> : null}
      </span>
    </li>
  );
}

export default function AnnouncementsPanel({ code }: Props) {
  const c = useColors();
  const t = useTokens();
  const { cardStyle, sectionHeaderStyle } = useStyles();
  const [page, setPage] = useState(1);
  const bulletinsQuery = useStockBulletins(code, page, BULLETIN_PAGE_SIZE);
  const data = bulletinsQuery.data;
  const items = data?.items ?? [];
  const totalPages = data?.total_pages ?? 0;

  return (
    <SectionDataState
      isLoading={bulletinsQuery.isLoading}
      error={bulletinsQuery.error}
      onRetry={() => bulletinsQuery.refetch()}
      errorTitle="公告数据加载失败"
      skeletonRows={6}
      minHeight={280}
    >
      <div style={{ display: "grid", gap: t.space[4] }}>
        <div style={sectionHeaderStyle}>
          <Text strong style={{ color: c.textPrimary, fontSize: t.font.md }}>公司公告</Text>
          <Text type="secondary" style={{ fontSize: t.font.sm }}>
            新浪财经公告列表{data?.name ? ` · ${data.name}` : ""}
          </Text>
        </div>
        <Card
          size="small"
          title={`公告列表（第 ${data?.page ?? page} / ${totalPages || "-"} 页）`}
          extra={<Text type="secondary">来源：新浪财经</Text>}
          style={{ ...cardStyle }}
          styles={{ body: { padding: t.space[4] } }}
        >
          {items.length > 0 ? (
            <ul className="analysis-detail-list">
              {items.map((item) => (
                <BulletinItem key={item.id || `${item.date}-${item.title}`} item={item} />
              ))}
            </ul>
          ) : (
            <div style={{ color: c.textSecondary }}>暂无公告数据</div>
          )}
          {totalPages > 1 && (
            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: t.space[3] }}>
              <Pagination
                size="small"
                simple
                current={page}
                pageSize={BULLETIN_PAGE_SIZE}
                total={totalPages * BULLETIN_PAGE_SIZE}
                onChange={(next) => setPage(next)}
                showSizeChanger={false}
              />
            </div>
          )}
        </Card>
      </div>
    </SectionDataState>
  );
}
