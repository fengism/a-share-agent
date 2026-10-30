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
  const nonMfgPmi = pmi?.latest?.NMAKE_INDEX != null ? Number(pmi.latest.NMAKE_INDEX) : null;
  const m2Val = moneySupply?.latest?.BASIC_CURRENCY != null ? (Number(moneySupply.latest.BASIC_CURRENCY) / 10_000).toFixed(1) : null;
  const lpr1y = lpr?.latest?.LPR1Y != null ? Number(lpr.latest.LPR1Y).toFixed(2) : null;
  const lpr5y = lpr?.latest?.LPR5Y != null ? Number(lpr.latest.LPR5Y).toFixed(2) : null;
  const expYoY = exportsImports?.latest?.EXPORTS_SAME != null ? Number(exportsImports.latest.EXPORTS_SAME) : null;

  // 核心衍生指标计算
  const profitScissors = (cpiYoY != null && ppiYoY != null) ? Number((cpiYoY - ppiYoY).toFixed(2)) : null;
  const termSpread = (lpr1y != null && lpr5y != null) ? Number((Number(lpr5y) - Number(lpr1y)).toFixed(2)) : null;

  // 宏观周期推导逻辑
  let cycleName = "政策对冲·筑底整固期";
  let cycleDesc = "宏观政策逆周期调节加力，实体融资成本处于历史低位，流动性水库充沛，支撑 A 股估值底线。";
  let cycleTagColor = "blue";
  let transmissionStance = "流动性支撑估值";

  if (mfgPmi != null) {
    if (mfgPmi >= 50.2 && (gdpYoY == null || gdpYoY >= 5)) {
      cycleName = "景气扩张·动能释放期";
      cycleDesc = "制造业处于扩张区间，经济动能持续好转，基本面对权益资产形成有力支撑。";
      cycleTagColor = "green";
      transmissionStance = "基本面与盈利双击";
    } else if (mfgPmi >= 49.5) {
      cycleName = "弱复苏·政策加力期";
      cycleDesc = "制造业景气度在荣枯线附近整固，流动性总闸门适度宽松，中下游成本释放带动结构性行情。";
      cycleTagColor = "blue";
      transmissionStance = "中性偏多·结构性主导";
    } else {
      cycleName = "逆周期调节·防守筑底期";
      cycleDesc = "实体需求仍待提振，货币政策保持宽松基调，低利率环境利好高股息与红利防御资产。";
      cycleTagColor = "gold";
      transmissionStance = "关注防御与高股息";
    }
  }

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
      {/* 1. 宏观周期罗盘与 A 股传导晴雨表 */}
      <div className="macro-overview-compass">
        <div className="macro-compass-header">
          <div className="macro-compass-title">
            <span className="macro-compass-badge">🇨🇳 宏观周期罗盘与 A 股传导晴雨表</span>
            <Tag color={cycleTagColor} style={{ marginLeft: 8, fontWeight: 600 }}>{cycleName}</Tag>
          </div>
          <Text className="macro-compass-source">
            数据来源：国家统计局 / 中国人民银行 / 海关总署 · 权威实时聚合
          </Text>
        </div>

        <div className="macro-compass-body">
          <div className="macro-compass-lead">
            <p className="macro-compass-desc">{cycleDesc}</p>
          </div>

          <div className="macro-compass-metrics">
            <div className="macro-compass-metric-item">
              <span className="macro-compass-metric-label">实体景气动能</span>
              <strong className="macro-compass-metric-value" style={{ color: mfgPmi != null && mfgPmi >= 50 ? c.up : c.warning }}>
                {mfgPmi != null ? (mfgPmi >= 50 ? "扩张区间" : "临界收缩") : "同步中"}
              </strong>
              <small>制造业 PMI: {mfgPmi ?? "-"}</small>
            </div>

            <div className="macro-compass-metric-item">
              <span className="macro-compass-metric-label">货币流动性</span>
              <strong className="macro-compass-metric-value" style={{ color: c.primary }}>
                充裕宽松
              </strong>
              <small>1Y LPR: {lpr1y ? `${lpr1y}%` : "-"}</small>
            </div>

            <div className="macro-compass-metric-item">
              <span className="macro-compass-metric-label">A 股基本面定调</span>
              <strong className="macro-compass-metric-value" style={{ color: c.up }}>
                {transmissionStance}
              </strong>
              <small>低利率提供估值安全垫</small>
            </div>
          </div>
        </div>
      </div>

      {/* 2. 六大宏观核心风向标（消除简单数字，升级为先导与衍生风向标） */}
      <div className="macro-overview-kpi-bar" style={{ marginBottom: 20 }}>
        <Row gutter={[12, 12]}>
          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
              <Statistic
                title="制造业 PMI (荣枯线)"
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
                {mfgPmi != null && mfgPmi >= 50 ? "● 扩张 (先导改善)" : "○ 收缩 (需政策支撑)"}
              </Text>
              <div className="macro-kpi-subtext">
                非制造业 {nonMfgPmi ?? "-"}
              </div>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
              <Statistic
                title="CPI-PPI 利润剪刀差"
                value={profitScissors ?? "-"}
                precision={2}
                suffix={profitScissors != null ? "%" : undefined}
                styles={{
                  content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: profitScissors != null && profitScissors > 0 ? c.up : c.textPrimary,
                  },
                }}
              />
              <Text style={{ color: profitScissors != null && profitScissors > 0 ? c.up : c.textMuted, fontSize: "var(--c-font-xs)", fontWeight: 500 }}>
                {profitScissors != null && profitScissors > 0 ? "📈 中下游毛利改善" : "上游成本挤压"}
              </Text>
              <div className="macro-kpi-subtext">
                CPI {cpiYoY ?? "-"}% · PPI {ppiYoY ?? "-"}%
              </div>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
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
              <div className="macro-kpi-subtext">
                全国宏观经济增长大盘
              </div>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
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
                流动性总水库充沛
              </Text>
              <div className="macro-kpi-subtext">
                流动性底线支撑估值
              </div>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
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
                期限利差 {termSpread != null ? `${termSpread}%` : "-"}
              </Text>
              <div className="macro-kpi-subtext">
                5年期以上 {lpr5y ? `${lpr5y}%` : "-"}
              </div>
            </Card>
          </Col>

          <Col xs={12} sm={8} xl={4}>
            <Card size="small" style={cardStyle} className="u-card-interactive macro-kpi-card">
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
              <Text style={{ color: expYoY != null && expYoY >= 0 ? c.up : c.down, fontSize: "var(--c-font-xs)" }}>
                {expYoY != null && expYoY >= 0 ? "海外需求保持韧性" : "外需承压需内需对冲"}
              </Text>
              <div className="macro-kpi-subtext">
                中国出海链景气风向标
              </div>
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
