import { useCallback, useEffect, useMemo, useState } from "react";
import { Button, DatePicker, Drawer, Space, Table, Tag, Tooltip } from "antd";
import { AppstoreOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { ColumnsType } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useIndustryRankings, useMarketSectorStocksHistory } from "../../api/queries";
import type { IndustryRankItem, MarketSectorStocksHistoryItem } from "../../types/stock";
import { useColors, useStyles, useTokens } from "../../theme/hooks";
import { normalizeIsoDate } from "../../utils/date";
import { formatAmount, formatMarketCap } from "../../utils/format";
import { rankBadge } from "../../components/rankBadge";

function formatRate(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

interface DrawerSector {
  code: string;
  name: string;
}

function SectorStocksDrawer({
  sector,
  dateText,
  onClose,
}: {
  sector: DrawerSector | null;
  dateText: string;
  onClose: () => void;
}) {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const query = useMarketSectorStocksHistory(sector ? dateText : "", sector?.code ?? "");
  const items = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const hasData = items.length > 0;

  const historyDetailsAvailable = query.data?.history_details_available ?? true;
  const columns: ColumnsType<MarketSectorStocksHistoryItem> = useMemo(() => {
    const stockColumn = {
      title: "股票",
      key: "stock",
      fixed: isNarrow ? undefined : ("left" as const),
      width: 140,
      render: (_value: unknown, stock: MarketSectorStocksHistoryItem) => (
        <StockExternalLink code={stock.code} name={stock.name} style={{ display: "inline-flex" }}>
          <Space orientation="vertical" size={0}>
            <span style={{ fontWeight: Number(t.weight.medium) }}>{stock.name}</span>
            <span style={{ color: c.textSecondary, fontSize: t.font.xs, fontFamily: "var(--c-font-mono)" }}>{stock.code}</span>
          </Space>
        </StockExternalLink>
      ),
    };
    const priceColumn = {
      title: "现价",
      dataIndex: "price",
      width: 80,
      align: "right" as const,
      render: (value: number | null) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{value === null ? "-" : value.toFixed(2)}</span>,
    };
    const changeColumn = {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 90,
      align: "right" as const,
      sorter: (left: MarketSectorStocksHistoryItem, right: MarketSectorStocksHistoryItem) => (
        (left.change_pct ?? 0) - (right.change_pct ?? 0)
      ),
      defaultSortOrder: "descend" as const,
      render: (value: number | null) => <ChangeValue value={value} />,
    };
    const amountColumn = {
      title: "成交额",
      dataIndex: "amount",
      width: 110,
      align: "right" as const,
      render: (value: number | null) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatAmount(value)}</span>,
    };
    const netColumn = {
      title: "主力净额",
      dataIndex: "main_net",
      width: 110,
      align: "right" as const,
      sorter: (left: MarketSectorStocksHistoryItem, right: MarketSectorStocksHistoryItem) => (
        (left.main_net ?? 0) - (right.main_net ?? 0)
      ),
      render: (value: number | null) => (
        <span style={{ color: value != null && value > 0 ? c.up : value != null && value < 0 ? c.down : undefined, fontFamily: "var(--c-font-mono)" }}>
          {formatAmount(value)}
        </span>
      ),
    };

    if (!historyDetailsAvailable) return [stockColumn, priceColumn, changeColumn, amountColumn];
    if (isNarrow) return [stockColumn, changeColumn, netColumn];

    return [
      stockColumn,
      priceColumn,
      changeColumn,
      {
        title: "连板标签",
        dataIndex: "limit_tag",
        width: 100,
        align: "center" as const,
        render: (value: string, stock: MarketSectorStocksHistoryItem) => value ? (
          <Tag style={{ color: c.up }}>{value}{(stock.limit_count ?? 0) > 0 ? ` · ${stock.limit_count}板` : ""}</Tag>
        ) : "-",
      },
      {
        title: "龙虎榜",
        dataIndex: "rank_tag",
        width: 80,
        align: "center" as const,
        render: (value: string) => value || "-",
      },
      amountColumn,
      netColumn,
      {
        title: "换手率",
        dataIndex: "turnover_rate",
        width: 90,
        align: "right" as const,
        render: (value: number | null) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatRate(value)}</span>,
      },
      {
        title: "近期涨幅",
        dataIndex: "recent_chg",
        width: 90,
        align: "right" as const,
        render: (value: number | null) => <ChangeValue value={value} />,
      },
      {
        title: "流通市值",
        dataIndex: "float_amount",
        width: 120,
        align: "right" as const,
        render: (value: number | null) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatMarketCap(value)}</span>,
      },
    ];
  }, [c, historyDetailsAvailable, isNarrow, t]);

  const renderExpandedRow = useCallback((record: MarketSectorStocksHistoryItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "price", label: "现价", value: record.price === null ? "-" : record.price.toFixed(2) },
        { key: "change", label: "涨跌幅", value: <ChangeValue value={record.change_pct} /> },
        { key: "amount", label: "成交额", value: formatAmount(record.amount) },
        { key: "main-net", label: "主力净额", value: formatAmount(record.main_net) },
        { key: "turnover", label: "换手率", value: formatRate(record.turnover_rate) },
        { key: "float-amount", label: "流通市值", value: formatMarketCap(record.float_amount) },
        { key: "recent-chg", label: "近期涨幅", value: <ChangeValue value={record.recent_chg} /> },
        { key: "limit-tag", label: "连板标签", value: record.limit_tag || "-" },
        { key: "rank-tag", label: "龙虎榜", value: record.rank_tag || "-" },
        { key: "tags", label: "概念标签", value: record.tags || "-" },
      ]}
    />
  ), []);

  return (
    <Drawer
      open={Boolean(sector)}
      onClose={onClose}
      width={isNarrow ? "100%" : "min(860px, 100vw)"}
      title={`${sector?.name ?? ""} 成分股 · ${dateText}`}
      destroyOnHidden
    >
      {query.data ? (
        <Space wrap style={{ marginBottom: t.space[3], color: c.textSecondary }}>
          <span>
            {query.data.date === query.data.constituent_date ? "成分日期" : "成分口径"}：
            {query.data.date === query.data.constituent_date ? "" : "开盘红 "}
            {query.data.constituent_date}
          </span>
          {query.data.quoted_at ? <span>行情时间：{query.data.quoted_at}</span> : null}
          {query.data.realtime_partial ? (
            <Tag color="warning">
              {query.data.is_realtime ? "部分成分股暂无当天行情" : "当天行情暂不可用，未回退历史交易数据"}
            </Tag>
          ) : null}
          {query.data.history_details_available && query.data.date !== query.data.constituent_date ? (
            <Tag>非交易日，展示最近交易日数据</Tag>
          ) : null}
        </Space>
      ) : null}
      <SectionDataState
        isLoading={query.isLoading && !hasData}
        error={hasData ? undefined : query.error}
        onRetry={() => query.refetch()}
        isEmpty={!query.isLoading && !query.error && !hasData}
        emptyText={`${dateText} 暂无 ${sector?.name ?? ""} 成分股数据`}
        errorTitle="成分股加载失败"
        minHeight={320}
        skeletonRows={8}
      >
        <Table<MarketSectorStocksHistoryItem>
          rowKey="code"
          columns={columns}
          dataSource={items}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          expandable={isNarrow && historyDetailsAvailable ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 36,
          } : undefined}
          scroll={{ x: isNarrow ? 340 : (historyDetailsAvailable ? 800 : 500) }}
          size="small"
        />
      </SectionDataState>
    </Drawer>
  );
}

