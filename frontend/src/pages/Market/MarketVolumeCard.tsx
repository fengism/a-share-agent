import { useMemo, useState } from "react";
import { Button, Card, Col, Row, Segmented, Statistic, Tag, Typography } from "antd";
import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  BarChartOutlined,
  ReloadOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useMarketVolume } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens } from "../../styles/ui";

const { Text } = Typography;

type VolumeRange = "30" | "60" | "120" | "all";

interface ProcessedVolumeItem {
  date: string;
  amountYi: number;
  volumeWanShou: number;
  ma5: number;
  ma20: number;
  changeYi: number;
  changePct: number;
  isHigherThanPrev: boolean;
}

export default function MarketVolumeCard({
  style,
  className,
}: {
  style?: React.CSSProperties;
  className?: string;
}) {
  const c = useColors();
  const t = useTokens();
  const [range, setRange] = useState<VolumeRange>("60");

  const { data, isLoading, isFetching, error, refetch } = useMarketVolume();

  const { displayItems, stats } = useMemo(() => {
    const rawItems = data?.items ?? [];
    if (rawItems.length === 0) {
      return { displayItems: [] as ProcessedVolumeItem[], stats: null };
    }

    // 先计算完整全序列的 MA5 与 MA20，避免切片后起始点均线产生空值缺口
    const allMapped: ProcessedVolumeItem[] = rawItems.map((item, idx) => {
      const amountYi = Number((item.amount / 1e8).toFixed(2));
      const volumeWanShou = Number((item.volume / 1e4).toFixed(0));

      const start5 = Math.max(0, idx - 4);
      const slice5 = rawItems.slice(start5, idx + 1);
      const ma5 = Number((slice5.reduce((sum, it) => sum + (it.amount || 0) / 1e8, 0) / slice5.length).toFixed(2));

      const start20 = Math.max(0, idx - 19);
      const slice20 = rawItems.slice(start20, idx + 1);
      const ma20 = Number((slice20.reduce((sum, it) => sum + (it.amount || 0) / 1e8, 0) / slice20.length).toFixed(2));

      const prevAmount = idx > 0 ? rawItems[idx - 1].amount / 1e8 : amountYi;
      const changeYi = idx > 0 ? amountYi - prevAmount : 0;
      const changePct = idx > 0 && prevAmount > 0 ? (changeYi / prevAmount) * 100 : 0;

      return {
        date: item.date,
        amountYi,
        volumeWanShou,
        ma5,
        ma20,
        changeYi: Number(changeYi.toFixed(2)),
        changePct: Number(changePct.toFixed(2)),
        isHigherThanPrev: changeYi >= 0,
      };
    });

    const limit =
      range === "30" ? 30 : range === "60" ? 60 : range === "120" ? 120 : allMapped.length;
    const displayItems = allMapped.slice(-limit);

    if (displayItems.length === 0) {
      return { displayItems, stats: null };
    }

    const latest = displayItems[displayItems.length - 1];
    let maxItem = displayItems[0];
    let minItem = displayItems[0];
    for (const it of displayItems) {
      if (it.amountYi > maxItem.amountYi) maxItem = it;
      if (it.amountYi < minItem.amountYi) minItem = it;
    }

    const volumeRatio = latest.ma20 > 0 ? Number((latest.amountYi / latest.ma20).toFixed(2)) : null;

    return {
      displayItems,
      stats: {
        latest,
        maxItem,
        minItem,
        volumeRatio,
      },
    };
  }, [data?.items, range]);

  const hasData = displayItems.length > 0;

  const chartOption = useMemo(() => {
    if (!hasData) return {};

    const dates = displayItems.map((it) => it.date);
    const amounts = displayItems.map((it) => it.amountYi);
    const ma5List = displayItems.map((it) => it.ma5);
    const ma20List = displayItems.map((it) => it.ma20);

    return {
      animation: false,
      grid: {
        left: 56,
        right: 20,
        top: 36,
        bottom: 28,
      },
      legend: {
        data: ["成交额", "MA5", "MA20"],
        top: 4,
        right: 24,
        textStyle: {
          color: c.textSecondary,
          fontSize: 12,
        },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: {
          type: "cross",
          label: {
            backgroundColor: c.border,
            color: c.textPrimary,
          },
        },
        backgroundColor: c.cardBg,
        borderColor: c.border,
        textStyle: {
          color: c.textPrimary,
          fontSize: 12,
        },
        formatter: (params: Array<{ seriesName: string; value: number; dataIndex: number }>) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const item = displayItems[idx];
          if (!item) return "";

          const changeColor = item.changeYi >= 0 ? c.up : c.down;
          const changeSign = item.changeYi >= 0 ? "+" : "";

          const rows = [
            `<div style="font-weight:600;margin-bottom:6px;border-bottom:1px solid ${c.border};padding-bottom:4px;">${item.date}</div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px;"><span>两市总成交额:</span><strong>${item.amountYi.toLocaleString("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 亿元</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px;color:${changeColor};"><span>较前一交易日:</span><strong>${changeSign}${item.changeYi.toFixed(1)} 亿元 (${changeSign}${item.changePct.toFixed(1)}%)</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px;color:#f59e0b;"><span>5日均量 (MA5):</span><strong>${item.ma5.toLocaleString("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 亿元</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px;color:#8b5cf6;"><span>20日均量 (MA20):</span><strong>${item.ma20.toLocaleString("zh-CN", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} 亿元</strong></div>`,
          ];
          return rows.join("");
        },
      },
      dataZoom: [
        {
          type: "inside",
          start: 0,
          end: 100,
        },
      ],
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: c.border } },
        axisTick: { alignWithLabel: true },
        axisLabel: {
          color: c.textSecondary,
          fontSize: 11,
          formatter: (value: string) => {
            const parts = value.split("-");
            return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value;
          },
        },
      },
      yAxis: {
        type: "value",
        name: "亿元",
        nameTextStyle: {
          color: c.textSecondary,
          fontSize: 11,
          align: "right",
          padding: [0, 8, 0, 0],
        },
        axisLabel: {
          color: c.textSecondary,
          fontSize: 11,
          formatter: (val: number) => {
            if (val >= 10000) return `${(val / 10000).toFixed(1)}万`;
            return `${val.toFixed(0)}`;
          },
        },
        splitLine: {
          lineStyle: {
            color: c.border,
            type: "dashed",
          },
        },
      },
      series: [
        {
          name: "成交额",
          type: "bar",
          data: amounts,
          barMaxWidth: 16,
          itemStyle: {
            color: (params: { dataIndex: number }) => {
              const it = displayItems[params.dataIndex];
              // 放量日（红）与缩量日（绿）区分，采用适度透明度契合整体风格
              return it?.isHigherThanPrev
                ? "rgba(239, 68, 68, 0.72)"
                : "rgba(16, 185, 129, 0.72)";
            },
            borderRadius: [2, 2, 0, 0],
          },
        },
        {
          name: "MA5",
          type: "line",
          data: ma5List,
          smooth: 0.25,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: "#f59e0b",
          },
          itemStyle: { color: "#f59e0b" },
        },
        {
          name: "MA20",
          type: "line",
          data: ma20List,
          smooth: 0.25,
          showSymbol: false,
          lineStyle: {
            width: 2,
            color: "#8b5cf6",
          },
          itemStyle: { color: "#8b5cf6" },
        },
      ],
    };
  }, [hasData, displayItems, c]);

  return (
    <Card
      className={className}
      style={{
        borderRadius: t.radius.md,
        border: `1px solid ${c.border}`,
        boxShadow: t.shadow.xs,
        ...style,
      }}
      title={
        <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
          <BarChartOutlined style={{ color: c.primary }} />
          <span style={{ fontWeight: Number(t.weight.semibold) }}>A股全市场成交额走势</span>
          <Text type="secondary" style={{ fontSize: t.font.xs, fontWeight: "normal" }}>
            沪深北全市场合计
          </Text>
        </div>
      }
      extra={
        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          <Segmented
            aria-label="成交额统计区间"
            size="small"
            value={range}
            onChange={(val) => setRange(val as VolumeRange)}
            options={[
              { label: "近30日", value: "30" },
              { label: "近60日", value: "60" },
              { label: "近120日", value: "120" },
              { label: "近1年", value: "all" },
            ]}
          />
          <Button
            icon={<ReloadOutlined />}
            size="small"
            loading={isFetching}
            onClick={() => refetch()}
            aria-label="刷新市场成交额"
          >
            刷新
          </Button>
        </div>
      }
    >
      <SectionDataState
        isLoading={isLoading && !hasData}
        error={hasData ? undefined : error}
        onRetry={() => refetch()}
        isEmpty={!hasData}
        emptyText="暂无全市场成交额数据"
        errorTitle="全市场成交额加载失败"
        minHeight={320}
      >
        {stats && (
          <Row gutter={[16, 12]} style={{ marginBottom: t.space[3] }}>
            <Col xs={12} sm={6}>
              <Card
                size="small"
                style={{
                  background: "var(--c-bg-subtle, rgba(0, 0, 0, 0.02))",
                  borderRadius: t.radius.sm,
                  border: `1px solid ${c.border}`,
                }}
              >
                <Statistic
                  title={<span style={{ fontSize: t.font.xs, color: c.textSecondary }}>最新全市场成交</span>}
                  value={stats.latest.amountYi}
                  precision={1}
                  suffix="亿元"
                  styles={{
                    content: {
                      fontSize: "clamp(16px, 3.5vw, 22px)",
                      fontWeight: Number(t.weight.bold),
                      fontFamily: "var(--c-font-mono)",
                    },
                  }}
                />
                <div style={{ marginTop: 4, display: "flex", alignItems: "center", gap: 4, flexWrap: "wrap" }}>
                  <Text
                    style={{
                      fontSize: t.font.xs,
                      color: stats.latest.changeYi >= 0 ? c.up : c.down,
                      fontFamily: "var(--c-font-mono)",
                    }}
                  >
                    {stats.latest.changeYi >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
                    {stats.latest.changeYi >= 0 ? "+" : ""}
                    {stats.latest.changeYi.toFixed(1)} 亿 ({stats.latest.changePct >= 0 ? "+" : ""}
                    {stats.latest.changePct.toFixed(1)}%)
                  </Text>
                  <Tag
                    color={stats.latest.isHigherThanPrev ? "error" : "success"}
                    style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}
                  >
                    {stats.latest.isHigherThanPrev ? "放量" : "缩量"}
                  </Tag>
                </div>
              </Card>
            </Col>

            <Col xs={12} sm={6}>
              <Card
                size="small"
                style={{
                  background: "var(--c-bg-subtle, rgba(0, 0, 0, 0.02))",
                  borderRadius: t.radius.sm,
                  border: `1px solid ${c.border}`,
                }}
              >
                <Statistic
                  title={<span style={{ fontSize: t.font.xs, color: c.textSecondary }}>20日均量 (MA20)</span>}
                  value={stats.latest.ma20}
                  precision={1}
                  suffix="亿元"
                  styles={{
                    content: {
                      fontSize: "clamp(16px, 3.5vw, 22px)",
                      fontWeight: Number(t.weight.bold),
                      color: "#8b5cf6",
                      fontFamily: "var(--c-font-mono)",
                    },
                  }}
                />
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: t.font.xs }}>
                    量比 {stats.volumeRatio ?? "-"} ·{" "}
                    {(stats.volumeRatio ?? 1) >= 1 ? "高于均量" : "低于均量"}
                  </Text>
                </div>
              </Card>
            </Col>

            <Col xs={12} sm={6}>
              <Card
                size="small"
                style={{
                  background: "var(--c-bg-subtle, rgba(0, 0, 0, 0.02))",
                  borderRadius: t.radius.sm,
                  border: `1px solid ${c.border}`,
                }}
              >
                <Statistic
                  title={<span style={{ fontSize: t.font.xs, color: c.textSecondary }}>区间最高 (天量)</span>}
                  value={stats.maxItem.amountYi}
                  precision={1}
                  suffix="亿元"
                  styles={{
                    content: {
                      fontSize: "clamp(16px, 3.5vw, 22px)",
                      fontWeight: Number(t.weight.bold),
                      color: c.up,
                      fontFamily: "var(--c-font-mono)",
                    },
                  }}
                />
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: t.font.xs }}>
                    {stats.maxItem.date}
                  </Text>
                </div>
              </Card>
            </Col>

            <Col xs={12} sm={6}>
              <Card
                size="small"
                style={{
                  background: "var(--c-bg-subtle, rgba(0, 0, 0, 0.02))",
                  borderRadius: t.radius.sm,
                  border: `1px solid ${c.border}`,
                }}
              >
                <Statistic
                  title={<span style={{ fontSize: t.font.xs, color: c.textSecondary }}>区间最低 (地量)</span>}
                  value={stats.minItem.amountYi}
                  precision={1}
                  suffix="亿元"
                  styles={{
                    content: {
                      fontSize: "clamp(16px, 3.5vw, 22px)",
                      fontWeight: Number(t.weight.bold),
                      color: c.down,
                      fontFamily: "var(--c-font-mono)",
                    },
                  }}
                />
                <div style={{ marginTop: 4 }}>
                  <Text type="secondary" style={{ fontSize: t.font.xs }}>
                    {stats.minItem.date}
                  </Text>
                </div>
              </Card>
            </Col>
          </Row>
        )}

        <div style={{ width: "100%", height: 340 }}>
          <ReactECharts
            echarts={echarts}
            option={chartOption}
            style={{ width: "100%", height: "100%" }}
            notMerge
          />
        </div>
      </SectionDataState>
    </Card>
  );
}
