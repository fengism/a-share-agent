import { useState, useMemo } from "react";
import { ReloadOutlined, BankOutlined, FallOutlined, TeamOutlined, GlobalOutlined } from "@ant-design/icons";
import { Alert, Button, Col, Row, Space, Typography, Tag, Card, Statistic, Segmented } from "antd";
import dayjs from "dayjs";
import { useForceRefreshUsMacroData, useUsMacroData } from "../../api/queryHooks/market";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";

const { Text } = Typography;

const DEFINITIONS = [
  ["gdp", "美国 GDP", [{ key: "VALUE", label: "GDP 增速", unit: "%" }], "growth_market"],
  ["cpi", "美国 CPI", [
    { key: "CPI_YOY", label: "同比", unit: "%" },
    { key: "CPI_MOM", label: "环比", unit: "%" },
    { key: "CORE_CPI_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_CPI_MOM", label: "核心环比", unit: "%" },
  ], "inflation_policy"],
  ["ppi", "美国 PPI", [
    { key: "PPI_YOY", label: "同比", unit: "%" },
    { key: "PPI_MOM", label: "环比", unit: "%" },
    { key: "CORE_PPI_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_PPI_MOM", label: "核心环比", unit: "%" },
  ], "inflation_policy"],
  ["pce", "美国 PCE", [
    { key: "PCE_YOY", label: "同比", unit: "%" },
    { key: "PCE_MOM", label: "环比", unit: "%" },
    { key: "CORE_PCE_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_PCE_MOM", label: "核心环比", unit: "%" },
  ], "inflation_policy"],
  ["labor", "美国就业", [
    { key: "UNEMPLOYMENT", label: "失业率", unit: "%" },
    { key: "NON_FARM", label: "新增非农", unit: "万人" },
    { key: "INITIAL_JOBLESS", label: "初请失业金", unit: "万人" },
  ], "labor_consumption"],
  ["employment_details", "美国就业细项", [
    { key: "CIVILIAN_LABOR_PARTICIPATION", label: "劳动参与率", unit: "%" },
    { key: "AVG_HOURLY_EARNINGS_MOM", label: "平均时薪环比", unit: "%", secondaryAxis: true },
  ], "labor_consumption"],
  ["consumer_confidence", "美国消费者信心", [{ key: "VALUE", label: "信心指数" }], "labor_consumption"],
  ["credit_spread", "美国信用利差", [{ key: "VALUE", label: "高收益利差", unit: "%" }], "growth_market"],
  ["pmi", "美国 PMI", [
    { key: "MANUFACTURING_PMI", label: "ISM 制造业" },
    { key: "SERVICES_PMI", label: "服务业" },
  ], "growth_market"],
  ["fed_rate", "美联储利率", [{ key: "VALUE", label: "目标利率", unit: "%" }], "inflation_policy"],
  ["retail_sales", "美国零售销售", [{ key: "VALUE", label: "月率", unit: "%" }], "labor_consumption"],
  ["trade_balance", "美国贸易差额", [{ key: "VALUE", label: "贸易差额", unit: "亿美元" }], "growth_market"],
] as const;

const INDICATOR_LABELS: Record<string, string> = Object.fromEntries(
  DEFINITIONS.map(([key, title]) => [key, title]),
);

type UsMacroCategory = "all" | "inflation_policy" | "labor_consumption" | "growth_market";

function formatSnapshotTime(value?: string | null) {
  if (!value) return "暂无快照更新时间";
  const parsed = dayjs(value);
  return parsed.isValid() ? `快照更新于 ${parsed.format("YYYY-MM-DD HH:mm")}` : "暂无快照更新时间";
}

