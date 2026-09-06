import { memo } from "react";
import { Row, Col, Card, Statistic, Tag, Typography } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors, useStyles } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const { Text } = Typography;

const CPI_FIELDS = (c: ThemeColors) => [
  { key: "NATIONAL_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "NATIONAL_SEQUENTIAL", label: "环比", color: c.accent, unit: "%" },
];

const PPI_FIELDS = (c: ThemeColors) => [
  { key: "BASE_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "BASE_ACCUMULATE", label: "累计", color: c.primary, unit: "%" },
];

const GDP_FIELDS = (c: ThemeColors) => [
  { key: "GDP_VALUE", label: "当季值", color: c.primary, precision: 1 },
  { key: "GDP_SAME", label: "同比增长", color: c.up, unit: "%" },
];

const PMI_FIELDS = (c: ThemeColors) => [
  { key: "MAKE_INDEX", label: "制造业 PMI", color: c.primary, precision: 1 },
  { key: "NMAKE_INDEX", label: "非制造业 PMI", color: c.accent, precision: 1 },
];

const MONEY_SUPPLY_FIELDS = (c: ThemeColors) => [
  { key: "BASIC_CURRENCY", label: "M2", color: c.primary, precision: 2, valueDivisor: 10_000 },
  { key: "CURRENCY", label: "M1", color: c.accent, precision: 2, valueDivisor: 10_000 },
];

const LPR_FIELDS = (c: ThemeColors) => [
  { key: "LPR1Y", label: "1年期", color: c.primary, unit: "%" },
  { key: "LPR5Y", label: "5年期", color: c.accent, unit: "%" },
];

export default memo(function DomesticMacroOverview() {
  const c = useColors();
  const { cardStyle } = useStyles();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const gdp = data?.growth?.gdp;
  const cpi = data?.prices?.cpi;
  const ppi = data?.prices?.ppi;
  const pmi = data?.sentiment?.pmi;
  const moneySupply = data?.monetary?.money_supply;
  const lpr = data?.rates?.lpr;
  const exportsImports = data?.trade?.exports_imports;

  // Key metrics derivation
  const gdpYoY = gdp?.latest?.GDP_SAME != null ? Number(gdp.latest.GDP_SAME) : null;
  const cpiYoY = cpi?.latest?.NATIONAL_SAME != null ? Number(cpi.latest.NATIONAL_SAME) : null;
  const ppiYoY = ppi?.latest?.BASE_SAME != null ? Number(ppi.latest.BASE_SAME) : null;
  const mfgPmi = pmi?.latest?.MAKE_INDEX != null ? Number(pmi.latest.MAKE_INDEX) : null;
  const m2Val = moneySupply?.latest?.BASIC_CURRENCY != null ? (Number(moneySupply.latest.BASIC_CURRENCY) / 10_000).toFixed(1) : null;
  const lpr1y = lpr?.latest?.LPR1Y != null ? Number(lpr.latest.LPR1Y).toFixed(2) : null;
  const lpr5y = lpr?.latest?.LPR5Y != null ? Number(lpr.latest.LPR5Y).toFixed(2) : null;
  const expYoY = exportsImports?.latest?.EXPORTS_SAME != null ? Number(exportsImports.latest.EXPORTS_SAME) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无宏观经济总览数据"
      errorTitle="宏观总览加载失败"
      minHeight={320}
    >
      {/* Top 6 Macro Weather Vane KPIs */}
      <div className="macro-overview-kpi-bar" style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: "var(--c-font-md)", fontWeight: "var(--c-weight-bold)", color: c.textPrimary }}>
              🇨🇳 国内宏观核心风向标（宏观晴雨表）
            </span>
            <Tag color="blue">实时聚合</Tag>
          </div>
          <Text style={{ fontSize: "var(--c-font-xs)", color: c.textMuted }}>
            数据来源：国家统计局 / 中国人民银行 / 海关总署
          </Text>
        </div>

        <Row gutter={[12, 12]}>
          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="GDP 季度同比"
                value={gdpYoY ?? "-"}
                precision={1}
                suffix={gdpYoY != null ? "%" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: gdpYoY != null && gdpYoY >= 5 ? c.up : c.textPrimary,
                  },
                }}
              />
              <Text style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
                经济总产出 · 当季
              </Text>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="CPI 居民消费价格"
                value={cpiYoY ?? "-"}
                precision={2}
                suffix={cpiYoY != null ? "%" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: cpiYoY != null && cpiYoY > 0 ? c.up : c.textPrimary,
                  },
                }}
              />
              <Text style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
                PPI 同比 {ppiYoY != null ? `${ppiYoY > 0 ? "+" : ""}${ppiYoY.toFixed(1)}%` : "-"}
              </Text>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="制造业 PMI"
                value={mfgPmi ?? "-"}
                precision={1}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: mfgPmi != null && mfgPmi >= 50 ? c.up : c.down,
                  },
                }}
              />
              <Text style={{ color: mfgPmi != null && mfgPmi >= 50 ? c.up : c.down, fontSize: "var(--c-font-xs)", fontWeight: 600 }}>
                {mfgPmi != null && mfgPmi >= 50 ? "● 处于扩张区间" : "○ 处于收缩区间"}
              </Text>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="M2 货币总量"
                value={m2Val ?? "-"}
                suffix={m2Val ? "万亿" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: c.primary,
                  },
                }}
              />
              <Text style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
                流动性总池深度
              </Text>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="1Y / 5Y LPR 利率"
                value={lpr1y != null ? Number(lpr1y) : "-"}
                precision={lpr1y != null ? 2 : undefined}
                suffix={lpr1y != null ? "%" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: c.textPrimary,
                  },
                }}
              />
              <Text style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
                5年期以上 {lpr5y ? `${lpr5y}%` : "-"}
              </Text>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive">
              <Statistic
                title="出口同比增速"
                value={expYoY ?? "-"}
                precision={1}
                suffix={expYoY != null ? "%" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: expYoY != null && expYoY >= 0 ? c.up : c.down,
                  },
                }}
              />
              <Text style={{ color: c.textMuted, fontSize: "var(--c-font-xs)" }}>
                外需与出口动能
              </Text>
            </Card>
          </Col>
        </Row>
      </div>

      {/* Structured Overview Matrix */}
      <div className="macro-section-divider"><span>🏛️ 核心宏观支柱走势</span></div>
      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="GDP 国内生产总值（季度）"
            latest={gdp?.latest ?? null}
            trend={gdp?.trend ?? []}
            metadata={gdp}
            fields={GDP_FIELDS(c)}
          />
        </Col>

        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="PMI 采购经理人指数"
            latest={pmi?.latest ?? null}
            trend={pmi?.trend ?? []}
            metadata={pmi}
            fields={PMI_FIELDS(c)}
          />
        </Col>

        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="CPI 居民消费价格指数"
            latest={cpi?.latest ?? null}
            trend={cpi?.trend ?? []}
            metadata={cpi}
            fields={CPI_FIELDS(c)}
          />
        </Col>

        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="PPI 工业生产者出厂价格指数"
            latest={ppi?.latest ?? null}
            trend={ppi?.trend ?? []}
            metadata={ppi}
            fields={PPI_FIELDS(c)}
          />
        </Col>

        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="货币供应量 M0/M1/M2（万亿元）"
            latest={moneySupply?.latest ?? null}
            trend={moneySupply?.trend ?? []}
            metadata={moneySupply}
            fields={MONEY_SUPPLY_FIELDS(c)}
          />
        </Col>

        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="LPR 贷款市场报价利率"
            latest={lpr?.latest ?? null}
            trend={lpr?.trend ?? []}
            metadata={lpr}
            fields={LPR_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
});
