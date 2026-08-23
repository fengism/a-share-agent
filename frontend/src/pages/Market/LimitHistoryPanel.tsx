import { useEffect, useMemo } from "react";
import { Button, Card, DatePicker, Segmented, Space, Table, Tag, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import type { ColumnsType } from "antd/es/table";
import { useMarketLimitHistory } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useUrlSearchParam } from "../../hooks/useUrlSearchParam";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type { MarketLimitHistoryCategory, MarketLimitHistoryItem } from "../../types/stock";
import { normalizeIsoDate } from "../../utils/date";
import { formatAmount } from "../../utils/format";

const { Text, Title } = Typography;
const HISTORY_CATEGORIES = ["limit_up", "limit_down", "wind_vane"] as const;
const CATEGORY_LABELS: Record<MarketLimitHistoryCategory, string> = {
  limit_up: "历史涨停",
  limit_down: "历史跌停",
  wind_vane: "风向标",
};

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", { hour12: false });
}

function formatRate(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

export default function LimitHistoryPanel() {
  const colors = useColors();
  const t = useTokens();
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

  const columns: ColumnsType<MarketLimitHistoryItem> = useMemo(() => {
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
              <Text type="secondary" style={{ fontSize: 12 }}>{stock.code}</Text>
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
  }, [category, colors.down, colors.up]);

  return (
    <div>
      <Card
        size="small"
        style={{ marginBottom: t.space[4], borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: t.space[3], flexWrap: "wrap" }}>
          <Space orientation="vertical" size={4}>
            <Title level={4} style={{ margin: 0 }}>{categoryLabel}</Title>
            <Space size={parseFloat(t.space[3])} wrap>
              <Text type="secondary">数据日期：{query.data?.date || dateText}</Text>
              <Text type="secondary">更新时间：{formatFetchedAt(query.data?.fetched_at)}</Text>
              <Text type="secondary">共 {query.data?.total ?? items.length} 家</Text>
            </Space>
          </Space>
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
        </div>
      </Card>

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
            pagination={{ pageSize: 20, showSizeChanger: false }}
            scroll={{ x: "max-content" }}
            size="middle"
          />
        </Card>
      </SectionDataState>
    </div>
  );
}
