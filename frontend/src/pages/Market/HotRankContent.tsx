import { useCallback, useMemo, useState } from "react";
import { Card, Col, Row, Segmented, Table, Tag } from "antd";
import {
  AppstoreOutlined,
  FireOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import {
  useThsHotConcept,
  useThsHotIndustry,
  useThsHotRank,
} from "../../api/queries";
import type { ThsHotPlate, ThsHotStock } from "../../types/stock";
import { formatHotValue } from "../../utils/format";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import { rankBadge } from "./rankBadge";

type TabKey = "stock" | "concept" | "industry";

const TAB_OPTIONS = [
  { label: <span><FireOutlined /> 热股榜</span>, value: "stock" as TabKey },
  { label: <span><RiseOutlined /> 概念榜</span>, value: "concept" as TabKey },
  { label: <span><AppstoreOutlined /> 行业榜</span>, value: "industry" as TabKey },
];

function StockTable({ enabled, scrollY }: { enabled: boolean; scrollY: number }) {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { data, isLoading, isFetching, error, refetch } = useThsHotRank(enabled);
  const hasData = (data?.length ?? 0) > 0;

  const columns: ColumnsType<ThsHotStock> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "股票",
          key: "stock",
          width: 150,
          render: (_: unknown, record: ThsHotStock) => (
            <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
              {rankBadge(record.rank, c, t)}
              <StockExternalLink code={record.code} name={record.name} style={{ minWidth: 0, color: c.primary }}>
                <span style={{ display: "block", color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
                <span style={{ display: "block", color: c.textMuted, fontSize: t.font.xs }}>{record.code}</span>
              </StockExternalLink>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 70,
          align: "right",
          render: (value: number | null) => <span style={{ fontWeight: Number(t.weight.semibold), color: c.up }}>{formatHotValue(value)}</span>,
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number | null) => rankBadge(rank, c, t) },
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      render: (code: string) => (
        <StockExternalLink code={code} style={{ color: c.primary, fontWeight: Number(t.weight.medium) }}>
          {code}
        </StockExternalLink>
      ),
    },
    { title: "名称", dataIndex: "name", width: 100, ellipsis: true },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontWeight: Number(t.weight.semibold), color: c.up }}>
          {formatHotValue(value)}
        </span>
      ),
    },
    {
      title: "关联概念",
      dataIndex: "concept_tag",
      width: 220,
      render: (tags: string) =>
        tags
          ? tags
              .split(";")
              .slice(0, 3)
              .map((tag, index) => (
                <Tag key={index} style={{ fontSize: t.font.xs, marginBottom: t.space[1] }}>
                  {tag}
                </Tag>
              ))
          : "-",
    },
    ];
  }, [c, t, isNarrow]);

  const renderExpandedRow = useCallback((record: ThsHotStock) => (
    <ResponsiveMetricGrid
      items={[
        { key: "concept", label: "关联概念", value: record.concept_tag || "-" },
        { key: "pop", label: "人气标签", value: record.pop_tag || "-" },
      ]}
    />
  ), []);

  return (
    <div>
      <div style={{ minHeight: 22, display: "flex", justifyContent: "flex-end" }}>
        <DataRefreshIndicator active={isFetching && !isLoading} />
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无热股排行数据"
        errorTitle="热股排行加载失败"
        minHeight={320}
      >
        <Table
          columns={columns}
          dataSource={data || []}
          rowKey={(record) => `${record.code}-${record.name}-${record.rank}`}
          size="small"
          pagination={false}
          expandable={isNarrow ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 38,
          } : undefined}
          scroll={{ y: scrollY }}
        />
      </SectionDataState>
    </div>
  );
}