export default function UsMacroTab() {
  const c = useColors();
  const [selectedCategory, setSelectedCategory] = useState<UsMacroCategory>("all");
  const { data, isLoading, error } = useUsMacroData();
  const forceRefresh = useForceRefreshUsMacroData();

  const failedIndicatorNames = Object.keys(data?.failed_indicators ?? {})
    .map((key) => INDICATOR_LABELS[key] ?? key);

  // 提取核心先导指标
  const fedRateVal = data?.indicators?.fed_rate?.latest?.VALUE != null
    ? Number(data.indicators.fed_rate.latest.VALUE)
    : null;
  const coreCpiVal = data?.indicators?.cpi?.latest?.CORE_CPI_YOY != null
    ? Number(data.indicators.cpi.latest.CORE_CPI_YOY)
    : (data?.indicators?.cpi?.latest?.CPI_YOY != null ? Number(data.indicators.cpi.latest.CPI_YOY) : null);
  const unrateVal = data?.indicators?.labor?.latest?.UNEMPLOYMENT != null
    ? Number(data.indicators.labor.latest.UNEMPLOYMENT)
    : null;
  const ismPmiVal = data?.indicators?.pmi?.latest?.MANUFACTURING_PMI != null
    ? Number(data.indicators.pmi.latest.MANUFACTURING_PMI)
    : null;

  // 美国宏观周期定调
  const macroCompass = useMemo(() => {
    let tag = "高利率限制区间 · 经济软着陆博弈";
    let tagColor = "blue";
    if (unrateVal != null && unrateVal >= 4.3) {
      tag = "劳动力市场降温 · 宽松降息预期升温";
      tagColor = "green";
    } else if (coreCpiVal != null && coreCpiVal > 3.5) {
      tag = "核心通胀具备粘性 · 维持高利率更久 (Higher for Longer)";
      tagColor = "orange";
    } else if (ismPmiVal != null && ismPmiVal < 48) {
      tag = "制造业收缩承压 · 关注实体外需收缩风险";
      tagColor = "volcano";
    }
    return { tag, tagColor };
  }, [unrateVal, coreCpiVal, ismPmiVal]);

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => forceRefresh.mutate()}
      isEmpty={!data}
      emptyText="暂无美国宏观数据"
      errorTitle="美国宏观数据加载失败"
      minHeight={280}
    >
      <Space className="macro-page__alerts" orientation="vertical" size={12} style={{ width: "100%" }}>
        <div className="macro-page__snapshot-status">
          <Text type="secondary">{formatSnapshotTime(data?.updated_at)}</Text>
          <Button
            aria-label="刷新美国数据"
            icon={<ReloadOutlined />}
            loading={forceRefresh.isPending}
            onClick={() => forceRefresh.mutate()}
          >
            刷新美国数据
          </Button>
        </div>

        {data?.refreshing ? <Alert type="info" showIcon title="正在后台刷新美国宏观数据，当前展示最近成功快照" /> : null}

        {failedIndicatorNames.length > 0 ? (
          <Alert
            type="warning"
            showIcon
            title={`部分指标刷新失败：${failedIndicatorNames.join("、")}`}
            action={(
              <Button
                size="small"
                loading={forceRefresh.isPending}
                onClick={() => forceRefresh.mutate()}
              >
                重新刷新
              </Button>
            )}
          />
        ) : null}

        {data && !data.indicators?.pce?.latest ? (
          <Alert
            type="info"
            showIcon
            title="PCE 暂无数据"
            description="PCE、就业细项、消费者信心与信用利差仅由 FRED 提供，请检查管理员 FRED API Key 配置或稍后重试。"
          />
        ) : null}

        {/* 美国宏观周期研判横幅 */}
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span><GlobalOutlined /> 美国宏观经济周期与美联储利率路径研判</span>
            <Tag color={macroCompass.tagColor}>{macroCompass.tag}</Tag>
          </div>
          <div className="macro-insight-banner__body">
            美联储基准利率 <strong>{fedRateVal != null ? `${fedRateVal.toFixed(2)}%` : "-"}</strong>，
            核心通胀（CPI/PCE）约为 <strong>{coreCpiVal != null ? `${coreCpiVal.toFixed(1)}%` : "-"}</strong>，
            失业率 <strong>{unrateVal != null ? `${unrateVal.toFixed(1)}%` : "-"}</strong>，
            ISM 制造业 PMI <strong>{ismPmiVal != null ? ismPmiVal.toFixed(1) : "-"}</strong>。
            美国宏观作为全球资产折现率与外资流动风向标，若利率步入降息周期，全球流动性将边际宽松，对新兴市场（A 股核心资产及高成长板块）估值折现压制将显著缓释。
          </div>
        </div>

        {/* 4 大核心风向标微卡片 */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 12, marginBottom: 4 }}>
          <Card size="small" className="macro-kpi-card" variant="borderless">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: c.textSecondary }}>联邦基金目标利率</span>
              <Tag color="purple" icon={<BankOutlined />}>全球折现率锚</Tag>
            </div>
            <Statistic
              value={fedRateVal != null ? `${fedRateVal.toFixed(2)}%` : "-"}
              styles={{ content: { fontSize: 20, fontWeight: 700, color: "#722ed1", marginTop: 4 } }}
            />
            <div className="macro-kpi-subtext">美联储官方货币政策姿态</div>
          </Card>

          <Card size="small" className="macro-kpi-card" variant="borderless">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: c.textSecondary }}>核心 CPI / PCE 同比</span>
              <Tag color="blue" icon={<FallOutlined />}>通胀目标 2%</Tag>
            </div>
            <Statistic
              value={coreCpiVal != null ? `${coreCpiVal.toFixed(1)}%` : "-"}
              styles={{ content: { fontSize: 20, fontWeight: 700, color: (coreCpiVal ?? 0) <= 2.8 ? c.up : c.warning, marginTop: 4 } }}
            />
            <div className="macro-kpi-subtext">通胀粘性与二次反弹观察</div>
          </Card>

          <Card size="small" className="macro-kpi-card" variant="borderless">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: c.textSecondary }}>官方失业率</span>
              <Tag color="cyan" icon={<TeamOutlined />}>劳动力市场</Tag>
            </div>
            <Statistic
              value={unrateVal != null ? `${unrateVal.toFixed(1)}%` : "-"}
              styles={{ content: { fontSize: 20, fontWeight: 700, color: (unrateVal ?? 0) >= 4.3 ? c.warning : c.textPrimary, marginTop: 4 } }}
            />
            <div className="macro-kpi-subtext">萨姆法则衰退预警线</div>
          </Card>

          <Card size="small" className="macro-kpi-card" variant="borderless">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: c.textSecondary }}>ISM 制造业 PMI</span>
              <Tag color={(ismPmiVal ?? 0) >= 50 ? "green" : "volcano"}>荣枯线 50</Tag>
            </div>
            <Statistic
              value={ismPmiVal != null ? ismPmiVal.toFixed(1) : "-"}
              styles={{ content: { fontSize: 20, fontWeight: 700, color: (ismPmiVal ?? 0) >= 50 ? c.up : c.down, marginTop: 4 } }}
            />
            <div className="macro-kpi-subtext">制造业景气与补库周期</div>
          </Card>
        </div>

        {/* 指标分类过滤工具栏 */}
        <div className="macro-category-toolbar" style={{ marginTop: 4 }}>
          <Segmented
            options={[
              { label: "全部指标 (12)", value: "all" },
              { label: "🎯 通胀与货币政策", value: "inflation_policy" },
              { label: "💼 就业与内需消费", value: "labor_consumption" },
              { label: "🏭 实体景气与金融", value: "growth_market" },
            ]}
            value={selectedCategory}
            onChange={(val) => setSelectedCategory(val as UsMacroCategory)}
            size="middle"
          />
        </div>

        <Row className="macro-card-grid" gutter={[16, 16]}>
          {DEFINITIONS.map(([key, title, fields, group]) => {
            const indicator = data?.indicators?.[key];
            const isVisible = selectedCategory === "all" || selectedCategory === group;
            return (
              <Col
                xs={24}
                md={12}
                key={key}
                style={{ display: isVisible ? "flex" : "none" }}
              >
                <MacroIndicatorCard
                  title={title}
                  latest={indicator?.latest ?? null}
                  trend={indicator?.trend ?? []}
                  metadata={indicator}
                  fields={[...fields]}
                />
              </Col>
            );
          })}
        </Row>
      </Space>
    </SectionDataState>
  );
}