export default function IndustryRankTab() {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { cardStyle } = useStyles();
  const today = dayjs().format("YYYY-MM-DD");
  const [dateParam, setDate] = useUrlSearchParam("industryDate", today, { replace: true });
  const normalizedDate = normalizeIsoDate(dateParam, today);
  const dateText = dayjs(normalizedDate).isAfter(dayjs(), "day") ? today : normalizedDate;
  const selectedDate = dayjs(dateText);

  useEffect(() => {
    if (dateParam !== dateText) setDate(dateText);
  }, [dateParam, dateText, setDate]);

  const { data, isLoading, isFetching, error, refetch } = useIndustryRankings(dateText);
  const sectors = useMemo(() => data?.sectors ?? [], [data?.sectors]);
  const hasData = sectors.length > 0;
  const source = data?.source || "未知";
  const actualDate = data?.date || dateText;
  const dateWasResolved = hasData && actualDate !== dateText;
  const isKaipanhongSource = source === "开盘红" && (data?.fund_data_available ?? false);
  const drillDownDisabled = !isKaipanhongSource;
  const drillDownTooltip = "当前数据来自降级数据源，仅开盘红数据支持查看成分股";
  const [drawerSector, setDrawerSector] = useState<DrawerSector | null>(null);

  const columns: ColumnsType<IndustryRankItem> = useMemo(() => {
    const stocksActionColumn = {
      title: "成分股",
      key: "stocks-action",
      width: isNarrow ? 78 : 90,
      align: "center" as const,
      render: (_value: unknown, record: IndustryRankItem) => {
        if (!record.code) return null;
        if (drillDownDisabled) {
          return (
            <Tooltip title={drillDownTooltip}>
              <Button type="link" size="small" disabled>
                成分股
              </Button>
            </Tooltip>
          );
        }
        return (
          <Button
            type="link"
            size="small"
            onClick={() => setDrawerSector({ code: record.code, name: record.name })}
          >
            成分股
          </Button>
        );
      },
    };
    const industryColumn = {
      title: "行业",
      dataIndex: "name",
      width: isNarrow ? 130 : 140,
      ellipsis: true,
      render: (value: string, record: IndustryRankItem) => (
        <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
          {isNarrow ? rankBadge(record.rank, c, t) : null}
          <span style={{ minWidth: 0, color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>
            {value}
          </span>
        </div>
      ),
    };
    const changeColumn = {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: isNarrow ? 78 : 90,
      align: "right" as const,
      sorter: (left: IndustryRankItem, right: IndustryRankItem) => (
        (left.change_pct ?? 0) - (right.change_pct ?? 0)
      ),
      defaultSortOrder: "descend" as const,
      render: (value: number | null) => (
        <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />
      ),
    };
    const netColumn = {
      title: "净流入",
      dataIndex: "net_inflow",
      width: isNarrow ? 96 : 110,
      align: "right" as const,
      sorter: (left: IndustryRankItem, right: IndustryRankItem) => (
        (left.net_inflow ?? 0) - (right.net_inflow ?? 0)
      ),
      render: (value: number | null) => (
        <span style={{ color: value == null ? c.textSecondary : value >= 0 ? c.up : c.down, fontFamily: "var(--c-font-mono)" }}>
          {formatAmount(value)}
        </span>
      ),
    };

    if (isNarrow) return [industryColumn, changeColumn, netColumn, stocksActionColumn];

    return [
      {
        title: "排名",
        dataIndex: "rank",
        width: 60,
        align: "center",
        render: (rank: number | null) => rankBadge(rank, c, t),
      },
      industryColumn,
      changeColumn,
      {
        title: "平均涨幅",
        dataIndex: "avg_change",
        width: 90,
        align: "right",
        render: (value: number | null) => <ChangeValue value={value} />,
      },
      { title: "成交额", dataIndex: "amount", width: 110, align: "right", render: (val) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatAmount(val)}</span> },
      netColumn,
      {
        title: "主买",
        dataIndex: "buy_amount",
        width: 110,
        align: "right",
        render: (value: number | null) => <span style={{ color: c.up, fontFamily: "var(--c-font-mono)" }}>{formatAmount(value)}</span>,
      },
      {
        title: "主卖",
        dataIndex: "sell_amount",
        width: 110,
        align: "right",
        render: (value: number | null) => <span style={{ color: c.down, fontFamily: "var(--c-font-mono)" }}>{formatAmount(value)}</span>,
      },
      { title: "换手率", dataIndex: "turnover_rate", width: 90, align: "right", render: (val) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatRate(val)}</span> },
      { title: "行业市值", dataIndex: "market_cap", width: 120, align: "right", render: (val) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatMarketCap(val)}</span> },
      stocksActionColumn,
    ];
  }, [c, isNarrow, drillDownDisabled, drillDownTooltip, t]);

  const renderExpandedRow = useCallback((record: IndustryRankItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "average", label: "平均涨幅", value: <ChangeValue value={record.avg_change} /> },
        { key: "amount", label: "成交额", value: formatAmount(record.amount) },
        { key: "buy", label: "主买金额", value: formatAmount(record.buy_amount) },
        { key: "sell", label: "主卖金额", value: formatAmount(record.sell_amount) },
        { key: "turnover", label: "换手率", value: formatRate(record.turnover_rate) },
        { key: "market-cap", label: "行业市值", value: formatMarketCap(record.market_cap) },
        { key: "up", label: "上涨家数", value: record.up_count ?? "-" },
        { key: "down", label: "下跌家数", value: record.down_count ?? "-" },
        { key: "leader", label: "领涨股", value: record.leader || "-" },
      ]}
    />
  ), []);

  return (
    <div style={{ ...cardStyle, padding: 0, borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
      <div
        style={{
          padding: `${t.space[3]} ${t.space[4]}`,
          borderBottom: `1px solid ${c.border}`,
          display: "flex",
          alignItems: "center",
          gap: t.space[2],
          flexWrap: "wrap",
        }}
      >
        <AppstoreOutlined style={{ color: c.primary }} />
        <span style={{ color: c.textPrimary, fontWeight: Number(t.weight.medium) }}>
          行业资金与涨跌排行
        </span>
        <Tag>{source}</Tag>
        {!data?.fund_data_available ? <Tag color="warning">资金数据降级</Tag> : null}
        {dateWasResolved ? <Tag color="warning">已回退至最近交易日</Tag> : null}
        <span style={{ color: c.textSecondary, fontSize: t.font.sm }}>
          数据日期：{actualDate}
        </span>
        <Space wrap style={{ marginLeft: "auto" }}>
          <DatePicker
            aria-label="行业排行日期"
            value={selectedDate}
            allowClear={false}
            disabledDate={(current) => current.isAfter(dayjs(), "day")}
            onChange={(value) => value && setDate(value.format("YYYY-MM-DD"))}
          />
          <DataRefreshIndicator active={isFetching && !isLoading} />
        </Space>
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText={`${dateText} 暂无行业排名数据`}
        errorTitle="行业排名加载失败"
        minHeight={320}
      >
        <Table<IndustryRankItem>
          columns={columns}
          dataSource={sectors}
          rowKey="code"
          pagination={false}
          virtual
          expandable={isNarrow ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 36,
          } : undefined}
          scroll={{ x: isNarrow ? 360 : 1180, y: 600 }}
          size="small"
          style={{ background: "transparent" }}
        />
      </SectionDataState>
      <SectorStocksDrawer
        sector={drawerSector}
        dateText={actualDate}
        onClose={() => setDrawerSector(null)}
      />
    </div>
  );
}
