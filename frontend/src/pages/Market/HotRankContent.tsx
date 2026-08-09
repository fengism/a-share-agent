import { useCallback, useMemo, useState } from "react";
import { Card, Col, Row, Segmented, Table, Tag } from "antd";
import {
  AppstoreOutlined,
  FireOutlined,
  RiseOutlined,
} from "@ant-design/icons";
import { Link } from "react-router-dom";
import type { ColumnsType } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import {
  useThsHotConcept,
  useThsHotIndustry,
  useThsHotRank,
} from "../../api/queries";
import type { ThsHotPlate, ThsHotStock } from "../../types/stock";
import { formatHotValue } from "../../utils/format";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

type TabKey = "stock" | "concept" | "industry";

const TAB_OPTIONS = [
  { label: <span><FireOutlined /> 热股榜</span>, value: "stock" as TabKey },
  { label: <span><RiseOutlined /> 概念榜</span>, value: "concept" as TabKey },
  { label: <span><AppstoreOutlined /> 行业榜</span>, value: "industry" as TabKey },
];

function rankBadge(rank: number, c: ThemeColors) {
  let color = c.textSecondary;
  let bg = "transparent";
  if (rank === 1 || rank === 2) {
    color = "#fff";
    bg = c.up;
  } else if (rank === 3) {
    color = "#fff";
    bg = "#eab308";
  } else if (rank <= 10) {
    color = "#eab308";
    bg = "rgba(234,179,8,0.15)";
  }

  return (
    <span
      style={{
        display: "inline-block",
        width: 28,
        height: 28,
        lineHeight: "28px",
        textAlign: "center",
        borderRadius: 6,
        fontWeight: 700,
        fontSize: 13,
        color,
        background: bg,
      }}
    >
      {rank}
    </span>
  );
}

function StockTable({ enabled, scrollY }: { enabled: boolean; scrollY: number }) {
  const c = useColors();
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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {rankBadge(record.rank, c)}
              <Link to={`/analysis/${record.code}`} style={{ minWidth: 0, color: c.primary }}>
                <span style={{ display: "block", color: c.textPrimary, fontWeight: 600 }}>{record.name}</span>
                <span style={{ display: "block", color: c.textMuted, fontSize: 11 }}>{record.code}</span>
              </Link>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number) => <ChangeValue value={value} fontWeight={500} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 70,
          align: "right",
          render: (value: number | null) => <span style={{ fontWeight: 600, color: c.up }}>{formatHotValue(value)}</span>,
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c) },
    {
      title: "代码",
      dataIndex: "code",
      width: 90,
      render: (code: string) => (
        <Link to={`/analysis/${code}`} style={{ color: c.primary, fontWeight: 500 }}>
          {code}
        </Link>
      ),
    },
    { title: "名称", dataIndex: "name", width: 100, ellipsis: true },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={500} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontWeight: 600, color: c.up }}>
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
                <Tag key={index} style={{ fontSize: 11, marginBottom: 2 }}>
                  {tag}
                </Tag>
              ))
          : "-",
    },
    ];
  }, [c, isNarrow]);

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
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {rankBadge(record.rank, c)}
              <span style={{ minWidth: 0, color: c.textPrimary, fontWeight: 600 }}>{record.name}</span>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 82,
          align: "right",
          render: (value: number) => <ChangeValue value={value} fontWeight={500} />,
        },
        {
          title: "热度",
          dataIndex: "hot_value",
          width: 70,
          align: "right",
          render: (value: number | null) => <span style={{ fontWeight: 600, color: c.up }}>{formatHotValue(value)}</span>,
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c) },
    {
      title: type === "concept" ? "概念名称" : "行业名称",
      dataIndex: "name",
      width: 160,
      ellipsis: true,
      render: (name: string) => <span style={{ fontWeight: 500 }}>{name}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 85,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={500} />,
    },
    {
      title: "热度",
      dataIndex: "hot_value",
      width: 80,
      align: "right",
      render: (value: number | null) => (
        <span style={{ fontWeight: 600, color: c.up }}>
          {formatHotValue(value)}
        </span>
      ),
    },
    {
      title: "上榜标签",
      dataIndex: "hot_tag",
      width: 140,
      render: (tag: string) =>
        tag ? <Tag color="blue" style={{ fontSize: 11 }}>{tag}</Tag> : "-",
    },
    {
      title: "涨跌停",
      dataIndex: "tag",
      width: 110,
      render: (tag: string) =>
        tag ? <Tag color="volcano" style={{ fontSize: 11 }}>{tag}</Tag> : "-",
    },
    ];
  }, [c, isNarrow, type]);

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
  const [tab, setTab] = useState<TabKey>("stock");
  const stockScrollY = embedded ? 580 : 600;

  return (
    <>
      <Card
        size="small"
        style={{
          marginBottom: embedded ? 12 : 16,
          borderRadius: 10,
          border: "none",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        }}
        styles={{ body: { padding: embedded ? undefined : "16px 24px" } }}
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
            <Tag color="red">同花顺</Tag>
            <span style={{ color: c.textSecondary, fontSize: 12, marginLeft: 8 }}>
              {embedded ? "每分钟自动更新" : "数据来源: 同花顺 | 5分钟更新"}
            </span>
          </Col>
        </Row>
      </Card>
      <Card
        size="small"
        style={{
          borderRadius: 10,
          border: "none",
          boxShadow: "0 1px 4px rgba(0,0,0,0.04)",
        }}
        styles={{ body: { padding: "8px 16px" } }}
      >
        {tab === "stock" && <StockTable enabled={tab === "stock"} scrollY={stockScrollY} />}
        {tab === "concept" && <PlateTable type="concept" enabled={tab === "concept"} />}
        {tab === "industry" && <PlateTable type="industry" enabled={tab === "industry"} />}
      </Card>
    </>
  );
}
