import { useState } from "react";
import { Row, Col, Segmented } from "antd";
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
