import { useCallback, useMemo } from "react";
import { Table, Tag } from "antd";
import { AppstoreOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import ChangeValue from "../../components/ChangeValue";
import DataRefreshIndicator from "../../components/DataRefreshIndicator";
import ResponsiveMetricGrid from "../../components/ResponsiveMetricGrid";
import SectionDataState from "../../components/SectionDataState";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useIndustryRankings } from "../../api/queries";
import type { IndustryRankItem } from "../../types/stock";
import { useColors, useStyles } from "../../theme/hooks";

function rankBadge(rank: number, colors: { up: string; textSecondary: string }) {
  let color = colors.textSecondary;
  let bg = "transparent";
  if (rank === 1 || rank === 2) {
    color = "#fff";
    bg = colors.up;
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

export default function IndustryRankTab() {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const { cardStyle } = useStyles();
  const { data, isLoading, isFetching, error, refetch } = useIndustryRankings();
  const sectors = data?.sectors ?? [];
  const hasData = sectors.length > 0;

  const columns: ColumnsType<IndustryRankItem> = useMemo(() => {
    if (isNarrow) {
      return [
        {
          title: "板块",
          key: "sector",
          width: 180,
          render: (_: unknown, record: IndustryRankItem) => (
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {rankBadge(record.rank, c)}
              <span style={{ minWidth: 0, color: c.textPrimary, fontWeight: 600 }}>{record.name}</span>
            </div>
          ),
        },
        {
          title: "涨跌幅",
          dataIndex: "change_pct",
          width: 88,
          align: "right",
          sorter: (left, right) => (left.change_pct ?? 0) - (right.change_pct ?? 0),
          defaultSortOrder: "descend",
          render: (value: number | null) => <ChangeValue value={value} fontWeight={500} />,
        },
      ];
    }

    return [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c) },
    { title: "板块名称", dataIndex: "name", width: 140, ellipsis: true },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 90,
      align: "right",
      sorter: (a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
      defaultSortOrder: "descend",
      render: (value: number) => <ChangeValue value={value} fontWeight={500} />,
    },
    {
      title: "上涨",
      dataIndex: "up_count",
      width: 65,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.up }}>{value ?? "-"}</span>
      ),
    },
    {
      title: "下跌",
      dataIndex: "down_count",
      width: 65,
      align: "right",
      render: (value: number | null) => (
        <span style={{ color: c.down }}>{value ?? "-"}</span>
      ),
    },
    { title: "领涨股", dataIndex: "leader", width: 110, ellipsis: true },
    {
      title: "领涨幅",
      dataIndex: "leader_change",
      width: 90,
      align: "right",
      render: (value: number) => <ChangeValue value={value} fontWeight={400} />,
    },
    ];
  }, [c, isNarrow]);

  const renderExpandedRow = useCallback((record: IndustryRankItem) => (
    <ResponsiveMetricGrid
      items={[
        { key: "up", label: "上涨家数", value: record.up_count ?? "-" },
        { key: "down", label: "下跌家数", value: record.down_count ?? "-" },
        { key: "leader", label: "领涨股", value: record.leader || "-" },
        { key: "leader-change", label: "领涨幅", value: <ChangeValue value={record.leader_change} fontWeight={400} /> },
      ]}
    />
  ), []);

  return (
    <div style={{ ...cardStyle, padding: 0 }}>
      <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}`, display: "flex", alignItems: "center", gap: 8 }}>
        <AppstoreOutlined style={{ color: c.primary }} />
        <span style={{ color: c.textPrimary, fontWeight: 500 }}>行业板块涨跌幅排名</span>
        <Tag color="blue" style={{ marginLeft: 4 }}>百度</Tag>
        <span style={{ marginLeft: "auto" }}>
          <DataRefreshIndicator active={isFetching && !isLoading} />
        </span>
      </div>
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!isLoading && !error && !hasData}
        emptyText="暂无行业排名数据"
        errorTitle="行业排名加载失败"
        minHeight={320}
      >
        <Table<IndustryRankItem>
          columns={columns}
          dataSource={sectors}
          rowKey="code"
          pagination={false}
          expandable={isNarrow ? {
            expandedRowRender: renderExpandedRow,
            columnWidth: 38,
          } : undefined}
          scroll={{ y: 600 }}
          size="small"
          style={{ background: "transparent" }}
        />
      </SectionDataState>
    </div>
  );
}
