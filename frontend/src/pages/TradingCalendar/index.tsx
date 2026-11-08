import type { CSSProperties } from "react";
import { useMemo, useState } from "react";
import { Button, Card, Tag, Typography } from "antd";
import { CalendarOutlined, LeftOutlined, RightOutlined } from "@ant-design/icons";
import dayjs from "dayjs";
import { useMarketIndexKline, useMarketIndices, useTradingCalendar } from "../../api/queries";
import PageShell, { PageHeader } from "../../components/page/PageShell";
import SectionDataState from "../../components/SectionDataState";
import { hexToRgba } from "../../charts/utils";
import "./trading-calendar.css";

const { Text } = Typography;

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

function getHeatStyle(heat: DayHeat | undefined, isTrading: boolean): CSSProperties | undefined {
  if (!isTrading || !heat) return undefined;
  const isUp = heat.changePct >= 0;
  const alpha = heatAlpha(heat.changePct);
  return {
    backgroundColor: hexToRgba(isUp ? "#f5222d" : "#52c41a", alpha),
  };
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
      <div className="trading-calendar__header">
        <div className="trading-calendar__month-ctrl">
          <Button type="text" size="small" icon={<LeftOutlined />} aria-label="上一月" onClick={onPrevMonth} />
          <Text strong className="trading-calendar__month-title">
            {year} 年 {month + 1} 月
          </Text>
          <Button type="text" size="small" icon={<RightOutlined />} aria-label="下一月" onClick={onNextMonth} />
          <Tag>{monthTradingCount} 个交易日</Tag>
          {monthStats.up + monthStats.down > 0 ? (
            <>
              <Tag className="trading-calendar__stat-tag--up">
                涨 {monthStats.up}
              </Tag>
              <Tag className="trading-calendar__stat-tag--down">
                跌 {monthStats.down}
              </Tag>
            </>
          ) : null}
          {yearTotalCount != null ? (
            <Text type="secondary" className="trading-calendar__year-total">全年 {yearTotalCount} 个</Text>
          ) : null}
        </div>
        <div className="trading-calendar__legend">
          <span className="trading-calendar__legend-item">
            <i className="trading-calendar__legend-chip trading-calendar__legend-chip--up-deep" />
            <i className="trading-calendar__legend-chip trading-calendar__legend-chip--up-light" />
            涨幅越深越红
          </span>
          <span className="trading-calendar__legend-item">
            <i className="trading-calendar__legend-chip trading-calendar__legend-chip--down-light" />
            <i className="trading-calendar__legend-chip trading-calendar__legend-chip--down-deep" />
            跌幅越深越绿
          </span>
        </div>
      </div>

      <div className="trading-calendar__weekdays">
        {WEEKDAYS.map((label, index) => (
          <div
            key={label}
            className={`trading-calendar__weekday ${index >= 5 ? "trading-calendar__weekday--weekend" : ""}`}
          >
            {label}
          </div>
        ))}
      </div>

      <div className="trading-calendar__grid">
        {cells.map((iso, index) => {
          if (iso === null) return <div key={`blank-${index}`} />;
          const isTrading = tradeDateSet.has(iso);
          const isToday = iso === today;
          const heat = heatMap.get(iso);

          let cellCls = "trading-calendar__cell";
          if (isToday) cellCls += " trading-calendar__cell--today";
          if (!isTrading) cellCls += " trading-calendar__cell--closed";

          let content = (
            <span className="trading-calendar__cell-closed-date">
              {dayjs(iso).date()}
            </span>
          );
          if (isTrading && heat) {
            const isUp = heat.changePct >= 0;
            content = (
              <span className="trading-calendar__cell-content">
                <span className="trading-calendar__cell-date">{dayjs(iso).date()}</span>
                <span className={`trading-calendar__cell-pct financial-num ${isUp ? "trading-calendar__cell-pct--up" : "trading-calendar__cell-pct--down"}`}>
                  {formatPct(heat.changePct)}
                </span>
              </span>
            );
          } else if (isTrading) {
            cellCls += " trading-calendar__cell--trading-empty";
            content = (
              <span className="trading-calendar__cell-date">{dayjs(iso).date()}</span>
            );
          }

          return (
            <div
              key={iso}
              className={cellCls}
              style={getHeatStyle(heat, isTrading)}
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
    <PageShell>
      <PageHeader
        title="交易日历"
        description="查看 A 股交易日安排与上证指数每日涨跌热力。"
      />

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
          className="u-card"
          title={(
            <span className="trading-calendar__card-title">
              <CalendarOutlined className="trading-calendar__title-icon" />
              <span>A 股交易日历</span>
              <Text type="secondary" className="trading-calendar__title-sub">
                · {BENCHMARK_NAME}涨跌热力
              </Text>
            </span>
          )}
          extra={
            query.data ? (
              <span className="trading-calendar__extra-tags">
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
          <Text type="secondary" className="trading-calendar__footer-note">
            交易日按{BENCHMARK_NAME}当日涨跌着色（较前收盘，hover 查看精确数值）；删除线为休市日；
            近一年之外的历史月份仅显示交易日无热力。数据源：新浪交易日历 + 指数日K。
          </Text>
        </Card>
      </SectionDataState>
    </PageShell>
  );
}