function PlateTable({ type, enabled }: { type: "concept" | "industry"; enabled: boolean }) {
  const c = useColors();
  const t = useTokens();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const hook = type === "concept" ? useThsHotConcept : useThsHotIndustry;
  const { data, isLoading, isFetching, error, refetch } = hook(enabled);
  const hasData = (data?.length ?? 0) > 0;

  const columns: ColumnsType<ThsHotPlate> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: type === "concept" ? "概念" : "行业",
          key: "plate",
          width: 150,
          render: (_: unknown, record: ThsHotPlate) => (
            <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
              {rankBadge(record.rank, c, t)}
              <span style={{ minWidth: 0, color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 70,
          align: "right",
          render: (value: number | null) => <span style={{ fontWeight: Number(t.weight.semibold), color: c.up }}>{formatHotValue(value)}</span>,
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c, t) },
    {
      title: type === "concept" ? "概念名称" : "行业名称",
      dataIndex: "name",
      width: 160,
      ellipsis: true,
      render: (name: string) => <span style={{ fontWeight: Number(t.weight.medium) }}>{name}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontWeight: Number(t.weight.semibold), color: c.up }}>
          {formatHotValue(value)}
        </span>
      ),
    },
    {
      title: "上榜标签",
      dataIndex: "hot_tag",
      width: 140,
      render: (tag: string) =>
        tag ? <Tag style={{ ...semanticTagStyle("primary"), fontSize: t.font.xs }}>{tag}</Tag> : "-",
    },
    {
      title: "涨跌停",
      dataIndex: "tag",
      width: 110,
      render: (tag: string) =>
        tag ? <Tag style={{ ...semanticTagStyle("warning"), fontSize: t.font.xs }}>{tag}</Tag> : "-",
    },
    ];
  }, [c, t, isNarrow, type]);

  const renderExpandedRow = useCallback((record: ThsHotPlate) => (
    <ResponsiveMetricGrid
      items={[
        { key: "hot-tag", label: "上榜标签", value: record.hot_tag || "-" },
        { key: "limit-tag", label: "涨跌停", value: record.tag || "-" },
      ]}
    />
  ), []);

  return (
    <div>
      <div style={{ minHeight: 22, display: "flex", justifyContent: "flex-end" }}>
        <DataRefreshIndicator active={isFetching && !isLoading} />
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText={`暂无${type === "concept" ? "概念" : "行业"}热榜数据`}
        errorTitle={`${type === "concept" ? "概念" : "行业"}热榜加载失败`}
        minHeight={320}
      >
        <Table
          columns={columns}
          dataSource={data || []}
          rowKey={(record) => `${record.code}-${record.name}-${record.rank}`}
          size="small"
          pagination={false}
          expandable={isNarrow ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 38,
          } : undefined}
        />
      </SectionDataState>
    </div>
  );
}

interface HotRankContentProps {
  embedded?: boolean;
}

export function HotRankContent({ embedded = false }: HotRankContentProps) {
  const c = useColors();
  const t = useTokens();
  const [tab, setTab] = useState<TabKey>("stock");
  const stockScrollY = embedded ? 580 : 600;

  return (
    <>
      <Card
        size="small"
        style={{
          marginBottom: embedded ? t.space[3] : t.space[4],
          borderRadius: t.radius.lg,
          border: "none",
          boxShadow: t.shadow.xs,
        }}
        styles={{ body: { padding: embedded ? undefined : `${t.space[4]} ${t.space[6]}` } }}
      >
        <Row justify="space-between" align="middle">
          <Col>
            <Segmented
              options={TAB_OPTIONS}
              value={tab}
              onChange={(value) => setTab(value as TabKey)}
            />
          </Col>
          <Col>
            <Tag>同花顺</Tag>
            <span style={{ color: c.textSecondary, fontSize: t.font.sm, marginLeft: t.space[2] }}>
              {embedded ? "每分钟自动更新" : "数据来源: 同花顺 | 5分钟更新"}
            </span>
          </Col>
        </Row>
      </Card>
      <Card
        size="small"
        style={{
          borderRadius: t.radius.lg,
          border: "none",
          boxShadow: t.shadow.xs,
        }}
        styles={{ body: { padding: `${t.space[2]} ${t.space[4]}` } }}
      >
        {tab === "stock" && <StockTable enabled={tab === "stock"} scrollY={stockScrollY} />}
        {tab === "concept" && <PlateTable type="concept" enabled={tab === "concept"} />}
        {tab === "industry" && <PlateTable type="industry" enabled={tab === "industry"} />}
      </Card>
    </>
  );
}
