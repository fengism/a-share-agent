import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Button, Card, Segmented, Table, Tag, Typography } from "antd";
import { RadarChartOutlined, ThunderboltOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";
import { usePotentialDates, usePotentialDaily, usePotentialRun } from "../../api/queries";
import ChangeValue from "../../components/ChangeValue";
import SectionDataState from "../../components/SectionDataState";
import StockExternalLink from "../../components/StockExternalLink";
import { useColors, useTokens, semanticTagStyle } from "../../styles/ui";
import type { PotentialStockItem } from "../../types/stock";

const { Text } = Typography;

function formatValue(value: number | null | undefined, digits = 2, suffix = "") {
  if (value == null) return "-";
  return `${value.toFixed(digits)}${suffix}`;
}

export default function PotentialPage() {
  const c = useColors();
  const t = useTokens();
  const datesQuery = usePotentialDates();
  const dates = useMemo(() => datesQuery.data ?? [], [datesQuery.data]);
  const [chosenDate, setChosenDate] = useState<string | null>(null);
  const selectedDate = chosenDate ?? dates[0]?.date ?? null;
  const resultQuery = usePotentialDaily(selectedDate);
  const runMutation = usePotentialRun();

  const items = useMemo(() => resultQuery.data?.items ?? [], [resultQuery.data?.items]);

  const isLatestDate = selectedDate == null || selectedDate === dates[0]?.date;

  const columns: ColumnsType<PotentialStockItem> = useMemo(() => [
    {
      title: "#",
      key: "rank",
      width: 52,
      align: "center",
      render: (_: unknown, __: PotentialStockItem, index: number) => {
        let rankBg = c.nestedBg;
        let rankColor = c.textSecondary;
        if (index === 0) {
          rankBg = "linear-gradient(135deg, #ffd700, #ffaa00)";
          rankColor = "#7a4100";
        } else if (index === 1) {
          rankBg = "linear-gradient(135deg, #e0e0e0, #b0bec5)";
          rankColor = "#37474f";
        } else if (index === 2) {
          rankBg = "linear-gradient(135deg, #ffcc80, #d7ccc8)";
          rankColor = "#5d4037";
        }
        return (
          <span
            style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 24, height: 24, borderRadius: t.radius.sm,
              fontSize: t.font.xs, fontWeight: Number(t.weight.bold),
              color: rankColor,
              background: rankBg,
              boxShadow: index < 3 ? "0 2px 6px rgba(0,0,0,0.12)" : undefined,
            }}
          >
            {index + 1}
          </span>
        );
      },
    },
    {
      title: "股票",
      key: "stock",
      width: 160,
      render: (_: unknown, record: PotentialStockItem) => (
        <StockExternalLink code={record.code} name={record.name} style={{ color: c.primary, display: "flex", flexDirection: "column", minWidth: 0 }}>
          <span style={{ color: c.textPrimary, fontWeight: Number(t.weight.semibold) }}>{record.name}</span>
          <span style={{ color: c.textMuted, fontSize: t.font.xs }}>{record.code}</span>
        </StockExternalLink>
      ),
    },
    {
      title: isLatestDate ? "收盘价" : "选出收盘价",
      dataIndex: "price",
      width: 100,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
    {
      title: isLatestDate ? "涨跌幅" : "当日涨跌",
      dataIndex: "change_pct",
      width: 90,
      align: "right",
      render: (value: number | null) => <ChangeValue value={value} fontWeight={Number(t.weight.medium)} />,
    },
    {
      title: "综合评分",
      dataIndex: "score",
      width: 100,
      align: "right",
      sorter: (a: PotentialStockItem, b: PotentialStockItem) => a.score - b.score,
      render: (value: number) => {
        const isHigh = value >= 4.5;
        return (
          <span
            className={isHigh ? "potential-score-badge--high" : "potential-score-badge"}
            style={{
              fontWeight: Number(t.weight.bold),
              color: isHigh ? c.accent : c.primary,
              fontFamily: "var(--c-font-mono)",
            }}
          >
            {value.toFixed(1)}
          </span>
        );
      },
    },
    {
      title: "命中策略",
      dataIndex: "strategies",
      render: (strategies: string[]) => (
        <span style={{ display: "flex", flexWrap: "wrap", gap: t.space[1] }}>
          {strategies.map((name) => (
            <Tag key={name} style={{ ...semanticTagStyle("primary"), fontSize: t.font.xs, marginInlineEnd: 0 }}>{name}</Tag>
          ))}
        </span>
      ),
    },
    {
      title: "信号日期",
      dataIndex: "signal_date",
      width: 110,
      render: (value: string, record: PotentialStockItem) => (
        <span style={{ fontFamily: "var(--c-font-mono)" }}>
          {value || "-"}
          {record.signal_age_days != null && record.signal_age_days <= 3 ? (
            <Tag
              className="potential-signal-new-tag"
              style={{
                ...semanticTagStyle("up"),
                fontSize: t.font.xs,
                marginInlineStart: t.space[1],
                fontWeight: Number(t.weight.semibold),
              }}
            >
              新
            </Tag>
          ) : null}
        </span>
      ),
    },
    {
      title: "成交额(亿)",
      dataIndex: "amount",
      width: 100,
      align: "right",
      render: (value: number | null) => formatValue(value),
    },
  ], [c, t, isLatestDate]);

  return (
    <div aria-label="潜力股挖掘页">
      <Card
        title={(
          <span style={{ display: "inline-flex", alignItems: "center", gap: t.space[2] }}>
            <RadarChartOutlined style={{ color: c.primary }} />
            <span>每日潜力股</span>
            <Tag
              style={{
                fontFamily: "var(--c-font-mono)",
                fontSize: t.font.xs,
                color: c.primary,
                borderColor: "color-mix(in srgb, var(--c-primary) 35%, transparent)",
                background: "color-mix(in srgb, var(--c-primary) 10%, transparent)",
                letterSpacing: "0.06em",
              }}
            >
              QUANT RADAR
            </Tag>
          </span>
        )}
        extra={(
          <Button
            icon={<ThunderboltOutlined />}
            loading={runMutation.isPending}
            onClick={() => runMutation.mutate(false, {
              onSuccess: () => {
                void datesQuery.refetch();
                void resultQuery.refetch();
              },
            })}
          >
            立即挖掘
          </Button>
        )}
      >
        <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: t.space[2], marginBottom: t.space[3] }}>
          <Segmented
            aria-label="结果日期"
            value={selectedDate ?? undefined}
            options={dates.slice(0, 7).map((item) => ({ label: item.date.slice(5), value: item.date }))}
            onChange={(value) => setChosenDate(String(value))}
          />
          {resultQuery.data ? (
            <Text type="secondary" style={{ fontSize: t.font.sm }}>
              {resultQuery.data.date} 生成 · 候选池 {resultQuery.data.universe_size} 只 · 评估 {resultQuery.data.evaluated} 只 · 命中 {items.length} 只
            </Text>
          ) : null}
        </div>
        <SectionDataState
          isLoading={resultQuery.isLoading}
          error={resultQuery.error}
          onRetry={() => resultQuery.refetch()}
          isEmpty={!resultQuery.isLoading && !resultQuery.error && items.length === 0}
          emptyText="暂无潜力股结果，可点击右上角「立即挖掘」生成今日结果（后台也会在每日收盘后自动运行）"
          errorTitle="潜力股数据加载失败"
          skeletonRows={8}
          minHeight={320}
        >
          <Table<PotentialStockItem>
            columns={columns}
            dataSource={items}
            rowKey={(record) => `${record.code}-${record.score}`}
            size="small"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            scroll={{ x: "max-content" }}
          />
        </SectionDataState>
        <Text type="secondary" style={{ fontSize: t.font.xs }}>
          说明：候选池按成交额取头部并剔除 ST/次新/低流动性标的；评分为 7 个量化策略当前持仓信号的加权融合（3 个交易日内触发的新鲜信号加权），
          仅供研究参考，不构成投资建议。股票名称可点击进入
          <Link to="/screener" style={{ color: c.primary }}>选股器</Link>
          进一步筛选或查看个股分析。
        </Text>
      </Card>
    </div>
  );
}
