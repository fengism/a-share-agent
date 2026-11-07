import { useCallback, useEffect, useMemo } from "react";
import { Button, Card, Col, DatePicker, Row, Segmented, Space, Statistic, Table, Tag, Typography } from "antd";
import { FireOutlined, ReloadOutlined, ThunderboltOutlined, TrophyOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { useMarketLimitUpLadder } from "../../api/queries";
import RefreshBadge from "../../components/RefreshBadge";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import SectionToolbar from "../../components/SectionToolbar";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import type { MarketLimitUpLadderStock } from "../../types/stock";
import { normalizeIsoDate } from "../../utils/date";
import { formatAmount } from "../../utils/format";
import { formatMarketDateTime } from "../../utils/marketTime";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import LimitHistoryPanel from "./LimitHistoryPanel";
import "./limit-up-ladder.css";

const { Text } = Typography;

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  return formatMarketDateTime(value, value);
}

function getLadderTagClass(boardCount: number) {
  if (boardCount >= 5) return "ladder-tag--5plus";
  if (boardCount >= 3) return "ladder-tag--3plus";
  return "";
}

function LimitUpLadderContent() {
  const colors = useColors();
  const t = useTokens();
  const isMobile = useMediaQuery("(max-width: 768px)");
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

  const renderExpandedRow = useCallback((stock: MarketLimitUpLadderStock) => (
    <ResponsiveMetricGrid
      items={[
        {
          key: "sector",
          label: "所属板块",
          value: `${stock.sector_name || "其他"}${stock.sector_limit_up_count > 0 ? ` (${stock.sector_limit_up_count}只)` : ""}`,
        },
        {
          key: "features",
          label: "特征",
          value: (
            <Space size={[4, 4]} wrap>
              {stock.one_word ? <Tag style={semanticTagStyle("warning")}>大单一字</Tag> : null}
              {stock.popular ? <Tag style={semanticTagStyle("primary")}>人气股</Tag> : null}
              {!stock.one_word && !stock.popular ? "-" : null}
            </Space>
          ),
        },
        { key: "amount", label: "成交额", value: formatAmount(stock.amount) },
        { key: "limit_up_time", label: "涨停时间", value: stock.limit_up_time || "-" },
      ]}
    />
  ), []);

  const columns: ColumnsType<MarketLimitUpLadderStock> = useMemo(() => {
    if (isMobile) {
      return [
        {
          title: "股票",
          key: "stock",
          width: 140,
          render: (_value: unknown, stock: MarketLimitUpLadderStock) => (
            <StockExternalLink code={stock.code} name={stock.name} className="ladder-stock-link">
              <Space orientation="vertical" size={0}>
                <Text strong className="ladder-stock-name">{stock.name}</Text>
                <Space size={4} wrap>
                  <Text type="secondary" className="ladder-stock-code">{stock.code}</Text>
                  {stock.sector_name && (
                    <Text type="secondary" className="ladder-stock-sector">· {stock.sector_name}</Text>
                  )}
                </Space>
              </Space>
            </StockExternalLink>
          ),
        },
        {
          title: "连板高度",
          dataIndex: "board_count",
          width: 86,
          align: "center",
          defaultSortOrder: "descend",
          sorter: (left, right) => left.board_count - right.board_count,
          render: (value: number) => {
            const tagClass = getLadderTagClass(value);
            return (
              <Tag style={tagClass ? undefined : semanticTagStyle("up")} className={tagClass || undefined}>
                {value}连板
              </Tag>
            );
          },
        },
        {
          title: "涨停时间",
          dataIndex: "limit_up_time",
          width: 86,
          align: "center",
          render: (value: string) => <span className="ladder-time-text">{value || "-"}</span>,
        },
      ];
    }

    return [
      {
        title: "股票",
        key: "stock",
        width: 150,
        fixed: "left",
        render: (_value: unknown, stock: MarketLimitUpLadderStock) => (
          <StockExternalLink code={stock.code} name={stock.name} className="ladder-stock-link">
            <Space orientation="vertical" size={0}>
              <Text strong className="ladder-stock-name">{stock.name}</Text>
              <Text type="secondary" className="ladder-stock-code">{stock.code}</Text>
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
        render: (value: number) => {
          const tagClass = getLadderTagClass(value);
          return (
            <Tag style={tagClass ? undefined : semanticTagStyle("up")} className={tagClass || undefined}>
              {value}连板
            </Tag>
          );
        },
      },
      {
        title: "涨停时间",
        dataIndex: "limit_up_time",
        width: 100,
        align: "center",
        render: (value: string) => <span className="ladder-mono">{value || "-"}</span>,
      },
      {
        title: "所属板块",
        dataIndex: "sector_name",
        width: 150,
        ellipsis: true,
        render: (value: string, stock) => (
          <Space size={6}>
            <span className="ladder-font-medium">{value || "其他"}</span>
            {stock.sector_limit_up_count > 0 ? (
              <Tag className="ladder-count-tag">
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
            {!stock.one_word && !stock.popular ? <span className="ladder-muted-dash">-</span> : null}
          </Space>
        ),
      },
      {
        title: "成交额",
        dataIndex: "amount",
        width: 110,
        align: "right",
        render: (value: number) => (
          <span className="ladder-amount-text">
            {formatAmount(value)}
          </span>
        ),
      },
    ];
  }, [isMobile]);

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
        <div className="u-mb-16">
          <SectionToolbar
            ariaLabel="涨停板工具条"
            meta={
              <Space size={parseFloat(t.space[3])} wrap>
                <span className="ladder-toolbar-title">
                  <FireOutlined className="ladder-fire-icon" /> 涨停板
                </span>
                <Text type="secondary">数据日期：{query.data?.date || dateText}</Text>
                <Text type="secondary">更新时间：{formatFetchedAt(query.data?.fetched_at)}</Text>
                <RefreshBadge />
              </Space>
            }
            actions={
              <Space wrap>
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
            }
          />
        </div>

        <Row gutter={[16, 16]} className="u-mb-16">
          <Col xs={12} lg={6}>
            <Card size="small" className="ladder-stat-card ladder-stat-card--up">
              <Statistic
                title={<span className="ladder-stat-title"><FireOutlined /> 涨停家数</span>}
                value={query.data?.total ?? stocks.length}
                suffix="家"
                styles={{ content: { color: colors.up, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" className="ladder-stat-card ladder-stat-card--accent">
              <Statistic
                title={<span className="ladder-stat-title"><TrophyOutlined /> 最高连板</span>}
                value={maxBoardCount}
                suffix="板"
                styles={{ content: { color: colors.up, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" className="ladder-stat-card">
              <Statistic
                title={<span className="ladder-stat-title"><ThunderboltOutlined /> 大单一字</span>}
                value={oneWordCount}
                suffix="家"
                styles={{ content: { color: colors.warning, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} lg={6}>
            <Card size="small" className="ladder-stat-card">
              <Statistic
                title={<span className="ladder-stat-title">人气股</span>}
                value={popularCount}
                suffix="家"
                styles={{ content: { color: colors.primary, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
        </Row>

        <Card
          title={<span className="ladder-card-title">板块涨停分布</span>}
          className="ladder-block-card u-mb-16"
        >
          <Row gutter={[12, 12]}>
            {sectors.map((sector, index) => (
              <Col xs={12} md={8} xl={6} key={`${sector.sector_code}-${sector.sector_name}`}>
                <Card
                  size="small"
                  className="ladder-sector-card"
                >
                  <div className="ladder-sector-header">
                    <Text strong className="ladder-sector-name">{sector.sector_name}</Text>
                    <Tag className="ladder-top-tag">
                      TOP {index + 1}
                    </Tag>
                  </div>
                  <div className="ladder-sector-footer">
                    <Text className="ladder-sector-count">{sector.stock_count} 家涨停</Text>
                    <Text type="secondary" className="ladder-sector-amount">{formatAmount(sector.amount)}</Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>
        </Card>

        <Card
          title={<span className="ladder-card-title">涨停天梯</span>}
          className="ladder-block-card"
        >
          <Table<MarketLimitUpLadderStock>
            rowKey="code"
            columns={columns}
            dataSource={stocks}
            pagination={{ pageSize: 20, showSizeChanger: !isMobile, simple: isMobile }}
            expandable={isMobile ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 38,
            } : undefined}
            scroll={isMobile ? undefined : { x: 780 }}
            size="middle"
          />
        </Card>
      </div>
    </SectionDataState>
  );
}

const LIMIT_UP_MODES = ["ladder", "history"] as const;

export default function LimitUpLadderTab() {
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
        className="u-mb-16"
      />
      {mode === "history" ? <LimitHistoryPanel /> : <LimitUpLadderContent />}
    </div>
  );
}
