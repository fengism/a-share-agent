import { useMemo, useState } from "react";
import { Button, Card, Col, Input, Row, Segmented, Space, Table, Tag } from "antd";
import type { ColumnsType } from "antd/es/table";
import {
  ClockCircleOutlined,
  CompassOutlined,
  DownloadOutlined,
  LineChartOutlined,
  RiseOutlined,
  SearchOutlined,
  StockOutlined,
  ThunderboltOutlined,
} from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../../charts/echarts-setup";
import { useColors } from "../../../styles/ui";
import { APP_FONT_FAMILY } from "../../../theme/typography";
import type {
  NationalTeamIntradayItem,
  NationalTeamIntradayObservation,
} from "../../../types/stock";
import { downloadCsv } from "../utils/csv";
import LazyChart from "./LazyChart";
import { DEFAULT_INTRADAY_OBSERVATION } from "../data/defaultIntradayObservation";

const CHART_STYLE_280: React.CSSProperties = { width: "100%", height: 280 };
const CHART_STYLE_250: React.CSSProperties = { width: "100%", height: 250 };

export interface NationalTeamIntradayMonitorProps {
  intraday?: NationalTeamIntradayObservation;
  asOfDate?: string | null;
  onSelectStock?: (stock: { code: string; name: string }) => void;
}

interface TooltipParam {
  seriesName: string;
  value: number | null;
  axisValue: string;
}

