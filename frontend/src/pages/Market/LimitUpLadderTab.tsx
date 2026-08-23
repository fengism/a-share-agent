import { useEffect, useMemo } from "react";
import { Button, Card, Col, DatePicker, Row, Segmented, Space, Statistic, Table, Tag, Typography } from "antd";
import { FireOutlined, ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { useMarketLimitUpLadder } from "../../api/queries";
import RefreshBadge from "../../components/RefreshBadge";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import type { MarketLimitUpLadderStock } from "../../types/stock";
import { normalizeIsoDate } from "../../utils/date";
import { formatAmount } from "../../utils/format";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import LimitHistoryPanel from "./LimitHistoryPanel";

const { Text, Title } = Typography;

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function LimitUpLadderContent() {
  const colors = useColors();
  const t = useTokens();
  const today = dayjs().format("YYYY-MM-DD");
  const [dateParam, setDate] = useUrlSearchParam("date", today, { replace: true });
  const normalizedDate = normalizeIsoDate(dateParam, today);
  const dateText = dayjs(normalizedDate).isAfter(dayjs(), "day") ? today : normalizedDate;
  const selectedDate = dayjs(dateText);

  useEffect(() => {
    if (dateParam !== dateText) setDate(dateText);
  }, [dateParam, dateText, setDate]);

  const query = useMarketLimitUpLadder(dateText);
  const stocks = useMemo(() => query.data?.stocks ?? [], [query.data?.stocks]);
  const sectors = useMemo(() => query.data?.sectors ?? [], [query.data?.sectors]);
  const hasData = stocks.length > 0 || sectors.length > 0;
  const maxBoardCount = Math.max(0, ...stocks.map((stock) => stock.board_count));
  const oneWordCount = stocks.filter((stock) => stock.one_word).length;
  const popularCount = stocks.filter((stock) => stock.popular).length;

  const columns: ColumnsType<MarketLimitUpLadderStock> = useMemo(() => [
    {
      title: "股票",
      key: "stock",
      width: 150,
      render: (_value: unknown, stock: MarketLimitUpLadderStock) => (
        <StockExternalLink code={stock.code} name={stock.name} style={{ display: "inline-flex" }}>
          <Space orientation="vertical" size={0}>
            <Text strong>{stock.name}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>{stock.code}</Text>
          </Space>
        </StockExternalLink>
      ),
    },
    {
      title: "连板高度",
      dataIndex: "board_count",
      width: 100,
      align: "center",
      defaultSortOrder: "descend",
      sorter: (left, right) => left.board_count - right.board_count,
      render: (value: number) => <Tag style={semanticTagStyle("up")}>{value}连板</Tag>,
    },
    {
      title: "涨停时间",
      dataIndex: "limit_up_time",
      width: 100,
      align: "center",
      render: (value: string) => value || "-",
    },
    {
      title: "所属板块",
      dataIndex: "sector_name",
      width: 130,
      ellipsis: true,
      render: (value: string, stock) => (
        <Space size={4}>
          <span>{value || "其他"}</span>
          {stock.sector_limit_up_count > 0 ? <Tag>{stock.sector_limit_up_count}只</Tag> : null}
        </Space>
      ),
    },
    {
      title: "特征",
      key: "tags",
      width: 170,
      render: (_value: unknown, stock: MarketLimitUpLadderStock) => (
        <Space size={[4, 4]} wrap>
          {stock.one_word ? <Tag style={semanticTagStyle("warning")}>大单一字</Tag> : null}
          {stock.popular ? <Tag style={semanticTagStyle("primary")}>人气股</Tag> : null}
          {!stock.one_word && !stock.popular ? "-" : null}
        </Space>
      ),
    },
    {
      title: "成交额",
      dataIndex: "amount",
      width: 110,
      align: "right",
      render: (value: number) => formatAmount(value),
    },
  ], []);

  return (
    <SectionDataState
      isLoading={query.isLoading && !hasData}
      error={hasData ? undefined : query.error}
      onRetry={() => query.refetch()}
      isEmpty={!query.isLoading && !query.error && !hasData}
      emptyText="暂无涨停板数据"
      errorTitle="涨停板加载失败"
      minHeight={480}
      skeletonRows={10}
    >
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: t.space[4], marginBottom: t.space[4], flexWrap: "wrap" }}>
          <Space size={parseFloat(t.space[3])} wrap>
            <Title level={4} style={{ margin: 0 }}><FireOutlined style={{ color: colors.up }} /> 涨停板</Title>
            <Text type="secondary">数据日期：{query.data?.date || dateText}</Text>
            <Text type="secondary">更新时间：{formatFetchedAt(query.data?.fetched_at)}</Text>
            <RefreshBadge />
          </Space>
          <Space>
            <DatePicker
              aria-label="涨停板日期"
              value={selectedDate}
              allowClear={false}
              disabledDate={(current) => current.isAfter(dayjs(), "day")}
              onChange={(value) => value && setDate(value.format("YYYY-MM-DD"))}
            />
            <Button icon={<ReloadOutlined />} loading={query.isFetching} onClick={() => query.refetch()}>
              刷新
            </Button>
          </Space>
        </div>

        <Row gutter={[16, 16]} style={{ marginBottom: t.space[4] }}>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic title="涨停家数" value={query.data?.total ?? stocks.length} suffix="家" styles={{ content: { color: colors.up } }} />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic title="最高连板" value={maxBoardCount} suffix="板" styles={{ content: { color: colors.up } }} />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic title="大单一字" value={oneWordCount} suffix="家" />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic title="人气股" value={popularCount} suffix="家" />
            </Card>
          </Col>
        </Row>

        <Card title="板块涨停分布" style={{ marginBottom: t.space[4], borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
          <Row gutter={[12, 12]}>
            {sectors.map((sector) => (
              <Col xs={12} md={8} xl={6} key={`${sector.sector_code}-${sector.sector_name}`}>
                <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, background: colors.nestedBg, boxShadow: t.shadow.xs }}>
                  <Space orientation="vertical" size={4}>
                    <Text strong>{sector.sector_name}</Text>
                    <Text style={{ color: colors.up }}>{sector.stock_count} 家涨停</Text>
                    <Text type="secondary">成交额 {formatAmount(sector.amount)}</Text>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card title="涨停天梯" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
          <Table<MarketLimitUpLadderStock>
            rowKey="code"
            columns={columns}
            dataSource={stocks}
            pagination={{ pageSize: 20, showSizeChanger: false }}
            scroll={{ x: 780 }}
            size="middle"
          />
        </Card>
      </div>
    </SectionDataState>
  );
}

const LIMIT_UP_MODES = ["ladder", "history"] as const;

export default function LimitUpLadderTab() {
  const t = useTokens();
  const [mode, setMode] = useUrlSearchParam("mode", "ladder", {
    allowedValues: LIMIT_UP_MODES,
    replace: true,
  });

  return (
    <div>
      <Segmented
        aria-label="涨停板模式"
        value={mode}
        onChange={(value) => setMode(String(value))}
        options={[
          { value: "ladder", label: "涨停天梯" },
          { value: "history", label: "历史复盘" },
        ]}
        style={{ marginBottom: t.space[4] }}
      />
      {mode === "history" ? <LimitHistoryPanel /> : <LimitUpLadderContent />}
    </div>
  );
}
