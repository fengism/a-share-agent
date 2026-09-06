import { useMemo, useState } from "react";
import { Row, Col, Card, Statistic, Tag, Table, Segmented, Radio, Input } from "antd";
import { ArrowUpOutlined, ArrowDownOutlined, GlobalOutlined, LineChartOutlined, BarChartOutlined, SearchOutlined } from "@ant-design/icons";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useGlobalMacroRates } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import type { TreasuryYieldPoint } from "../../types/stock";

type TimeRange = "3m" | "6m" | "1y" | "all";
type ChartMode = "10y" | "2y" | "term_spread" | "all_series";

export default function GlobalRatesTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useGlobalMacroRates();
  const [timeRange, setTimeRange] = useState<TimeRange>("1y");
  const [chartMode, setChartMode] = useState<ChartMode>("10y");
  const [tableSearch, setTableSearch] = useState("");

  const fx = data?.dollar_and_fx;
  const bond = data?.treasury_yields_and_spreads;
  const curve = data?.treasury_curve;
  const policy = data?.central_bank_policy_rates;
  const imp = data?.market_implications;

  // Filter historical curve data by selected time range
  const filteredHistory = useMemo(() => {
    const raw = curve?.history ?? [];
    if (raw.length === 0) return [];
    
    // Sort chronological (oldest to newest for charting)
    const sorted = [...raw].reverse();
    if (timeRange === "all") return sorted;
    
    const countMap: Record<TimeRange, number> = {
      "3m": 65,
      "6m": 130,
      "1y": 250,
      "all": sorted.length,
    };
    const limit = countMap[timeRange] || sorted.length;
    return sorted.slice(-limit);
  }, [curve?.history, timeRange]);

  // ECharts Multi-line Option for Historical Yield Comparison
  const historyChartOption = useMemo(() => {
    if (filteredHistory.length === 0) return null;

    const dates = filteredHistory.map((d) => d.date);
    const cn10y = filteredHistory.map((d) => d.cn_10y);
    const us10y = filteredHistory.map((d) => d.us_10y);
    const cn2y = filteredHistory.map((d) => d.cn_2y);
    const us2y = filteredHistory.map((d) => d.us_2y);
    const spread10y = filteredHistory.map((d) => d.spread_10y);
    const cn10y2y = filteredHistory.map((d) => d.cn_10y_2y);
    const us10y2y = filteredHistory.map((d) => d.us_10y_2y);

    const series = [];
    if (chartMode === "10y") {
      series.push(
        {
          name: "中国 10 年期国债收益率",
          type: "line",
          data: cn10y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#1677ff" },
          lineStyle: { width: 2.2 },
        },
        {
          name: "美国 10 年期国债收益率",
          type: "line",
          data: us10y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#fa541c" },
          lineStyle: { width: 2.2 },
        },
        {
          name: "中美 10Y 国债利差 (中-美)",
          type: "line",
          data: spread10y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#722ed1" },
          lineStyle: { width: 1.8, type: "dashed" },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(114, 46, 209, 0.15)" },
                { offset: 1, color: "rgba(114, 46, 209, 0.0)" },
              ],
            },
          },
        },
      );
    } else if (chartMode === "2y") {
      series.push(
        {
          name: "中国 2 年期国债收益率",
          type: "line",
          data: cn2y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#13c2c2" },
          lineStyle: { width: 2 },
        },
        {
          name: "美国 2 年期国债收益率",
          type: "line",
          data: us2y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#fa8c16" },
          lineStyle: { width: 2 },
        },
        {
          name: "中美 2Y 国债利差 (中-美)",
          type: "line",
          data: filteredHistory.map((d) => d.spread_2y),
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#eb2f96" },
          lineStyle: { width: 1.8, type: "dashed" },
        },
      );
    } else if (chartMode === "term_spread") {
      series.push(
        {
          name: "中国 10Y-2Y 期限利差",
          type: "line",
          data: cn10y2y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#1677ff" },
          lineStyle: { width: 2 },
        },
        {
          name: "美国 10Y-2Y 期限利差",
          type: "line",
          data: us10y2y,
          smooth: true,
          showSymbol: false,
          itemStyle: { color: "#fa541c" },
          lineStyle: { width: 2 },
        },
      );
    } else {
      // all_series
      series.push(
        { name: "中国 10Y", type: "line", data: cn10y, smooth: true, showSymbol: false, itemStyle: { color: "#1677ff" }, lineStyle: { width: 2 } },
        { name: "中国 2Y", type: "line", data: cn2y, smooth: true, showSymbol: false, itemStyle: { color: "#69b1ff" }, lineStyle: { width: 1.5 } },
        { name: "美国 10Y", type: "line", data: us10y, smooth: true, showSymbol: false, itemStyle: { color: "#fa541c" }, lineStyle: { width: 2 } },
        { name: "美国 2Y", type: "line", data: us2y, smooth: true, showSymbol: false, itemStyle: { color: "#ff85c0" }, lineStyle: { width: 1.5 } },
        { name: "中美 10Y 利差", type: "line", data: spread10y, smooth: true, showSymbol: false, itemStyle: { color: "#722ed1" }, lineStyle: { width: 1.5, type: "dashed" } },
      );
    }

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        backgroundColor: "rgba(255, 255, 255, 0.96)",
        borderColor: "#e2e8f0",
        textStyle: { color: "#1e293b", fontSize: 12 },
        extraCssText: "box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12); border-radius: 6px;",
        valueFormatter: (val: unknown) => (val != null && typeof val === "number" ? `${val.toFixed(3)}%` : "-"),
      },
      legend: {
        top: 0,
        textStyle: { color: c.textSecondary, fontSize: 12 },
      },
      grid: {
        left: "3%",
        right: "3%",
        bottom: "8%",
        top: "14%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: dates,
        axisLine: { lineStyle: { color: c.border } },
        axisLabel: { color: c.textSecondary, fontSize: 11 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          color: c.textSecondary,
          formatter: "{value}%",
          fontSize: 11,
        },
        splitLine: {
          lineStyle: { color: c.border, type: "dashed" },
        },
      },
      series,
    };
  }, [filteredHistory, chartMode, c]);

  // ECharts Term Structure Option
  const termStructureChartOption = useMemo(() => {
    const termData = curve?.term_structure ?? [];
    if (termData.length === 0) return null;

    const tenors = termData.map((t) => t.tenor);
    const cnYields = termData.map((t) => t.cn_yield);
    const usYields = termData.map((t) => t.us_yield);

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        valueFormatter: (val: unknown) => (val != null ? `${Number(val).toFixed(3)}%` : "-"),
      },
      legend: {
        top: 0,
        textStyle: { color: c.textSecondary, fontSize: 12 },
      },
      grid: {
        left: "3%",
        right: "4%",
        bottom: "8%",
        top: "16%",
        containLabel: true,
      },
      xAxis: {
        type: "category",
        data: tenors,
        axisLine: { lineStyle: { color: c.border } },
        axisLabel: { color: c.textPrimary, fontWeight: 600 },
      },
      yAxis: {
        type: "value",
        scale: true,
        axisLabel: {
          color: c.textSecondary,
          formatter: "{value}%",
        },
        splitLine: {
          lineStyle: { color: c.border, type: "dashed" },
        },
      },
      series: [
        {
          name: "🇨🇳 中国国债收益率",
          type: "bar",
          barWidth: "30%",
          data: cnYields,
          itemStyle: { color: "#1677ff", borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", fontSize: 11 },
        },
        {
          name: "🇺🇸 美国国债收益率",
          type: "bar",
          barWidth: "30%",
          data: usYields,
          itemStyle: { color: "#fa541c", borderRadius: [4, 4, 0, 0] },
          label: { show: true, position: "top", formatter: "{c}%", fontSize: 11 },
        },
      ],
    };
  }, [curve?.term_structure, c]);

  // Filtered table rows
  const tableData = useMemo(() => {
    const raw = curve?.history ?? [];
    if (!tableSearch.trim()) return raw;
    const query = tableSearch.trim().toLowerCase();
    return raw.filter((row) => row.date.includes(query));
  }, [curve?.history, tableSearch]);

  const tableColumns = [
    {
      title: "日期",
      dataIndex: "date",
      key: "date",
      width: 110,
      render: (text: string) => <strong>{text}</strong>,
    },
    {
      title: "🇨🇳 中债 2Y",
      dataIndex: "cn_2y",
      key: "cn_2y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "🇨🇳 中债 5Y",
      dataIndex: "cn_5y",
      key: "cn_5y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "🇨🇳 中债 10Y",
      dataIndex: "cn_10y",
      key: "cn_10y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? <span style={{ color: "#1677ff", fontWeight: 600 }}>{v.toFixed(3)}%</span> : "-"),
    },
    {
      title: "🇨🇳 中债 30Y",
      dataIndex: "cn_30y",
      key: "cn_30y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "🇺🇸 美债 2Y",
      dataIndex: "us_2y",
      key: "us_2y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "🇺🇸 美债 5Y",
      dataIndex: "us_5y",
      key: "us_5y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "🇺🇸 美债 10Y",
      dataIndex: "us_10y",
      key: "us_10y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? <span style={{ color: "#fa541c", fontWeight: 600 }}>{v.toFixed(3)}%</span> : "-"),
    },
    {
      title: "🇺🇸 美债 30Y",
      dataIndex: "us_30y",
      key: "us_30y",
      align: "right" as const,
      render: (v: number | null) => (v != null ? `${v.toFixed(3)}%` : "-"),
    },
    {
      title: "⚖️ 中美 10Y 利差",
      dataIndex: "spread_10y",
      key: "spread_10y",
      align: "right" as const,
      render: (v: number | null) => (
        v != null ? (
          <Tag color={v < 0 ? "volcano" : "green"}>
            {v > 0 ? "+" : ""}{v.toFixed(3)}%
          </Tag>
        ) : "-"
      ),
    },
    {
      title: "🇺🇸 美债 10Y-2Y 倒挂",
      dataIndex: "us_10y_2y",
      key: "us_10y_2y",
      align: "right" as const,
      render: (v: number | null) => (
        v != null ? (
          <Tag color={v < 0 ? "red" : "blue"}>
            {v.toFixed(3)}%
          </Tag>
        ) : "-"
      ),
    },
  ];

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无全球宏观利率数据"
      errorTitle="全球宏观利率数据加载失败"
      minHeight={320}
    >
      {/* 投研指引横幅 */}
      <div className="macro-insight-banner">
        <div className="macro-insight-banner__title">
          <span><GlobalOutlined /> 全球流动性、资产折现率与中美国债收益率曲线</span>
          {bond?.us_china_10y_spread != null ? (
            <Tag color={bond.us_china_10y_spread < 0 ? "volcano" : "green"}>
              {bond.us_china_spread_status} ({bond.us_china_10y_spread}%)
            </Tag>
          ) : null}
        </div>
        <div className="macro-insight-banner__body">
          {imp?.us_10y_impact} {imp?.us_china_spread_impact}
        </div>
      </div>

      {/* 核心指标看板 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        {/* 美元指数 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" className="macro-stat-card">
            <Statistic
              title="美元指数 (DXY)"
              value={fx?.dxy?.value ?? "-"}
              precision={2}
              valueStyle={{ color: (fx?.dxy?.change ?? 0) >= 0 ? c.up : c.down, fontWeight: 600 }}
              prefix={(fx?.dxy?.change ?? 0) >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
              suffix={<span style={{ fontSize: 13, marginLeft: 4 }}>{fx?.dxy?.change_pct != null ? `${fx.dxy.change_pct > 0 ? "+" : ""}${fx.dxy.change_pct}%` : ""}</span>}
            />
            <div style={{ fontSize: 12, color: c.textSecondary, marginTop: 4 }}>全球风险资产定价基准</div>
          </Card>
        </Col>

        {/* 离岸人民币 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" className="macro-stat-card">
            <Statistic
              title="美元兑离岸人民币 (USD/CNH)"
              value={fx?.usd_cnh?.value ?? "-"}
              precision={4}
              valueStyle={{ color: (fx?.usd_cnh?.change ?? 0) >= 0 ? c.down : c.up, fontWeight: 600 }}
              suffix={<span style={{ fontSize: 13, marginLeft: 4 }}>{fx?.usd_cnh?.change_pct != null ? `${fx.usd_cnh.change_pct > 0 ? "+" : ""}${fx.usd_cnh.change_pct}%` : ""}</span>}
            />
            <div style={{ fontSize: 12, color: c.textSecondary, marginTop: 4 }}>外资进出 A 股风向标</div>
          </Card>
        </Col>

        {/* 美债 10 年期收益率 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" className="macro-stat-card">
            <Statistic
              title="美债 10 年期收益率"
              value={bond?.us_10y_yield ?? "-"}
              precision={2}
              valueStyle={{ color: "#fa541c", fontWeight: 600 }}
              suffix="%"
            />
            <div style={{ fontSize: 12, color: c.textSecondary, marginTop: 4 }}>全球无风险折现率之锚</div>
          </Card>
        </Col>

        {/* 中美 10Y 国债利差 */}
        <Col xs={24} sm={12} md={6}>
          <Card size="small" className="macro-stat-card">
            <Statistic
              title="中美 10Y 利差 (中 - 美)"
              value={bond?.us_china_10y_spread ?? "-"}
              precision={2}
              valueStyle={{ color: (bond?.us_china_10y_spread ?? 0) >= 0 ? c.up : c.down, fontWeight: 600 }}
              suffix="%"
            />
            <div style={{ fontSize: 12, color: c.textSecondary, marginTop: 4 }}>{bond?.us_china_spread_status ?? "-"}</div>
          </Card>
        </Col>
      </Row>

      {/* 中美国债收益率历史走势与利差曲线对比 */}
      <Card
        title={
          <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap", justifyContent: "space-between" }}>
            <span style={{ fontSize: "var(--c-font-base)", fontWeight: 600 }}>
              <LineChartOutlined style={{ color: "#1677ff", marginRight: 6 }} />
              中美国债收益率走势与利差曲线对比（参考东方财富数据中心）
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <Segmented
                size="small"
                value={chartMode}
                onChange={(v) => setChartMode(v as ChartMode)}
                options={[
                  { label: "10年期对比", value: "10y" },
                  { label: "2年期对比", value: "2y" },
                  { label: "期限利差 (10Y-2Y)", value: "term_spread" },
                  { label: "全量曲线", value: "all_series" },
                ]}
              />
              <Radio.Group
                size="small"
                value={timeRange}
                onChange={(e) => setTimeRange(e.target.value)}
                buttonStyle="solid"
              >
                <Radio.Button value="3m">近3月</Radio.Button>
                <Radio.Button value="6m">近6月</Radio.Button>
                <Radio.Button value="1y">近1年</Radio.Button>
                <Radio.Button value="all">全部</Radio.Button>
              </Radio.Group>
            </div>
          </div>
        }
        size="small"
        style={{ marginBottom: 16 }}
      >
        {historyChartOption ? (
          <ReactECharts
            echarts={echarts}
            option={historyChartOption}
            style={{ height: 380, width: "100%" }}
            notMerge
          />
        ) : (
          <div style={{ height: 380, display: "flex", alignItems: "center", justifyContent: "center", color: c.textMuted }}>
            正在加载国债收益率曲线...
          </div>
        )}
      </Card>

      {/* 收益率期限结构 (Term Structure) 与主要央行基准利率 */}
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} lg={12}>
          <Card
            title={
              <span>
                <BarChartOutlined style={{ color: "#722ed1", marginRight: 6 }} />
                中美国债收益率期限结构对比 (2Y · 5Y · 10Y · 30Y)
              </span>
            }
            size="small"
          >
            {termStructureChartOption ? (
              <ReactECharts
                echarts={echarts}
                option={termStructureChartOption}
                style={{ height: 260, width: "100%" }}
                notMerge
              />
            ) : (
              <div style={{ height: 260, display: "flex", alignItems: "center", justifyContent: "center", color: c.textMuted }}>
                期限结构数据加载中...
              </div>
            )}
          </Card>
        </Col>

        <Col xs={24} lg={12}>
          <Card title="全球主要央行政策基准利率与传导" size="small">
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.02)", borderRadius: 6, borderLeft: `3px solid ${c.primary}` }}>
                <div style={{ fontSize: 12, color: c.textSecondary }}>中国人民银行 · 1年期 LPR</div>
                <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>{policy?.china_lpr_1y ?? "3.10%"}</div>
              </div>
              <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.02)", borderRadius: 6, borderLeft: `3px solid ${c.accent}` }}>
                <div style={{ fontSize: 12, color: c.textSecondary }}>中国人民银行 · 5年期以上 LPR (房贷基准)</div>
                <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>{policy?.china_lpr_5y ?? "3.60%"}</div>
              </div>
              <div style={{ padding: "10px 14px", background: "rgba(0,0,0,0.02)", borderRadius: 6, borderLeft: `3px solid #722ed1` }}>
                <div style={{ fontSize: 12, color: c.textSecondary }}>美联储 · 联邦基金目标利率 (Fed Funds Rate)</div>
                <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>{policy?.us_fed_funds_rate ?? "4.25% - 4.50%"}</div>
              </div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* 历史明细数据表格 */}
      <Card
        title="中美国债收益率与利差历史明细"
        size="small"
        extra={
          <Input
            placeholder="搜索日期 (如 2026-08)..."
            prefix={<SearchOutlined style={{ color: c.textMuted }} />}
            size="small"
            value={tableSearch}
            onChange={(e) => setTableSearch(e.target.value)}
            style={{ width: 220 }}
            allowClear
          />
        }
      >
        <Table<TreasuryYieldPoint>
          size="small"
          dataSource={tableData}
          columns={tableColumns}
          rowKey="date"
          pagination={{ pageSize: 12, showSizeChanger: true, pageSizeOptions: ["12", "24", "50"] }}
          scroll={{ x: 1000 }}
        />
      </Card>
    </SectionDataState>
  );
}
