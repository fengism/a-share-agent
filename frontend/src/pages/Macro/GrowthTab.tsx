import { useState, useMemo } from "react";
import { Row, Col, Segmented, Card, Statistic, Tag } from "antd";
import {
  BarChartOutlined,
  ShoppingOutlined,
  FundProjectionScreenOutlined,
  TeamOutlined,
} from "@ant-design/icons";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const GDP_FIELDS = (c: ThemeColors) => [
  { key: "GDP_VALUE", label: "当季值", color: c.primary, precision: 1 },
  { key: "GDP_SAME", label: "同比增长", color: c.up, unit: "%" },
];

const INDUSTRIAL_PRODUCTION_FIELDS = (c: ThemeColors) => [
  { key: "VALUE_ADDED_YOY", label: "当月同比", color: c.primary, unit: "%" },
  { key: "VALUE_ADDED_ACCUMULATE_YOY", label: "累计同比", color: c.up, unit: "%" },
];

const RETAIL_SALES_FIELDS = (c: ThemeColors) => [
  { key: "RETAIL_VALUE", label: "当月值", color: c.primary, unit: "万亿元", precision: 2, valueDivisor: 10_000 },
  { key: "RETAIL_YOY", label: "当月同比", color: c.up, unit: "%" },
  { key: "RETAIL_ACCUMULATE", label: "累计值", color: c.accent, unit: "万亿元", precision: 2, valueDivisor: 10_000 },
  { key: "RETAIL_ACCUMULATE_YOY", label: "累计同比", color: c.warning, unit: "%" },
];

const FIXED_ASSET_INVESTMENT_FIELDS = (c: ThemeColors) => [
  { key: "INVESTMENT_ACCUMULATE_YOY", label: "累计同比", color: c.primary, unit: "%" },
];

const REAL_ESTATE_FIELDS = (c: ThemeColors) => [
  { key: "DEVELOPMENT_INVESTMENT", label: "开发投资累计值", color: c.primary, unit: "万亿元", precision: 2, valueDivisor: 10_000 },
  { key: "DEVELOPMENT_INVESTMENT_YOY", label: "开发投资累计同比", color: c.up, unit: "%" },
  { key: "SALES_AREA", label: "商品房销售面积", color: c.accent, unit: "亿平方米", precision: 2, valueDivisor: 10_000 },
  { key: "SALES_AREA_YOY", label: "销售面积累计同比", color: c.warning, unit: "%" },
  { key: "SALES_VALUE", label: "商品房销售额", color: c.textSecondary, unit: "万亿元", precision: 2, valueDivisor: 10_000 },
  { key: "SALES_VALUE_YOY", label: "销售额累计同比", color: c.down, unit: "%" },
];

const EMPLOYMENT_FIELDS = (c: ThemeColors) => [
  { key: "URBAN_SURVEYED_UNEMPLOYMENT", label: "全国城镇调查失业率", color: c.primary, unit: "%" },
  { key: "CITY31_SURVEYED_UNEMPLOYMENT", label: "31个大城市调查失业率", color: c.warning, unit: "%" },
];

type GrowthCategory = "all" | "output" | "demand" | "focus";

