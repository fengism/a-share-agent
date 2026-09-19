import { useMemo, useState } from "react";
import { Button, Card, Tag, Typography } from "antd";
import { CalendarOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useMarketIndexKline, useMarketIndices, useTradingCalendar } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { hexToRgba } from "../../charts/utils";
import { useColors, useStyles, useTokens } from "../../styles/ui";

const { Text, Title, Paragraph } = Typography;

const WEEKDAYS = ["一", "二", "三", "四", "五", "六", "日"];
const BENCHMARK_SYMBOL = "000001"; // 上证指数
const BENCHMARK_NAME = "上证指数";

/** 涨跌幅 → 色块透明度：1% 内浅色，3% 以上接近饱和 */
function heatAlpha(changePct: number) {
  return Math.min(0.55, 0.10 + Math.abs(changePct) * 0.14);
}

function formatPct(value: number) {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

interface DayHeat {
  changePct: number;
}

interface MonthGridProps {
  year: number;
  month: number;
  tradeDateSet: Set<string>;
  heatMap: Map<string, DayHeat>;
  today: string;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  yearTotalCount: number | null;
}

function MonthGrid({
  year,
  month,
  tradeDateSet,
  heatMap,
  today,
  onPrevMonth,
  onNextMonth,
  yearTotalCount,
}: MonthGridProps) {
  const c = useColors();
  const t = useTokens();

  const cells = useMemo(() => {
    const first = dayjs(`${year}-${String(month + 1).padStart(2, "0")}-01`);
    const leading = (first.day() + 6) % 7; // 周一为一周起点
    const list: (string | null)[] = Array.from({ length: leading }, () => null);
    for (let day = 1; day <= first.daysInMonth(); day += 1) {
      list.push(first.date(day).format("YYYY-MM-DD"));
    }
    while (list.length % 7 !== 0) list.push(null);
    return list;
  }, [year, month]);

  const monthPrefix = `${year}-${String(month + 1).padStart(2, "0")}`;
  const monthTradingCount = useMemo(
    () => Array.from(tradeDateSet).filter((iso) => iso.startsWith(monthPrefix)).length,
    [tradeDateSet, monthPrefix],
  );
  const monthStats = useMemo(() => {
    let up = 0;
    let down = 0;
    for (const [iso, heat] of heatMap) {
      if (!iso.startsWith(monthPrefix)) continue;
      if (heat.changePct > 0.05) up += 1;
      else if (heat.changePct < -0.05) down += 1;
    }
    return { up, down };
  }, [heatMap, monthPrefix]);

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", justifyContent: "space-between", alignItems: "center", gap: t.space[2], marginBottom: t.space[3] }}>
        <div style={{ display: "flex", alignItems: "center", gap: t.space[2], flexWrap: "wrap" }}>
          <Button type="text" size="small" icon={<LeftOutlined />} aria-label="上一月" onClick={onPrevMonth} />
          <Text strong style={{ fontSize: t.font.lg, minWidth: 96, textAlign: "center" }}>
            {year} 年 {month + 1} 月
          </Text>
          <Button type="text" size="small" icon={<RightOutlined />} aria-label="下一月" onClick={onNextMonth} />
          <Tag>{monthTradingCount} 个交易日</Tag>
          {monthStats.up + monthStats.down > 0 ? (
            <>
              <Tag style={{ color: c.up, borderColor: hexToRgba(c.up, 0.4), background: hexToRgba(c.up, 0.08) }}>
                涨 {monthStats.up}
              </Tag>
              <Tag style={{ color: c.down, borderColor: hexToRgba(c.down, 0.4), background: hexToRgba(c.down, 0.08) }}>
                跌 {monthStats.down}
              </Tag>
            </>
          ) : null}
          {yearTotalCount != null ? (
            <Text type="secondary" style={{ fontSize: t.font.sm }}>全年 {yearTotalCount} 个</Text>
          ) : null}
        </div>
        <div style={{ display: "inline-flex", gap: t.space[3], fontSize: t.font.xs, color: c.textSecondary, alignItems: "center" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <i style={{ display: "inline-block", width: 14, height: 14, borderRadius: 4, background: hexToRgba(c.up, 0.45) }} />
            <i style={{ display: "inline-block", width: 14, height: 14, borderRadius: 4, background: hexToRgba(c.up, 0.12) }} />
            涨幅越深越红
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            <i style={{ display: "inline-block", width: 14, height: 14, borderRadius: 4, background: hexToRgba(c.down, 0.12) }} />
            <i style={{ display: "inline-block", width: 14, height: 14, borderRadius: 4, background: hexToRgba(c.down, 0.45) }} />
            跌幅越深越绿
          </span>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: t.space[1], marginBottom: t.space[1] }}>
        {WEEKDAYS.map((label, index) => (
          <div
            key={label}
            style={{
              textAlign: "center",
              fontSize: t.font.xs,
              fontWeight: Number(t.weight.semibold),
              color: index >= 5 ? c.textMuted : c.textSecondary,
              padding: `${t.space[1]} 0`,
            }}
          >
            {label}
          </div>
        ))}
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: t.space[1] }}>
        {cells.map((iso, index) => {
          if (iso === null) return <div key={`blank-${index}`} />;
          const isTrading = tradeDateSet.has(iso);
          const isToday = iso === today;
          const heat = heatMap.get(iso);

          let background = "transparent";
          let content = (
            <span style={{ fontSize: t.font.md, color: c.textMuted, textDecoration: "line-through", textDecorationColor: c.textMuted }}>
              {dayjs(iso).date()}
            </span>
          );
          if (isTrading && heat) {
            const color = heat.changePct >= 0 ? c.up : c.down;
            background = hexToRgba(color, heatAlpha(heat.changePct));
            content = (
              <span style={{ display: "flex", flexDirection: "column", alignItems: "center", lineHeight: "var(--c-leading-tight)" }}>
                <span style={{ fontSize: t.font.md, color: c.textPrimary }}>{dayjs(iso).date()}</span>
                <span style={{ fontSize: t.font.xs, fontWeight: Number(t.weight.semibold), color: heat.changePct >= 0 ? c.up : c.down }}>
                  {formatPct(heat.changePct)}
                </span>
              </span>
            );
          } else if (isTrading) {
            background = c.hoverBg;
            content = (
              <span style={{ fontSize: t.font.md, color: c.textPrimary }}>{dayjs(iso).date()}</span>
            );
          }

          return (
            <div
              key={iso}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 52,
                borderRadius: t.radius.md,
                background,
                border: `1.5px solid ${isToday ? c.primary : "transparent"}`,
                boxShadow: isToday ? `0 0 0 2px ${hexToRgba(c.primary, 0.25)}` : "none",
                opacity: isTrading ? 1 : 0.5,
              }}
              title={heat ? `${iso} ${BENCHMARK_NAME} ${formatPct(heat.changePct)}` : iso}
            >
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function TradingCalendar() {
  const t = useTokens();
  const c = useColors();
  const { pageContainerStyle, pageHeaderStyle, pageTitleStyle, pageDescriptionStyle } = useStyles();
  const initial = dayjs();
  const [cursor, setCursor] = useState(() => ({ year: initial.year(), month: initial.month() }));
  const query = useTradingCalendar(cursor.year);
  const klineQuery = useMarketIndexKline(BENCHMARK_SYMBOL, "daily");
  const indicesQuery = useMarketIndices();

  const tradeDateSet = useMemo(
    () => new Set(query.data?.trade_dates ?? []),
    [query.data?.trade_dates],
  );

  // 上证指数日涨跌幅：以前收盘为基准计算历史热力，并融合今日实时指数快照
  const heatMap = useMemo(() => {
    const map = new Map<string, DayHeat>();
    const items = klineQuery.data?.items ?? [];
    for (let index = 1; index < items.length; index += 1) {
      const prev = items[index - 1];
      const current = items[index];
      if (!prev.close || !current.close) continue;
      map.set(current.date, { changePct: (current.close / prev.close - 1) * 100 });
    }

    // 当今天为交易日且历史日K尚未归档今日数据时，使用大盘实时行情补充当日涨跌幅
    const today = query.data?.today ?? dayjs().format("YYYY-MM-DD");
    const isTodayTrading = query.data?.today_is_trading_day || tradeDateSet.has(today);
    if (today && isTodayTrading && !map.has(today)) {
      const shIndex = indicesQuery.data?.indices?.find(
        (idx) =>
          idx.code === BENCHMARK_SYMBOL ||
          idx.code.includes(BENCHMARK_SYMBOL) ||
          idx.name.includes("上证"),
      );
      if (shIndex?.change_pct != null) {
        map.set(today, { changePct: shIndex.change_pct });
      }
    }

    return map;
  }, [
    klineQuery.data?.items,
    query.data?.today,
    query.data?.today_is_trading_day,
    tradeDateSet,
    indicesQuery.data?.indices,
  ]);

  const moveMonth = (delta: number) => {
    setCursor((current) => {
      const next = dayjs(`${current.year}-${String(current.month + 1).padStart(2, "0")}-01`).add(delta, "month");
      return { year: next.year(), month: next.month() };
    });
  };

  return (
    <div style={pageContainerStyle}>
      <div style={pageHeaderStyle}>
        <div className="u-page-title u-page-title--compact">
          <Title level={3} style={pageTitleStyle}>交易日历</Title>
        </div>
        <Paragraph style={pageDescriptionStyle}>查看 A 股交易日安排与上证指数每日涨跌热力。</Paragraph>
      </div>

      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={false}
        errorTitle="交易日历加载失败"
        skeletonRows={8}
        minHeight={480}
      >
        <Card
          title={(
            <span style={{ display: "inline-flex", alignItems: "center", gap: t.space[2] }}>
              <CalendarOutlined style={{ color: c.primary }} />
              <span>A 股交易日历</span>
              <Text type="secondary" style={{ fontSize: t.font.sm, fontWeight: "var(--c-weight-normal)" }}>
                · {BENCHMARK_NAME}涨跌热力
              </Text>
            </span>
          )}
          extra={
            query.data ? (
              <span style={{ display: "inline-flex", gap: t.space[2], alignItems: "center", flexWrap: "wrap" }}>
                <Tag color={query.data.today_is_trading_day ? "red" : "default"}>
                  今天{query.data.today_is_trading_day ? "交易日" : "休市"}
                </Tag>
                {query.data.previous_trading_day ? (
                  <Tag>上一交易日 {query.data.previous_trading_day.slice(5)}</Tag>
                ) : null}
                {query.data.next_trading_day ? (
                  <Tag>下一交易日 {query.data.next_trading_day.slice(5)}</Tag>
                ) : null}
                {query.data.degraded ? <Tag color="warning">降级：按工作日近似</Tag> : null}
              </span>
            ) : null
          }
        >
          <MonthGrid
            year={cursor.year}
            month={cursor.month}
            tradeDateSet={tradeDateSet}
            heatMap={heatMap}
            today={query.data?.today ?? ""}
            onPrevMonth={() => moveMonth(-1)}
            onNextMonth={() => moveMonth(1)}
            yearTotalCount={query.data?.count ?? null}
          />
          <Text type="secondary" style={{ fontSize: t.font.xs, display: "block", marginTop: t.space[3] }}>
            交易日按{BENCHMARK_NAME}当日涨跌着色（较前收盘，hover 查看精确数值）；删除线为休市日；
            近一年之外的历史月份仅显示交易日无热力。数据源：新浪交易日历 + 指数日K。
          </Text>
        </Card>
      </SectionDataState>
    </div>
  );
}
