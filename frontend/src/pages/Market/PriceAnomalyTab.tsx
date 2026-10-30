import { useMemo, useState } from "react";
import { ReloadOutlined } from "@ant-design/icons";
import { Button, Card, Col, Pagination, Row, Segmented, Statistic, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  useMarketPriceAnomaly,
  useMarketPriceAnomalyCount,
} from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import SectionToolbar from "../../components/SectionToolbar";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens } from "../../styles/ui";
import type {
  MarketPriceAnomalyCountItem,
  MarketPriceAnomalyExchange,
  MarketPriceAnomalyItem,
} from "../../types/stock";
import "./market-price-anomaly.css";

const { Text } = Typography;
type AnomalyView = "detail" | "count";

const EXCHANGE_LABELS: Record<MarketPriceAnomalyExchange, string> = {
  SH: "上交所",
  SZ: "深交所",
  BJ: "北交所",
};

function formatDate(value: string | undefined) {
  if (!value) return "-";
  const compact = value.match(/^(\d{4})(\d{2})(\d{2})$/);
  return compact ? `${compact[1]}-${compact[2]}-${compact[3]}` : value;
}

function shanghaiToday() {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

function formatNumber(value: number | null | undefined, suffix = "") {
  return value == null ? "-" : `${value.toFixed(2)}${suffix}`;
}

function ChangeValue({ value }: { value: number | null | undefined }) {
  const c = useColors();
  if (value == null) return <>-</>;
  return (
    <span style={{ color: value > 0 ? c.up : value < 0 ? c.down : c.textSecondary, fontFamily: "var(--c-font-mono)" }}>
      {value > 0 ? "+" : ""}{value.toFixed(2)}%
    </span>
  );
}

function StockCell({ code, name }: { code: string; name: string }) {
  const c = useColors();
  const t = useTokens();
  return (
    <StockExternalLink code={code} name={name} className="market-price-anomaly__stock">
      <span style={{ color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{name || "-"}</span>
      <span style={{ color: c.textMuted, fontFamily: "var(--c-font-mono)" }}>{code}</span>
    </StockExternalLink>
  );
}

function ExchangeTag({ market }: { market: MarketPriceAnomalyExchange }) {
  const color = market === "SH" ? "red" : market === "SZ" ? "blue" : "purple";
  return <Tag color={color}>{EXCHANGE_LABELS[market]}</Tag>;
}

export default function PriceAnomalyTab() {
  const c = useColors();
  const t = useTokens();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const [view, setView] = useUrlSearchParam<AnomalyView>("view", "detail", {
    allowedValues: ["detail", "count"],
  });
  const [detailPage, setDetailPage] = useState(1);
  const [countPage, setCountPage] = useState(1);
  const detailQuery = useMarketPriceAnomaly(detailPage, 200, view === "detail");
  const countQuery = useMarketPriceAnomalyCount(countPage, 50, "", "", view === "count");
  const isDetail = view === "detail";
  const data = isDetail ? detailQuery.data : countQuery.data;
  const dataDate = formatDate(data?.date);
  const isCurrentDataDate = dataDate !== "-" && dataDate === shanghaiToday();

  const detailColumns: ColumnsType<MarketPriceAnomalyItem> = useMemo(() => [
    {
      title: "股票",
      key: "stock",
      fixed: isMobile ? undefined : "left",
      width: 138,
      render: (_value, record) => <StockCell code={record.code} name={record.name} />,
    },
    {
      title: "交易所",
      dataIndex: "market",
      width: 86,
      render: (market: MarketPriceAnomalyExchange) => <ExchangeTag market={market} />,
    },
    {
      title: "当日涨跌幅",
      dataIndex: "change_pct",
      width: 108,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "累计偏离值",
      dataIndex: "deviation",
      width: 108,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "统计窗口",
      dataIndex: "days",
      width: 92,
      align: "right",
      render: (value: number | null) => value == null ? "-" : `${value}日`,
    },
    {
      title: "触发规则",
      dataIndex: "rule",
      minWidth: 280,
      render: (value: string) => value || "-",
    },
    {
      title: "状态",
      dataIndex: "is_today",
      width: 86,
      render: (value: boolean) => value
        ? <Tag color="error">{isCurrentDataDate ? "今日异动" : "数据日异动"}</Tag>
        : <Tag>窗口记录</Tag>,
    },
  ], [isCurrentDataDate, isMobile]);

  const countColumns: ColumnsType<MarketPriceAnomalyCountItem> = useMemo(() => [
    {
      title: "股票",
      key: "stock",
      fixed: isMobile ? undefined : "left",
      width: 138,
      render: (_value, record) => <StockCell code={record.code} name={record.name} />,
    },
    {
      title: "交易所",
      dataIndex: "market",
      width: 86,
      render: (market: MarketPriceAnomalyExchange) => <ExchangeTag market={market} />,
    },
    {
      title: "最新价",
      dataIndex: "price",
      width: 90,
      align: "right",
      render: (value: number | null) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatNumber(value)}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 92,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "异动次数",
      dataIndex: "times",
      width: 92,
      align: "right",
      render: (value: number | null) => value == null ? "-" : <span style={{ fontFamily: "var(--c-font-mono)" }}>{value}次</span>,
    },
    {
      title: "累计偏离值",
      dataIndex: "deviation",
      width: 108,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} />,
    },
    {
      title: "统计窗口",
      dataIndex: "days",
      width: 92,
      align: "right",
      render: (value: number | null) => value == null ? "-" : `${value}日`,
    },
  ], [isMobile]);

  const query = isDetail ? detailQuery : countQuery;
  const items = isDetail ? detailQuery.data?.items ?? [] : countQuery.data?.items ?? [];
  const page = isDetail ? detailPage : countPage;
  const pageSize = isDetail ? 200 : 50;
  const pages = data?.pages ?? 0;
  const paginationTotal = pages > 0
    ? (pages - 1) * pageSize + (page === pages ? items.length : pageSize)
    : 0;
  const todayCount = detailQuery.data?.items.filter((item) => item.is_today).length ?? 0;
  const anomalyTimes = countQuery.data?.items.reduce((sum, item) => sum + (item.times ?? 0), 0) ?? 0;
  const fallbackHint = data?.is_stale
    ? (isCurrentDataDate ? "当前为本地快照" : "已回退至最近数据日")
    : (data?.date && !isCurrentDataDate ? "已回退至最近数据日" : "");

  return (
    <div className="market-price-anomaly">
      <SectionToolbar
        ariaLabel="交易所异动工具条"
        meta={
          <Segmented<AnomalyView>
            value={view}
            options={[
              { label: "异动明细", value: "detail" },
              { label: "异动统计", value: "count" },
            ]}
            onChange={setView}
          />
        }
        actions={
          <>
            <Text type="secondary">数据日期：{dataDate}</Text>
            {fallbackHint ? <Tag color="warning">{fallbackHint}</Tag> : null}
            {query.isFetching ? <Tag color="processing">更新中</Tag> : null}
            <Button icon={<ReloadOutlined />} onClick={() => query.refetch()} loading={query.isFetching}>
              刷新
            </Button>
          </>
        }
      />

      <Row gutter={[12, 12]} className="market-price-anomaly__metrics">
        <Col xs={12} sm={8}>
          <Card size="small" style={{ borderRadius: t.radius?.md || 8, boxShadow: t.shadow?.xs }}>
            <Statistic title={isDetail ? "本页异动记录" : "本页异动股票"} value={items.length} styles={{ content: { fontFamily: "var(--c-font-mono)" } }} />
          </Card>
        </Col>
        <Col xs={12} sm={8}>
          <Card size="small" style={{ borderRadius: t.radius?.md || 8, boxShadow: t.shadow?.xs }}>
            <Statistic
              title={isDetail ? (isCurrentDataDate ? "今日触发" : "数据日触发") : "本页异动次数"}
              value={isDetail ? todayCount : anomalyTimes}
              styles={{ content: { color: c.warning, fontFamily: "var(--c-font-mono)", fontWeight: 600 } }}
            />
          </Card>
        </Col>
        <Col xs={24} sm={8}>
          <Card size="small" style={{ borderRadius: t.radius?.md || 8, boxShadow: t.shadow?.xs }}>
            <Statistic title="数据来源" value={data?.source ?? "东方财富"} />
          </Card>
        </Col>
      </Row>

      <SectionDataState
        isLoading={query.isLoading && items.length === 0}
        error={items.length > 0 ? undefined : query.error}
        onRetry={() => query.refetch()}
        isEmpty={!query.isLoading && !query.error && items.length === 0}
        emptyText={isDetail ? "暂无交易所异动明细" : "暂无交易所异动统计"}
        errorTitle="交易所异动数据加载失败"
        minHeight={360}
        skeletonRows={8}
      >
        <Card size="small" style={{ borderRadius: t.radius?.md || 8, boxShadow: t.shadow?.xs, padding: 0 }}>
          {isDetail ? (
            <Table<MarketPriceAnomalyItem>
              rowKey={(record) => `${record.market}-${record.code}-${record.rule_code}`}
              columns={detailColumns}
              dataSource={detailQuery.data?.items ?? []}
              pagination={false}
              scroll={{ x: 930 }}
              size="small"
            />
          ) : (
            <Table<MarketPriceAnomalyCountItem>
              rowKey={(record) => `${record.market}-${record.code}`}
              columns={countColumns}
              dataSource={countQuery.data?.items ?? []}
              pagination={false}
              scroll={{ x: 700 }}
              size="small"
            />
          )}
          {pages > 1 ? (
            <Pagination
              className="market-price-anomaly__pagination"
              current={page}
              pageSize={pageSize}
              total={paginationTotal}
              showSizeChanger={false}
              showLessItems
              simple={isMobile}
              onChange={isDetail ? setDetailPage : setCountPage}
              style={{ padding: 12 }}
            />
          ) : null}
        </Card>
      </SectionDataState>
    </div>
  );
}
