import { useCallback, useEffect, useMemo } from "react";
import { Button, Card, DatePicker, Segmented, Space, Table, Tag, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { useMarketLimitHistory } from "../../api/queries";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import SectionToolbar from "../../components/SectionToolbar";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type { MarketLimitHistoryCategory, MarketLimitHistoryItem } from "../../types/stock";
import { normalizeIsoDate } from "../../utils/date";
import { formatAmount } from "../../utils/format";
import { formatMarketDateTime } from "../../utils/marketTime";

const { Text } = Typography;
const HISTORY_CATEGORIES = ["limit_up", "limit_down", "wind_vane"] as const;
const CATEGORY_LABELS: Record<MarketLimitHistoryCategory, string> = {
  limit_up: "历史涨停",
  limit_down: "历史跌停",
  wind_vane: "风向标",
};

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  return formatMarketDateTime(value, value);
}

function formatRate(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

export default function LimitHistoryPanel() {
  const colors = useColors();
  const t = useTokens();
  const isMobile = useMediaQuery("(max-width: 768px)");
  const defaultDate = dayjs().subtract(1, "day").format("YYYY-MM-DD");
  const [category, setCategory] = useUrlSearchParam<MarketLimitHistoryCategory>(
    "historyCategory",
    "limit_up",
    { allowedValues: HISTORY_CATEGORIES, replace: true },
  );
  const [dateParam, setDate] = useUrlSearchParam("historyDate", defaultDate, { replace: true });
  const normalizedDate = normalizeIsoDate(dateParam, defaultDate);
  const dateText = dayjs(normalizedDate).isBefore(dayjs(), "day") ? normalizedDate : defaultDate;
  const selectedDate = dayjs(dateText);

  useEffect(() => {
    if (dateParam !== dateText) setDate(dateText);
  }, [dateParam, dateText, setDate]);

  const query = useMarketLimitHistory(dateText, category);
  const items = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const hasData = items.length > 0;
  const categoryLabel = CATEGORY_LABELS[category];

  const renderExpandedRow = useCallback((stock: MarketLimitHistoryItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "themes", label: "题材", value: stock.themes || "-" },
        ...(category !== "limit_down" && stock.reason && stock.reason !== "无"
          ? [{ key: "reason", label: "涨停原因", value: stock.reason }]
          : []),
        { key: "open_time", label: "开板时间", value: stock.open_time || "未开板" },
        { key: "turnover_rate", label: "换手率", value: formatRate(stock.turnover_rate) },
        { key: "seal_money", label: "封单金额", value: formatAmount(stock.seal_money) },
        { key: "seal_amount", label: "封单量", value: formatAmount(stock.seal_amount) },
        { key: "turnover", label: "成交额", value: formatAmount(stock.turnover) },
        {
          key: "net_inflow",
          label: "净流入",
          value: (
            <span style={{ color: stock.net_inflow > 0 ? colors.up : stock.net_inflow < 0 ? colors.down : undefined }}>
              {formatAmount(stock.net_inflow)}
            </span>
          ),
        },
        { key: "market_cap", label: "流通市值", value: formatAmount(stock.market_cap) },
        ...(category !== "limit_down" && stock.industry_limit_up_count > 0
          ? [{ key: "industry_limit", label: "同行业涨停", value: `${stock.industry_limit_up_count}家` }]
          : []),
      ]}
    />
  ), [category, colors.down, colors.up]);

  const columns: ColumnsType<MarketLimitHistoryItem> = useMemo(() => {
    if (isMobile) {
      const mobileColumns: ColumnsType<MarketLimitHistoryItem> = [
        {
          title: "股票",
          key: "stock",
          width: 140,
          render: (_value, stock) => (
            <StockExternalLink code={stock.code} name={stock.name} style={{ display: "inline-flex" }}>
              <Space orientation="vertical" size={0}>
                <Text strong>{stock.name}</Text>
                <Space size={4} wrap>
                  <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>{stock.code}</Text>
                  {stock.themes ? (
                    <Text type="secondary" style={{ fontSize: "var(--c-font-xs)" }} ellipsis>
                      · {stock.themes.split("、")[0]}
                    </Text>
                  ) : null}
                </Space>
              </Space>
            </StockExternalLink>
          ),
        },
      ];

      if (category !== "limit_down") {
        mobileColumns.push({
          title: "连板",
          key: "limit_tag",
          width: 86,
          align: "center",
          render: (_value, stock) => stock.limit_tag ? (
            <Tag style={semanticTagStyle("up")}>
              {stock.limit_tag}{stock.limit_count > 0 ? ` · ${stock.limit_count}板` : ""}
            </Tag>
          ) : "-",
        });
      }

      mobileColumns.push({
        title: category === "limit_down" ? "跌停时间" : "涨停时间",
        dataIndex: "limit_time",
        width: 86,
        align: "center",
        render: (value: string) => <span style={{ fontFamily: "var(--c-font-mono)", fontSize: t.font.xs }}>{value || "-"}</span>,
      });

      return mobileColumns;
    }

    const result: ColumnsType<MarketLimitHistoryItem> = [
      {
        title: "股票",
        key: "stock",
        fixed: "left",
        width: 144,
        render: (_value, stock) => (
          <StockExternalLink code={stock.code} name={stock.name} style={{ display: "inline-flex" }}>
            <Space orientation="vertical" size={0}>
              <Text strong>{stock.name}</Text>
              <Text type="secondary" style={{ fontSize: "var(--c-font-sm)" }}>{stock.code}</Text>
            </Space>
          </StockExternalLink>
        ),
      },
    ];

    if (category !== "limit_down") {
      result.push({
        title: "连板标签",
        key: "limit_tag",
        width: 110,
        align: "center",
        render: (_value, stock) => stock.limit_tag ? (
          <Tag style={semanticTagStyle("up")}>
            {stock.limit_tag}{stock.limit_count > 0 ? ` · ${stock.limit_count}板` : ""}
          </Tag>
        ) : "-",
      });
    }

    result.push(
      {
        title: category === "limit_down" ? "跌停时间" : "涨停时间",
        dataIndex: "limit_time",
        width: 100,
        align: "center",
        render: (value: string) => value || "-",
      },
      {
        title: "开板时间",
        dataIndex: "open_time",
        width: 100,
        align: "center",
        render: (value: string) => value || "未开板",
      },
      {
        title: "题材",
        dataIndex: "themes",
        width: 190,
        ellipsis: true,
        render: (value: string) => value || "-",
      },
    );

    if (category !== "limit_down") {
      result.push({
        title: "涨停原因",
        dataIndex: "reason",
        width: 160,
        ellipsis: true,
        render: (value: string) => value && value !== "无" ? value : "-",
      });
    }

    result.push(
      {
        title: "封单量",
        dataIndex: "seal_amount",
        width: 110,
        align: "right",
        render: (value: number) => formatAmount(value),
      },
      {
        title: "封单金额",
        dataIndex: "seal_money",
        width: 110,
        align: "right",
        render: (value: number) => formatAmount(value),
      },
      {
        title: "成交额",
        dataIndex: "turnover",
        width: 110,
        align: "right",
        render: (value: number) => formatAmount(value),
      },
      {
        title: "换手率",
        dataIndex: "turnover_rate",
        width: 90,
        align: "right",
        render: (value: number | null) => formatRate(value),
      },
      {
        title: "净流入",
        dataIndex: "net_inflow",
        width: 110,
        align: "right",
        render: (value: number) => (
          <span style={{ color: value > 0 ? colors.up : value < 0 ? colors.down : undefined }}>
            {formatAmount(value)}
          </span>
        ),
      },
      {
        title: "流通市值",
        dataIndex: "market_cap",
        width: 120,
        align: "right",
        render: (value: number) => formatAmount(value),
      },
    );

    if (category !== "limit_down") {
      result.push({
        title: "同行业涨停",
        dataIndex: "industry_limit_up_count",
        width: 110,
        align: "center",
        render: (value: number) => value > 0 ? `${value}家` : "-",
      });
    }
    return result;
  }, [category, colors.down, colors.up, isMobile, t.font.xs]);

  return (
    <div>
      <div style={{ marginBottom: t.space[4] }}>
        <SectionToolbar
          ariaLabel="历史榜单工具条"
          meta={
            <Space size={parseFloat(t.space[3])} wrap>
              <span style={{ fontWeight: Number(t.weight.semibold), color: colors.textPrimary }}>
                {categoryLabel}
              </span>
              <Text type="secondary">数据日期：{query.data?.date || dateText}</Text>
              <Text type="secondary">更新时间：{formatFetchedAt(query.data?.fetched_at)}</Text>
              <Text type="secondary">共 {query.data?.total ?? items.length} 家</Text>
            </Space>
          }
          actions={
            <Space wrap>
              <Segmented
                aria-label="历史榜单类别"
                value={category}
                onChange={(value) => setCategory(String(value))}
                options={HISTORY_CATEGORIES.map((value) => ({ value, label: CATEGORY_LABELS[value] }))}
              />
              <DatePicker
                aria-label="历史复盘日期"
                value={selectedDate}
                allowClear={false}
                disabledDate={(current) => !current.isBefore(dayjs(), "day")}
                onChange={(value) => value && setDate(value.format("YYYY-MM-DD"))}
              />
              <Button icon={<ReloadOutlined />} loading={query.isFetching} onClick={() => query.refetch()}>
                刷新
              </Button>
            </Space>
          }
        />
      </div>

      <SectionDataState
        isLoading={query.isLoading && !hasData}
        error={hasData ? undefined : query.error}
        onRetry={() => query.refetch()}
        isEmpty={!query.isLoading && !query.error && !hasData}
        emptyText={`${dateText} 暂无${categoryLabel}数据`}
        errorTitle={`${categoryLabel}加载失败`}
        minHeight={420}
        skeletonRows={10}
      >
        <Card title={`${categoryLabel}明细`} style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
          <Table<MarketLimitHistoryItem>
            rowKey="code"
            columns={columns}
            dataSource={items}
            pagination={{ pageSize: 20, showSizeChanger: !isMobile, simple: isMobile }}
            expandable={isMobile ? {
              expandedRowRender: renderExpandedRow,
              columnWidth: 38,
            } : undefined}
            scroll={isMobile ? undefined : { x: "max-content" }}
            size="middle"
          />
        </Card>
      </SectionDataState>
    </div>
  );
}