export default function GrowthTab() {
  const c = useColors();
  const [category, setCategory] = useState<GrowthCategory>("all");
  const { data, isLoading, error, refetch } = useMacroAllData();

  const gdp = data?.growth?.gdp;
  const industrialProduction = data?.growth?.industrial_production;
  const retailSales = data?.growth?.retail_sales;
  const fixedAssetInvestment = data?.growth?.fixed_asset_investment;
  const realEstate = data?.growth?.real_estate;
  const employment = data?.growth?.employment;

  const gdpYoY = gdp?.latest?.GDP_SAME != null ? Number(gdp.latest.GDP_SAME) : null;
  const indYoY = industrialProduction?.latest?.VALUE_ADDED_YOY != null ? Number(industrialProduction.latest.VALUE_ADDED_YOY) : null;
  const indAccYoY = industrialProduction?.latest?.VALUE_ADDED_ACCUMULATE_YOY != null ? Number(industrialProduction.latest.VALUE_ADDED_ACCUMULATE_YOY) : null;
  const retailYoY = retailSales?.latest?.RETAIL_YOY != null ? Number(retailSales.latest.RETAIL_YOY) : null;
  const retailAccYoY = retailSales?.latest?.RETAIL_ACCUMULATE_YOY != null ? Number(retailSales.latest.RETAIL_ACCUMULATE_YOY) : null;
  const faiYoY = fixedAssetInvestment?.latest?.INVESTMENT_ACCUMULATE_YOY != null ? Number(fixedAssetInvestment.latest.INVESTMENT_ACCUMULATE_YOY) : null;
  const unemployment = employment?.latest?.URBAN_SURVEYED_UNEMPLOYMENT != null ? Number(employment.latest.URBAN_SURVEYED_UNEMPLOYMENT) : null;
  const reInvestYoY = realEstate?.latest?.DEVELOPMENT_INVESTMENT_YOY != null ? Number(realEstate.latest.DEVELOPMENT_INVESTMENT_YOY) : null;

  // 研判实体经济供需基调
  const growthAssessment = useMemo(() => {
    let tag = "实体修复与结构调整期";
    let tagColor = "blue";
    if (indYoY != null && indYoY >= 5.5 && retailYoY != null && retailYoY >= 4.5) {
      tag = "供需协同加速扩张";
      tagColor = "green";
    } else if (indYoY != null && indYoY >= 5.0) {
      tag = "生产供给强于内需，先进制造韧性突出";
      tagColor = "cyan";
    } else if (reInvestYoY != null && reInvestYoY < -5.0) {
      tag = "地产链仍处筑底期，政策加力托底需求";
      tagColor = "orange";
    }
    return { tag, tagColor };
  }, [indYoY, retailYoY, reInvestYoY]);

  const showOutput = category === "all" || category === "output";
  const showDemand = category === "all" || category === "demand";
  const showFocus = category === "all" || category === "focus";

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无经济增长数据"
      errorTitle="经济增长数据加载失败"
      minHeight={280}
    >
      {/* 实体增长宏观研判横幅 */}
      <div className="macro-insight-banner">
        <div className="macro-insight-banner__title">
          <span>💡 宏观增长动能与供需基本盘研判</span>
          <Tag color={growthAssessment.tagColor}>{growthAssessment.tag}</Tag>
        </div>
        <div className="macro-insight-banner__body">
          {gdpYoY != null ? <>最新 GDP 同比增速 <strong>{gdpYoY.toFixed(1)}%</strong>；</> : null}
          规上工业增加值当月同比 <strong>{indYoY != null ? `${indYoY > 0 ? "+" : ""}${indYoY.toFixed(1)}%` : "-"}</strong>
          {indAccYoY != null ? <>（累计同比 <strong>{indAccYoY > 0 ? `+${indAccYoY.toFixed(1)}` : indAccYoY.toFixed(1)}%</strong>）</> : null}
          ，社零当月同比 <strong>{retailYoY != null ? `${retailYoY > 0 ? "+" : ""}${retailYoY.toFixed(1)}%` : "-"}</strong>
          ，固定资产投资累计同比 <strong>{faiYoY != null ? `${faiYoY > 0 ? "+" : ""}${faiYoY.toFixed(1)}%` : "-"}</strong>。
          全国城镇调查失业率 <strong>{unemployment != null ? `${unemployment.toFixed(1)}%` : "-"}</strong>。
          当前实体经济呈现“供给生产韧性强于终端消费、制造业与出海链支撑大盘、地产筑底拖累减弱”的结构特征。
        </div>
      </div>

      {/* 4 大核心增长动能风向标速览 */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(210px, 1fr))", gap: 14, marginBottom: 16 }}>
        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>规上工业增加值 (月同比)</span>
            <Tag color="blue" icon={<BarChartOutlined />}>供给底座</Tag>
          </div>
          <Statistic
            value={indYoY != null ? `${indYoY > 0 ? "+" : ""}${indYoY.toFixed(1)}%` : "-"}
            styles={{ content: { fontSize: 20, fontWeight: 700, color: (indYoY ?? 0) >= 5 ? c.up : c.primary, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            累计同比: {indAccYoY != null ? `${indAccYoY > 0 ? "+" : ""}${indAccYoY.toFixed(1)}%` : "-"}
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>社会消费品零售 (月同比)</span>
            <Tag color="cyan" icon={<ShoppingOutlined />}>内需晴雨表</Tag>
          </div>
          <Statistic
            value={retailYoY != null ? `${retailYoY > 0 ? "+" : ""}${retailYoY.toFixed(1)}%` : "-"}
            styles={{ content: { fontSize: 20, fontWeight: 700, color: (retailYoY ?? 0) >= 4 ? c.up : c.accent, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            累计同比: {retailAccYoY != null ? `${retailAccYoY > 0 ? "+" : ""}${retailAccYoY.toFixed(1)}%` : "-"}
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>固定资产投资 (累计同比)</span>
            <Tag color="purple" icon={<FundProjectionScreenOutlined />}>投资动能</Tag>
          </div>
          <Statistic
            value={faiYoY != null ? `${faiYoY > 0 ? "+" : ""}${faiYoY.toFixed(1)}%` : "-"}
            styles={{ content: { fontSize: 20, fontWeight: 700, color: (faiYoY ?? 0) >= 3 ? c.up : c.textPrimary, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            制造业与基建双轮托底
          </div>
        </Card>

        <Card size="small" className="macro-kpi-card" variant="borderless">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={{ fontSize: 12, color: c.textSecondary }}>全国城镇失业率</span>
            <Tag color="gold" icon={<TeamOutlined />}>民生底线</Tag>
          </div>
          <Statistic
            value={unemployment != null ? `${unemployment.toFixed(1)}%` : "-"}
            styles={{ content: { fontSize: 20, fontWeight: 700, color: (unemployment ?? 5.5) <= 5.2 ? c.up : c.warning, marginTop: 4 } }}
          />
          <div className="macro-kpi-subtext">
            {(unemployment ?? 6) <= 5.2 ? "处于充分就业平稳区间" : "民生稳就业仍需政策呵护"}
          </div>
        </Card>
      </div>

      <div className="macro-category-toolbar">
        <Segmented
          options={[
            { label: "全部增长指标", value: "all" },
            { label: "📊 产出与总量", value: "output" },
            { label: "🛍️ 消费与投资", value: "demand" },
            { label: "🏢 地产与就业", value: "focus" },
          ]}
          value={category}
          onChange={(val) => setCategory(val as GrowthCategory)}
          size="middle"
        />
      </div>

      <Row className="macro-card-grid" gutter={[16, 16]}>
        {/* Output section */}
        {category === "all" && (
          <Col xs={24}>
            <div className="macro-section-divider"><span>📊 核心产出与大盘总量</span></div>
          </Col>
        )}
        <Col xs={24} lg={12} style={{ display: showOutput ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="GDP 国内生产总值（季度）"
            latest={gdp?.latest ?? null}
            trend={gdp?.trend ?? []}
            metadata={gdp}
            fields={GDP_FIELDS(c)}
          />
        </Col>
        <Col xs={24} lg={12} style={{ display: showOutput ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="规模以上工业增加值"
            latest={industrialProduction?.latest ?? null}
            trend={industrialProduction?.trend ?? []}
            metadata={industrialProduction}
            fields={INDUSTRIAL_PRODUCTION_FIELDS(c)}
          />
        </Col>

        {/* Demand section */}
        {category === "all" && (
          <Col xs={24}>
            <div className="macro-section-divider"><span>🛍️ 需求端：消费与投资</span></div>
          </Col>
        )}
        <Col xs={24} lg={12} style={{ display: showDemand ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="社会消费品零售总额"
            latest={retailSales?.latest ?? null}
            trend={retailSales?.trend ?? []}
            metadata={retailSales}
            fields={RETAIL_SALES_FIELDS(c)}
          />
        </Col>
        <Col xs={24} lg={12} style={{ display: showDemand ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="固定资产投资"
            latest={fixedAssetInvestment?.latest ?? null}
            trend={fixedAssetInvestment?.trend ?? []}
            metadata={fixedAssetInvestment}
            fields={FIXED_ASSET_INVESTMENT_FIELDS(c)}
          />
        </Col>

        {/* Focus & livelihood section */}
        {category === "all" && (
          <Col xs={24}>
            <div className="macro-section-divider"><span>🏢 重点关注：房地产与城镇民生</span></div>
          </Col>
        )}
        <Col xs={24} lg={12} style={{ display: showFocus ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="城镇调查失业率"
            latest={employment?.latest ?? null}
            trend={employment?.trend ?? []}
            metadata={employment}
            fields={EMPLOYMENT_FIELDS(c)}
          />
        </Col>
        <Col xs={24} lg={12} style={{ display: showFocus ? "flex" : "none" }}>
          <MacroIndicatorCard
            title="房地产开发与销售"
            latest={realEstate?.latest ?? null}
            trend={realEstate?.trend ?? []}
            metadata={realEstate}
            fields={REAL_ESTATE_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