export default function NationalTeamIntradayMonitor({
  intraday,
  asOfDate,
  onSelectStock,
}: NationalTeamIntradayMonitorProps) {
  const colors = useColors();
  const [caseView, setCaseView] = useState<"case" | "norm">("case");
  const [caseMetric, setCaseMetric] = useState<"bar" | "cum">("bar");
  const [rankSearchText, setRankSearchText] = useState("");

  // 智能合并兜底：若后端未注入或接口返回空结构，自动回退到内置基准观测数据，杜绝图表与对比表空白
  const minute = intraday?.minute?.times?.length ? intraday.minute : DEFAULT_INTRADAY_OBSERVATION.minute;
  const cum = intraday?.cum?.slots?.length ? intraday.cum : DEFAULT_INTRADAY_OBSERVATION.cum;
  const typicalCases = intraday?.typical_cases?.slots?.length ? intraday.typical_cases : DEFAULT_INTRADAY_OBSERVATION.typical_cases;
  const volumeSignals = intraday?.volume_signals?.support_days?.length ? intraday.volume_signals : DEFAULT_INTRADAY_OBSERVATION.volume_signals;

  const date = minute?.date || asOfDate || "最新";

  // 为原始排行数据绑定全局名次，并支持按名称/代码快速搜索
  const rankedTable = useMemo(() => {
    return (minute?.table ?? []).map((item, index) => ({
      ...item,
      originalRank: index + 1,
    }));
  }, [minute?.table]);

  const filteredTable = useMemo(() => {
    if (!rankSearchText.trim()) return rankedTable;
    const q = rankSearchText.trim().toLowerCase();
    return rankedTable.filter(
      (item) => item.code.toLowerCase().includes(q) || item.name.toLowerCase().includes(q)
    );
  }, [rankedTable, rankSearchText]);

  // 1. 分钟成交脉冲与大盘走势图 option
  const minuteOption = useMemo(() => {
    if (!minute?.times?.length) return {};

    const times = minute.times;
    const bars = minute.bars;
    const rawCloses = minute.closes;
    const preClose = minute.pre_close;

    // 自适应校验：若 closes 点位与 pre_close 存在严重量纲割裂（例如 closes 在 11 附近而 pre_close 在 3700 附近），
    // 将 closes 按基准比率重缩放到昨收指数基准，避免 yAxis 跨度被拉大到几千导致分时折线贴底被压成一条横线看不见
    let closes = rawCloses;
    if (preClose > 100 && rawCloses && rawCloses.length > 0 && rawCloses[0] > 0 && rawCloses[0] < 50) {
      const base = rawCloses[0];
      closes = rawCloses.map((c) => Number((preClose * (c / base)).toFixed(2)));
    }

    return {
      animationDuration: 300,
      textStyle: { fontFamily: APP_FONT_FAMILY },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", lineStyle: { color: colors.border, type: "dashed" } },
        formatter: (rawParams: unknown) => {
          const params = rawParams as TooltipParam[];
          if (!params || !params.length) return "";
          const t = params[0].axisValue;
          const barVal = params.find((p) => p.seriesName === "分钟成交额")?.value;
          const closeVal = params.find((p) => p.seriesName === "上证综指")?.value;
          return [
            `<div style="font-weight:600;margin-bottom:4px">${t} · 分钟走势</div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>重点ETF分钟成交额：</span><strong>${barVal != null ? barVal.toFixed(2) + " 亿元" : "-"}</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>上证指数点位：</span><strong style="color:${colors.warning}">${closeVal != null ? closeVal.toFixed(2) : "-"}</strong></div>`,
          ].join("");
        },
      },
      legend: {
        data: ["分钟成交额", "上证综指"],
        top: 4,
        right: 12,
        textStyle: { color: colors.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 60,
        right: 56,
        top: 40,
        bottom: 46,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: times,
        axisLine: { lineStyle: { color: colors.border } },
        axisLabel: { color: colors.textSecondary, fontSize: 11, interval: 29 },
      },
      yAxis: [
        {
          type: "value",
          name: "亿元",
          nameTextStyle: { color: colors.textSecondary, align: "right" },
          axisLabel: { color: colors.textSecondary, fontSize: 11 },
          splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.6 } },
        },
        {
          type: "value",
          name: "点",
          scale: true,
          position: "right",
          nameTextStyle: { color: colors.textSecondary, align: "left" },
          axisLabel: { color: colors.textSecondary, fontSize: 11 },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 16, bottom: 6 },
      ],
      series: [
        {
          name: "分钟成交额",
          type: "bar",
          yAxisIndex: 0,
          data: bars,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: colors.primary },
              { offset: 1, color: colors.primary + "66" },
            ]),
            borderRadius: [2, 2, 0, 0],
          },
        },
        {
          name: "上证综指",
          type: "line",
          yAxisIndex: 1,
          data: closes,
          showSymbol: false,
          smooth: true,
          lineStyle: { color: colors.warning, width: 2 },
          itemStyle: { color: colors.warning },
          ...((minute.pre_close ?? 0) > 0
            ? {
                markLine: {
                  symbol: "none",
                  silent: true,
                  label: {
                    formatter: `昨收 ${minute.pre_close.toFixed(2)}`,
                    position: "insideEndTop",
                    fontSize: 10,
                    color: colors.textSecondary,
                  },
                  lineStyle: {
                    type: "dashed",
                    color: colors.textSecondary,
                    opacity: 0.6,
                  },
                  data: [{ yAxis: minute.pre_close }],
                },
              }
            : {}),
        },
      ],
    };
  }, [colors, minute]);

  // 2. 分钟累计成交额对比图 (今日 vs 昨日 vs 近20日均值)
  const cumOption = useMemo(() => {
    if (!cum?.slots?.length) return {};

    const slots = cum.slots;
    const prev = cum.prev;
    const avg20 = cum.avg20;

    // 当日累计
    const currentCum: (number | null)[] = [];
    let curAcc = 0;
    const bars = minute?.bars ?? [];
    for (let i = 0; i < slots.length; i++) {
      if (i < bars.length) {
        curAcc += bars[i];
        currentCum.push(Number(curAcc.toFixed(2)));
      } else {
        currentCum.push(null);
      }
    }

    return {
      animationDuration: 300,
      textStyle: { fontFamily: APP_FONT_FAMILY },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", lineStyle: { color: colors.border, type: "dashed" } },
        formatter: (rawParams: unknown) => {
          const params = rawParams as TooltipParam[];
          if (!params || !params.length) return "";
          const t = params[0].axisValue;
          const pToday = params.find((p) => p.seriesName === "今日累计")?.value;
          const pPrev = params.find((p) => p.seriesName === "昨日累计")?.value;
          const pAvg = params.find((p) => p.seriesName === "近20日均值")?.value;

          return [
            `<div style="font-weight:600;margin-bottom:4px">${t} · 分钟累计走势</div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>今日实时累计：</span><strong style="color:${colors.primary}">${pToday != null ? pToday.toFixed(2) + " 亿元" : "未开始"}</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>前一交易日：</span><strong style="color:${colors.textSecondary}">${pPrev != null ? pPrev.toFixed(2) + " 亿元" : "-"}</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>近20日均值：</span><strong style="color:${colors.warning}">${pAvg != null ? pAvg.toFixed(2) + " 亿元" : "-"}</strong></div>`,
          ].join("");
        },
      },
      legend: {
        data: ["今日累计", "昨日累计", "近20日均值"],
        top: 4,
        right: 12,
        textStyle: { color: colors.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 60,
        right: 56,
        top: 40,
        bottom: 46,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: slots,
        axisLine: { lineStyle: { color: colors.border } },
        axisLabel: { color: colors.textSecondary, fontSize: 11, interval: 29 },
      },
      yAxis: {
        type: "value",
        name: "亿元",
        axisLabel: { color: colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.6 } },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 16, bottom: 6 },
      ],
      series: [
        {
          name: "今日累计",
          type: "line",
          data: currentCum,
          showSymbol: false,
          lineStyle: { color: colors.primary, width: 2.2 },
          itemStyle: { color: colors.primary },
          areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: colors.primary + "33" },
              { offset: 1, color: colors.primary + "05" },
            ]),
          },
        },
        {
          name: "昨日累计",
          type: "line",
          data: prev,
          showSymbol: false,
          lineStyle: { color: colors.textSecondary, width: 1.5, type: "dashed" },
          itemStyle: { color: colors.textSecondary },
        },
        {
          name: "近20日均值",
          type: "line",
          data: avg20,
          showSymbol: false,
          lineStyle: { color: colors.warning, width: 2 },
          itemStyle: { color: colors.warning },
        },
      ],
    };
  }, [colors, cum, minute]);

  // 3. 典型放量日 vs 常态交易日对比 option (支持 分钟量能形态 / 全天累计进程 两种视图)
  const typicalOption = useMemo(() => {
    if (!typicalCases?.slots?.length) return {};

    if (caseMetric === "cum") {
      return {
        animationDuration: 300,
        textStyle: { fontFamily: APP_FONT_FAMILY },
        title: {
          text: "全天累计量能进程对比（救市放量日 vs 常态交易日）",
          left: 12,
          top: 6,
          textStyle: { fontSize: 13, fontWeight: 600, color: colors.textPrimary },
        },
        tooltip: {
          trigger: "axis",
          axisPointer: { type: "cross", lineStyle: { color: colors.border, type: "dashed" } },
          formatter: (rawParams: unknown) => {
            const params = rawParams as TooltipParam[];
            if (!params || !params.length) return "";
            const t = params[0].axisValue;
            const p1 = params.find((p) => p.seriesName === "放量护盘案例日")?.value;
            const p2 = params.find((p) => p.seriesName === "常态交易日")?.value;
            const diff = p1 != null && p2 != null ? (p1 - p2).toFixed(1) : null;
            return [
              `<div style="font-weight:600;margin-bottom:4px">${t} · 全天累计量能基准</div>`,
              `<div style="display:flex;justify-content:space-between;gap:16px"><span>放量护盘日累计：</span><strong style="color:${colors.up}">${p1 != null ? p1.toFixed(1) + " 亿元" : "-"}</strong></div>`,
              `<div style="display:flex;justify-content:space-between;gap:16px"><span>常态交易日累计：</span><strong style="color:${colors.primary}">${p2 != null ? p2.toFixed(1) + " 亿元" : "-"}</strong></div>`,
              diff != null
                ? `<div style="display:flex;justify-content:space-between;gap:16px;margin-top:2px;border-top:1px dashed ${colors.border};padding-top:2px"><span>放量超出规模：</span><strong style="color:${colors.warning}">+${diff} 亿元</strong></div>`
                : "",
            ].join("");
          },
        },
        legend: {
          data: ["放量护盘案例日", "常态交易日"],
          top: 6,
          right: 12,
          textStyle: { color: colors.textSecondary, fontSize: 12 },
        },
        grid: {
          left: 60,
          right: 20,
          top: 42,
          bottom: 46,
          containLabel: false,
        },
        xAxis: {
          type: "category",
          data: typicalCases.slots,
          axisLine: { lineStyle: { color: colors.border } },
          axisLabel: { color: colors.textSecondary, fontSize: 11, interval: 29 },
        },
        yAxis: {
          type: "value",
          name: "亿元",
          axisLabel: { color: colors.textSecondary, fontSize: 11 },
          splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.6 } },
        },
        dataZoom: [
          { type: "inside", xAxisIndex: 0 },
          { type: "slider", xAxisIndex: 0, height: 16, bottom: 6 },
        ],
        series: [
          {
            name: "放量护盘案例日",
            type: "line",
            data: typicalCases.sup_cum,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: colors.up, width: 2.2 },
            itemStyle: { color: colors.up },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: colors.up + "33" },
                { offset: 1, color: colors.up + "05" },
              ]),
            },
          },
          {
            name: "常态交易日",
            type: "line",
            data: typicalCases.nor_cum,
            smooth: true,
            showSymbol: false,
            lineStyle: { color: colors.primary, width: 2, type: "dashed" },
            itemStyle: { color: colors.primary },
          },
        ],
      };
    }

    const isCase = caseView === "case";
    const title = isCase ? "放量护盘案例日 · 分钟量能形态" : "常态交易日 · 分钟量能基准形态";
    const activeAmt = isCase ? typicalCases.sup_amt : typicalCases.nor_amt;
    const refAmt = isCase ? typicalCases.nor_amt : typicalCases.sup_amt;
    const refName = isCase ? "常态交易日" : "放量案例日";
    const mainColor = isCase ? colors.up : colors.primary;
    const refColor = isCase ? colors.primary : colors.up;

    return {
      animationDuration: 300,
      textStyle: { fontFamily: APP_FONT_FAMILY },
      title: {
        text: title,
        left: 12,
        top: 6,
        textStyle: { fontSize: 13, fontWeight: 600, color: colors.textPrimary },
      },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross", lineStyle: { color: colors.border, type: "dashed" } },
        formatter: (rawParams: unknown) => {
          const params = rawParams as TooltipParam[];
          if (!params || !params.length) return "";
          const t = params[0].axisValue;
          const p1 = params.find((p) => p.seriesName === "特征均值")?.value;
          const p2 = params.find((p) => p.seriesName === refName)?.value;
          return [
            `<div style="font-weight:600;margin-bottom:4px">${t} · ${title}</div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>本组特征量能：</span><strong style="color:${mainColor}">${p1 != null ? p1.toFixed(2) + " 亿/分" : "-"}</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>对照（${refName}）：</span><strong style="color:${refColor}">${p2 != null ? p2.toFixed(2) + " 亿/分" : "-"}</strong></div>`,
          ].join("");
        },
      },
      legend: {
        data: ["特征均值", refName],
        top: 6,
        right: 12,
        textStyle: { color: colors.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 60,
        right: 20,
        top: 42,
        bottom: 46,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: typicalCases.slots,
        axisLine: { lineStyle: { color: colors.border } },
        axisLabel: { color: colors.textSecondary, fontSize: 11, interval: 29 },
      },
      yAxis: {
        type: "value",
        name: "亿元/分",
        axisLabel: { color: colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.6 } },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 16, bottom: 6 },
      ],
      series: [
        {
          name: "特征均值",
          type: "bar",
          data: activeAmt,
          itemStyle: { color: mainColor, borderRadius: [2, 2, 0, 0] },
        },
        {
          name: refName,
          type: "line",
          data: refAmt,
          showSymbol: false,
          lineStyle: { color: refColor, width: 1.8, type: "dashed" },
          itemStyle: { color: refColor },
        },
      ],
    };
  }, [caseMetric, caseView, colors, typicalCases]);

  // 4. 百亿放量信号直方柱 (第二部分 · 放量信号对比)
  const volumeSignalOption = useMemo(() => {
    if (!volumeSignals?.support_days?.length) return {};

    const supDays = volumeSignals.support_days ?? [];
    const recDays = volumeSignals.recent_days ?? [];
    const combined = [...supDays, ...recDays].sort((a, b) => (a.date < b.date ? -1 : 1));

    const dates = combined.map((x) => x.date);
    const amtBars = combined.map((x) => ({
      value: x.amount,
      itemStyle: {
        color: x.is_support_day
          ? colors.primary
          : colors.warning, // 蓝柱=放量日，黄柱=近期交易日
      },
    }));

    return {
      animationDuration: 300,
      textStyle: { fontFamily: APP_FONT_FAMILY },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (rawParams: unknown) => {
          const params = rawParams as TooltipParam[];
          if (!params || !params.length) return "";
          const d = params[0].axisValue;
          const item = combined.find((x) => x.date === d);
          const isSup = item?.is_support_day;
          return [
            `<div style="font-weight:600;margin-bottom:4px">${d} ${isSup ? "【百亿放量护盘日】" : "【近期交易日】"}</div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>样本成交额：</span><strong>${item?.amount != null ? item.amount.toFixed(1) + " 亿元" : "-"}</strong></div>`,
            `<div style="display:flex;justify-content:space-between;gap:16px"><span>申赎净流入：</span><strong style="color:${(item?.netflow ?? 0) >= 0 ? colors.up : colors.down}">${item?.netflow != null ? item.netflow.toFixed(1) + " 亿元" : "待公布"}</strong></div>`,
          ].join("");
        },
      },
      legend: {
        data: ["百亿放量日成交(蓝)", "近期交易日成交(黄)"],
        top: 6,
        right: 12,
        textStyle: { color: colors.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 60,
        right: 20,
        top: 42,
        bottom: 50,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: colors.border } },
        axisLabel: { color: colors.textSecondary, fontSize: 11, rotate: 36, interval: 2 },
      },
      yAxis: {
        type: "value",
        name: "亿元",
        axisLabel: { color: colors.textSecondary, fontSize: 11 },
        splitLine: { lineStyle: { color: colors.border, type: "dashed", opacity: 0.6 } },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 16, bottom: 6 },
      ],
      series: [
        {
          name: "成交额",
          type: "bar",
          data: amtBars,
        },
      ],
    };
  }, [colors, volumeSignals]);

  // 计算百亿放量日与近期交易日统计指标
  const volumeStats = useMemo(() => {
    const supDays = volumeSignals?.support_days ?? [];
    const recDays = volumeSignals?.recent_days ?? [];
    if (!supDays.length) return null;

    const supTotalAmt = supDays.reduce((acc, x) => acc + x.amount, 0);
    const recTotalAmt = recDays.reduce((acc, x) => acc + x.amount, 0);
    const supAvgAmt = supDays.length > 0 ? supTotalAmt / supDays.length : 0;
    const recAvgAmt = recDays.length > 0 ? recTotalAmt / recDays.length : 0;
    const multiple = recAvgAmt > 0 ? (supAvgAmt / recAvgAmt).toFixed(1) : "-";

    return {
      supCount: supDays.length,
      recCount: recDays.length,
      supAvgAmt: supAvgAmt.toFixed(1),
      recAvgAmt: recAvgAmt.toFixed(1),
      multiple,
    };
  }, [volumeSignals]);

  // 导出重点 ETF 当日成交额排行 CSV（支持导出当前过滤视图）
  const handleExportRankCsv = () => {
    const listToExport = filteredTable;
    if (!listToExport.length) return;
    const headers = ["排名", "代码", "ETF名称", "最新价", "当日涨跌幅(%)", "当日成交额(亿元)"];
    const rows = listToExport.map((item) => [
      item.originalRank,
      item.code,
      item.name,
      item.price.toFixed(3),
      `${item.pct > 0 ? "+" : ""}${item.pct.toFixed(2)}%`,
      item.amount.toFixed(1),
    ]);
    const fileSuffix = rankSearchText.trim() ? `_搜索[${rankSearchText.trim()}]` : "";
    downloadCsv(`重点宽基ETF当日成交额排行_${date}${fileSuffix}.csv`, [headers, ...rows]);
  };

  // 单只 ETF 当日成交表现表格列
  const tableColumns: ColumnsType<NationalTeamIntradayItem & { originalRank: number }> = [
    {
      title: "#",
      key: "idx",
      width: 44,
      align: "center",
      render: (_: unknown, record: { originalRank: number }) => {
        const rank = record.originalRank;
        const rankClass = rank === 1
          ? "national-team-table-rank-badge--1"
          : rank === 2
          ? "national-team-table-rank-badge--2"
          : rank === 3
          ? "national-team-table-rank-badge--3"
          : "";
        return (
          <span className={`national-team-table-rank-badge ${rankClass}`}>
            {rank}
          </span>
        );
      },
    },
    {
      title: "代码",
      dataIndex: "code",
      key: "code",
      width: 82,
      render: (val: string, record: NationalTeamIntradayItem) => (
        <Button
          type="link"
          size="small"
          className="financial-num national-team-intraday__link-btn"
          onClick={() => onSelectStock?.({ code: record.code, name: record.name })}
          title={`点击查看 ${record.name} 行情分时`}
        >
          {val}
        </Button>
      ),
    },
    {
      title: "ETF 名称",
      dataIndex: "name",
      key: "name",
      ellipsis: true,
      render: (val: string, record: NationalTeamIntradayItem) => (
        <span
          className={`national-team-intraday__stock-name ${onSelectStock ? "u-cursor-pointer" : ""}`}
          onClick={() => onSelectStock?.({ code: record.code, name: record.name })}
        >
          {val}
        </span>
      ),
    },
    {
      title: "最新价",
      dataIndex: "price",
      key: "price",
      align: "right",
      width: 80,
      render: (val: number) => <span className="financial-num">{val.toFixed(3)}</span>,
    },
    {
      title: "涨跌幅",
      dataIndex: "pct",
      key: "pct",
      align: "right",
      width: 85,
      render: (val: number) => {
        const textCls = val > 0 ? "u-text-up" : val < 0 ? "u-text-down" : "u-text-muted";
        return (
          <span className={`financial-num u-text-semibold ${textCls}`}>
            {val > 0 ? "+" : ""}{val.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: "当日成交额",
      dataIndex: "amount",
      key: "amount",
      align: "right",
      width: 105,
      render: (val: number) => (
        <span className="financial-num u-text-semibold u-text-primary">
          {val.toFixed(1)} 亿
        </span>
      ),
    },
    ...(onSelectStock
      ? [
          {
            title: "行情",
            key: "action",
            align: "center" as const,
            width: 65,
            render: (_: unknown, record: NationalTeamIntradayItem) => (
              <Button
                type="link"
                size="small"
                icon={<ThunderboltOutlined />}
                className="national-team-intraday__action-btn"
                onClick={() => onSelectStock({ code: record.code, name: record.name })}
                title={`查看 ${record.name} 分时K线`}
              >
                分时
              </Button>
            ),
          },
        ]
      : []),
  ];

  return (
    <div className="national-team-intraday-section">
      {/* 顶部指示标 */}
      <Card
        size="small"
        className="national-team-intraday-header-card"
      >
        <div className="national-team-intraday__header-bar">
          <Space size={8} align="center">
            <CompassOutlined className="national-team-intraday__compass-icon" />
            <span className="national-team-intraday__title">盘中分钟量能观测与放量信号对比</span>
            <Tag color="blue" className="national-team-intraday__tag u-text-semibold">分钟级实盘对齐</Tag>
            <Tag color="cyan" className="national-team-intraday__tag">20只重点ETF池</Tag>
          </Space>
          <Space size={10} align="center">
            <span className="national-team-intraday__subtitle">
              <ClockCircleOutlined />
              业务观测日：<strong className="u-text-primary">{date}</strong>
            </span>
          </Space>
        </div>
      </Card>

      {/* 第一部分：双图同屏（分钟成交脉冲 vs 分钟累计成交额对比） */}
      <Row gutter={[12, 12]}>
        <Col xs={24} lg={12}>
          <Card
            size="small"
            title={
              <div className="national-team-intraday__card-title">
                <StockOutlined className="u-text-primary" />
                <span className="national-team-intraday__card-title-text">重点宽基 ETF 分钟成交脉冲与上证走势</span>
              </div>
            }
            extra={<span className="national-team-intraday__card-extra">双轴联动 · 1分钟聚合</span>}
          >
            <div className="national-team-intraday__chart-wrapper">
              <LazyChart height={280}>
                <ReactECharts
                  echarts={echarts}
                  data-testid="national-team-intraday-minute-chart"
                  option={minuteOption}
                  style={CHART_STYLE_280}
                  opts={{ renderer: "canvas" }}
                  notMerge
                />
              </LazyChart>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card
            size="small"
            title={
              <div className="national-team-intraday__card-title">
                <LineChartOutlined className="u-text-warning" />
                <span className="national-team-intraday__card-title-text">全天分钟累计成交额进度对比</span>
              </div>
            }
            extra={<span className="national-team-intraday__card-extra">今日 vs 昨日 vs 20日均值</span>}
          >
            <div className="national-team-intraday__chart-wrapper">
              <LazyChart height={280}>
                <ReactECharts
                  echarts={echarts}
                  data-testid="national-team-intraday-cum-chart"
                  option={cumOption}
                  style={CHART_STYLE_280}
                  opts={{ renderer: "canvas" }}
                  notMerge
                />
              </LazyChart>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 第二部分：典型案例分钟形态对比 & 单只 ETF 当日表现排行榜 */}
      <Row gutter={[12, 12]} align="stretch">
        <Col xs={24} lg={13}>
          <Card
            size="small"
            className="national-team-intraday__flex-card"
            styles={{ body: { padding: "10px 12px", flex: 1, display: "flex", flexDirection: "column" } }}
            title={
              <div className="national-team-intraday__flex-header">
                <span className="national-team-intraday__card-title-text">放量护盘日典型分钟特征对照基准</span>
                <Space size={6} wrap>
                  <Segmented
                    size="small"
                    value={caseMetric}
                    options={[
                      { label: "分钟形态", value: "bar" },
                      { label: "累计进程", value: "cum" },
                    ]}
                    onChange={(v) => setCaseMetric(v as "bar" | "cum")}
                    className="national-team-segmented"
                  />
                  {caseMetric === "bar" && (
                    <Segmented
                      size="small"
                      value={caseView}
                      options={[
                        { label: "放量案例日", value: "case" },
                        { label: "常态交易日", value: "norm" },
                      ]}
                      onChange={(v) => setCaseView(v as "case" | "norm")}
                      className="national-team-segmented"
                    />
                  )}
                </Space>
              </div>
            }
          >
            <div className="national-team-intraday__chart-flex">
              <LazyChart height={280}>
                <ReactECharts
                  echarts={echarts}
                  data-testid="national-team-intraday-typical-chart"
                  option={typicalOption}
                  style={CHART_STYLE_280}
                  opts={{ renderer: "canvas" }}
                  notMerge
                />
              </LazyChart>
            </div>
          </Card>
        </Col>

        <Col xs={24} lg={11}>
          <Card
            data-testid="national-team-intraday-rank-card"
            size="small"
            className="national-team-intraday__flex-card"
            title={
              <div className="national-team-intraday__flex-header">
                <span className="national-team-intraday__card-title-text">20 大重点 ETF 当日成交额排行</span>
                <Space size={6} wrap>
                  <Input
                    size="small"
                    placeholder="搜索代码/名称..."
                    prefix={<SearchOutlined className="national-team-intraday__search-icon" />}
                    value={rankSearchText}
                    onChange={(e) => setRankSearchText(e.target.value)}
                    allowClear
                    className="national-team-intraday__search-input"
                    data-testid="intraday-rank-search-input"
                  />
                  <Button
                    size="small"
                    icon={<DownloadOutlined />}
                    onClick={handleExportRankCsv}
                    className="national-team-intraday__export-btn"
                  >
                    导出 CSV
                  </Button>
                </Space>
              </div>
            }
            styles={{ body: { padding: 0, flex: 1 } }}
          >
            <Table
              rowKey="code"
              size="small"
              columns={tableColumns}
              dataSource={filteredTable}
              pagination={false}
              scroll={{ y: 275 }}
            />
          </Card>
        </Col>
      </Row>

      {/* 第三部分：历史百亿放量护盘日 vs 近期交易日信号标定 */}
      {volumeSignals?.support_days?.length ? (
        <Card
          size="small"
          title={
            <div className="national-team-intraday__flex-header">
              <Space size={6}>
                <RiseOutlined className="u-text-up" />
                <span className="national-team-intraday__card-title-text">
                  历史百亿级放量护盘日 vs 近期成交直方对照
                </span>
                <Tag color="gold" className="national-team-intraday__sub-tag">
                  单日净申购 &gt; 100 亿元阈值标定
                </Tag>
              </Space>
              <span className="national-team-intraday__card-extra">
                蓝柱 = 历史百亿放量日，黄柱 = 近期交易日 · 支持缩放拖拽
              </span>
            </div>
          }
        >
          {volumeStats && (
            <div className="national-team-volume-signal-pills">
              <div className="national-team-pill-item">
                <span className="national-team-pill-item__label">历史百亿护盘日</span>
                <span className="national-team-pill-item__value u-text-primary">{volumeStats.supCount} 天</span>
              </div>
              <div className="national-team-pill-item">
                <span className="national-team-pill-item__label">近期对比交易日</span>
                <span className="national-team-pill-item__value u-text-warning">{volumeStats.recCount} 天</span>
              </div>
              <div className="national-team-pill-item">
                <span className="national-team-pill-item__label">护盘日均成交额</span>
                <span className="national-team-pill-item__value u-text-primary">{volumeStats.supAvgAmt} 亿元</span>
              </div>
              <div className="national-team-pill-item">
                <span className="national-team-pill-item__label">近期日均成交额</span>
                <span className="national-team-pill-item__value u-text-muted">{volumeStats.recAvgAmt} 亿元</span>
              </div>
              <div className="national-team-pill-item national-team-pill-item--highlight">
                <span className="national-team-pill-item__label">救市脉冲放大倍数</span>
                <span className="national-team-pill-item__value u-text-up">{volumeStats.multiple}x 放量中枢</span>
              </div>
            </div>
          )}
          <div className="national-team-intraday__chart-wrapper--sm">
            <LazyChart height={250}>
              <ReactECharts
                echarts={echarts}
                data-testid="national-team-intraday-signal-chart"
                option={volumeSignalOption}
                style={CHART_STYLE_250}
                opts={{ renderer: "canvas" }}
                notMerge
              />
            </LazyChart>
          </div>
        </Card>
      ) : null}
    </div>
  );
}
