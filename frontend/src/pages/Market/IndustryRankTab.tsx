import { Table, Tag } from "antd";
import { AppstoreOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { useIndustryRankings } from "../../api/queries";
import type { IndustryRankItem } from "../../types/stock";
import { changeColor, formatSignedPercent } from "../../utils/format";
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
  const { cardStyle } = useStyles();
  const { data, isLoading, isFetching } = useIndustryRankings();
  const sectors = data?.sectors ?? [];

  const columns: ColumnsType<IndustryRankItem> = [
    { title: "排名", dataIndex: "rank", width: 60, align: "center", render: (rank: number) => rankBadge(rank, c) },
    { title: "板块名称", dataIndex: "name", width: 140, ellipsis: true },
    {
      title: "涨跌幅",
      dataIndex: "change_pct",
      width: 90,
      align: "right",
      sorter: (a, b) => (a.change_pct ?? 0) - (b.change_pct ?? 0),
      defaultSortOrder: "descend",
      render: (value: number) => (
        <span style={{ color: changeColor(value, c), fontWeight: 500 }}>
          {formatSignedPercent(value)}
        </span>
      ),
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
      render: (value: number) => (
        <span style={{ color: changeColor(value, c) }}>
          {formatSignedPercent(value)}
        </span>
      ),
    },
  ];

  return (
    <div style={{ ...cardStyle, padding: 0 }}>
      <div style={{ padding: "12px 16px", borderBottom: `1px solid ${c.border}`, display: "flex", alignItems: "center", gap: 8 }}>
        <AppstoreOutlined style={{ color: c.primary }} />
        <span style={{ color: c.textPrimary, fontWeight: 500 }}>行业板块涨跌幅排名</span>
        <Tag color="blue" style={{ marginLeft: 4 }}>百度</Tag>
        {isFetching && <span style={{ color: c.textMuted, fontSize: 12, marginLeft: "auto" }}>更新中...</span>}
      </div>
      <Table<IndustryRankItem>
        columns={columns}
        dataSource={sectors}
        rowKey="code"
        loading={isLoading}
        pagination={false}
        scroll={{ y: 600 }}
        size="small"
        style={{ background: "transparent" }}
      />
    </div>
  );
}
