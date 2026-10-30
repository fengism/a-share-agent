import { useMemo } from "react";
import { AutoComplete, Button, Empty, Spin, Tag, Tooltip } from "antd";
import { CloseOutlined, LineChartOutlined, PlusOutlined } from "@ant-design/icons";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import ChangeValue from "../../components/ChangeValue";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors } from "../../styles/ui";
import {
  useConceptIndexSeries,
  useConceptList,
  type ConceptIndexPoint,
} from "../../api/queryHooks/concept";

interface Props {
  /** 主概念（当前选中的概念） */
  mainConcept: string;
  /** 对比概念（不含主概念，最多 2 个） */
  compareConcepts: string[];
  days: number;
  onAdd: (name: string) => void;
  onRemove: (name: string) => void;
  onSelectMain: (name: string) => void;
}

/** 对比线颜色：主概念用主题色，对比概念依次用涨/跌色 */
function seriesColors(c: { primary: string; up: string; down: string }) {
  return [c.primary, c.up, c.down];
}

function toPctSeries(points: ConceptIndexPoint[]): Array<[string, number]> {
  if (!points.length) return [];
  const base = points[0].close;
  if (!base) return [];
  return points.map((point) => [point.date, (point.close / base - 1) * 100]);
}

/**
 * 概念对比：把当前概念与最多 2 个概念的同区间合成指数归一化成涨跌幅曲线叠加，
 * 回答"同一时间段谁更强"。数据与单概念指数共享缓存。
 */
export default function ConceptComparePanel({
  mainConcept,
  compareConcepts,
  days,
  onAdd,
  onRemove,
  onSelectMain,
}: Props) {
  const c = useColors();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const listQuery = useConceptList();
  const concepts = useMemo(() => listQuery.data?.items ?? [], [listQuery.data]);

  const allNames = useMemo(
    () => [mainConcept, ...compareConcepts].filter(Boolean),
    [mainConcept, compareConcepts],
  );
  const seriesQueries = useConceptIndexSeries(allNames, days);

  const loaded = allNames.map((name, index) => ({
    name,
    main: index === 0,
    points: seriesQueries[index]?.data?.items as ConceptIndexPoint[] | undefined,
    isLoading: seriesQueries[index]?.isLoading ?? false,
  }));

  const option = useMemo(() => {
    const colors = seriesColors(c);
    const series = loaded
      .filter((item) => item.points?.length)
      .map((item, index) => ({
        name: item.name,
        type: "line" as const,
        showSymbol: false,
        // 主概念加粗，对比概念细线
        lineStyle: { width: item.main ? 2.4 : 1.6 },
        emphasis: { focus: "series" as const },
        itemStyle: { color: colors[index % colors.length] },
        data: toPctSeries(item.points ?? []),
      }));
    if (!series.length) return null;
    return {
      animation: false,
      grid: { left: 8, right: 8, top: 34, bottom: 8, containLabel: true },
      legend: {
        top: 0,
        textStyle: { color: c.textSecondary, fontSize: 11 },
        itemWidth: 14,
        itemHeight: 8,
      },
      tooltip: {
        trigger: "axis" as const,
        valueFormatter: (value: number) => `${value >= 0 ? "+" : ""}${value?.toFixed(2)}%`,
        backgroundColor: c.elevatedBg,
        borderColor: c.border,
        textStyle: { color: c.textPrimary, fontSize: 12 },
      },
      xAxis: {
        type: "time",
        axisLabel: { color: c.textMuted, fontSize: 11 },
        axisLine: { lineStyle: { color: c.border } },
        splitLine: { show: false },
      },
      yAxis: {
        type: "value",
        axisLabel: {
          color: c.textMuted,
          fontSize: 11,
          formatter: (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(0)}%`,
        },
        splitLine: { lineStyle: { color: c.border, opacity: 0.4 } },
      },
      series,
    };
  }, [loaded, c]);

  // 添加概念的候选：本地概念列表，排除已选
  const candidates = useMemo(
    () => concepts.filter((item) => !allNames.includes(item.name)),
    [concepts, allNames],
  );
  const canAdd = compareConcepts.length < 2;

  return (
    <div className="concept-compare" style={{ display: "flex", flexDirection: "column", gap: 10, minWidth: 0 }}>
      <div className="concept-compare__toolbar" style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        <span className="concept-compare__label" style={{ color: c.textMuted, fontSize: 12 }}>
          <LineChartOutlined /> 对比组合
        </span>
        {[{ name: mainConcept, main: true }, ...compareConcepts.map((name) => ({ name, main: false }))].map(
          (item) => (
            <Tag
              key={item.name}
              style={{
                marginInlineEnd: 0,
                cursor: item.main ? "default" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
              }}
              onClick={item.main ? undefined : () => onRemove(item.name)}
            >
              {item.main ? (
                <Tooltip title="当前概念；点击对比列表中的概念名可查看其单概念走势">
                  <a role="button" onClick={() => onSelectMain(item.name)} style={{ color: "inherit" }}>
                    {item.name}
                  </a>
                </Tooltip>
              ) : (
                <>
                  {item.name}
                  <CloseOutlined style={{ fontSize: 10 }} aria-label={`移出对比-${item.name}`} />
                </>
              )}
            </Tag>
          ),
        )}
        {canAdd ? (
          <AutoComplete
            size="small"
            style={{ width: isNarrow ? 140 : 200 }}
            filterOption={(input, option) =>
              String(option?.value ?? "").toLowerCase().includes(input.trim().toLowerCase())
            }
            options={candidates.slice(0, 20).map((item) => ({ value: item.name }))}
            onSelect={(value) => onAdd(String(value))}
            placeholder={isNarrow ? "添加对比" : "搜索并添加对比概念"}
          />
        ) : (
          <Tooltip title="最多对比 2 个概念（加上当前概念共 3 条线）">
            <Button size="small" icon={<PlusOutlined />} disabled>
              添加
            </Button>
          </Tooltip>
        )}
        <span style={{ fontSize: 11, color: c.textMuted }}>
          归一化为区间涨跌幅，消除基期差异
        </span>
      </div>

      <Spin spinning={loaded.some((item) => item.isLoading) && !option}>
        {option ? (
          <ReactEChartsCore
            echarts={echarts}
            option={option}
            style={{ height: isNarrow ? 280 : 380, width: "100%" }}
            notMerge
            lazyUpdate
          />
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无对比数据：等待指数合成或添加对比概念"
            style={{ padding: isNarrow ? 40 : 80 }}
          />
        )}
      </Spin>

      <div className="concept-compare__legend">
        {loaded
          .filter((item) => item.points?.length)
          .map((item) => {
            const pct = toPctSeries(item.points ?? []).at(-1)?.[1] ?? null;
            return (
              <span key={item.name} className="concept-compare__legend-item">
                <span
                  className="financial-num"
                  style={{ color: c.textMuted, cursor: item.main ? "default" : "pointer" }}
                  onClick={item.main ? undefined : () => onRemove(item.name)}
                >
                  {item.name}
                </span>
                <ChangeValue value={pct} digits={2} />
              </span>
            );
          })}
      </div>
    </div>
  );
}
