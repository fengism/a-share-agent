import { useEffect, useMemo } from "react";
import { Button, Card, Col, DatePicker, Row, Segmented, Space, Statistic, Table, Tag, Typography } from "antd";
import { FireOutlined, ReloadOutlined, ThunderboltOutlined, TrophyOutlined } from "@ant-design/icons";
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

function getLadderTagStyle(boardCount: number, colors: ReturnType<typeof useColors>) {
  if (boardCount >= 5) {
    return {
      background: "linear-gradient(135deg, rgba(200, 52, 31, 0.15), rgba(247, 144, 9, 0.15))",
      color: colors.down,
      borderColor: colors.down,
      fontWeight: 700,
    };
  }
  if (boardCount >= 3) {
    return {
      background: "rgba(200, 52, 31, 0.1)",
      color: colors.up,
      borderColor: colors.up,
      fontWeight: 600,
    };
  }
  return semanticTagStyle("up");
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
            <Text strong style={{ fontSize: t.font.md }}>{stock.name}</Text>
            <Text type="secondary" style={{ fontSize: t.font.xs, fontFamily: "var(--c-font-mono)" }}>{stock.code}</Text>
          </Space>
        </StockExternalLink>
      ),
    },
    {
      title: "连板高度",
      dataIndex: "board_count",
      width: 110,
      align: "center",
      defaultSortOrder: "descend",
      sorter: (left, right) => left.board_count - right.board_count,
      render: (value: number) => (
        <Tag style={getLadderTagStyle(value, colors)}>
          {value}连板
        </Tag>
      ),
    },
    {
      title: "涨停时间",
      dataIndex: "limit_up_time",
      width: 100,
      align: "center",
      render: (value: string) => <span style={{ fontFamily: "var(--c-font-mono)" }}>{value || "-"}</span>,
    },
    {
      title: "所属板块",
      dataIndex: "sector_name",
      width: 150,
      ellipsis: true,
      render: (value: string, stock) => (
        <Space size={6}>
          <span style={{ fontWeight: Number(t.weight.medium) }}>{value || "其他"}</span>
          {stock.sector_limit_up_count > 0 ? (
            <Tag style={{ borderRadius: 10, padding: "0 6px", fontSize: t.font.xs }}>
              {stock.sector_limit_up_count}只
            </Tag>
          ) : null}
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
          {!stock.one_word && !stock.popular ? <span style={{ color: colors.textMuted }}>-</span> : null}
        </Space>
      ),
    },
    {
      title: "成交额",
      dataIndex: "amount",
      width: 110,
      align: "right",
      render: (value: number) => (
        <span style={{ fontFamily: "var(--c-font-mono)", fontWeight: Number(t.weight.medium) }}>
          {formatAmount(value)}
        </span>
      ),
    },
  ], [colors, t]);

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
            <Title level={4} style={{ margin: 0, display: "inline-flex", alignItems: "center", gap: 6 }}>
              <FireOutlined style={{ color: colors.up }} /> 涨停板
            </Title>
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
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs, borderLeft: `3px solid ${colors.up}` }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: colors.textSecondary }}><FireOutlined /> 涨停家数</span>}
                value={query.data?.total ?? stocks.length}
                suffix="家"
                styles={{ content: { color: colors.up, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs, borderLeft: `3px solid ${colors.accent}` }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: colors.textSecondary }}><TrophyOutlined /> 最高连板</span>}
                value={maxBoardCount}
                suffix="板"
                styles={{ content: { color: colors.up, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: colors.textSecondary }}><ThunderboltOutlined /> 大单一字</span>}
                value={oneWordCount}
                suffix="家"
                styles={{ content: { color: colors.warning, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" style={{ height: "100%", borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ fontSize: t.font.sm, color: colors.textSecondary }}>人气股</span>}
                value={popularCount}
                suffix="家"
                styles={{ content: { color: colors.primary, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title={<span style={{ fontWeight: Number(t.weight.semibold) }}>板块涨停分布</span>}
          style={{ marginBottom: t.space[4], borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
        >
          <Row gutter={[12, 12]}>
            {sectors.map((sector, index) => (
              <Col xs={12} md={8} xl={6} key={`${sector.sector_code}-${sector.sector_name}`}>
                <Card
                  size="small"
                  style={{
                    height: "100%",
                    borderRadius: t.radius.md,
                    background: colors.nestedBg,
                    border: `1px solid ${colors.border}`,
                    boxShadow: t.shadow.xs,
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 6 }}>
                    <Text strong style={{ fontSize: t.font.md }}>{sector.sector_name}</Text>
                    <Tag style={{ borderRadius: 10, margin: 0, padding: "0 6px", fontSize: t.font.xs }}>
                      TOP {index + 1}
                    </Tag>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <Text style={{ color: colors.up, fontWeight: Number(t.weight.bold) }}>{sector.stock_count} 家涨停</Text>
                    <Text type="secondary" style={{ fontSize: t.font.xs }}>{formatAmount(sector.amount)}</Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card
          title={<span style={{ fontWeight: Number(t.weight.semibold) }}>涨停天梯</span>}
          style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
        >
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
