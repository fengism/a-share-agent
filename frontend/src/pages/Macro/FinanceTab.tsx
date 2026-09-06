import { Row, Col, Tag } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const MONEY_SUPPLY_FIELDS = (c: ThemeColors) => [
  { key: "BASIC_CURRENCY", label: "M2", color: c.primary, precision: 2, valueDivisor: 10_000 },
  { key: "CURRENCY", label: "M1", color: c.accent, precision: 2, valueDivisor: 10_000 },
  { key: "FREE_CASH", label: "M0", color: c.accent, precision: 2, valueDivisor: 10_000 },
];

const SOCIAL_FIN_FIELDS = (c: ThemeColors) => [
  { key: "SOCIAL_FINANCING_INCREMENT", label: "社融增量", color: c.primary, unit: "亿元", precision: 0 },
  { key: "RMB_LOAN", label: "人民币贷款", color: c.accent, unit: "亿元", precision: 0 },
  { key: "GOVERNMENT_BOND", label: "政府债券", color: c.up, unit: "亿元", precision: 0 },
  { key: "CORPORATE_BOND", label: "企业债券", color: c.warning, unit: "亿元", precision: 0 },
];

const LPR_FIELDS = (c: ThemeColors) => [
  { key: "LPR1Y", label: "1年期", color: c.primary, unit: "%" },
  { key: "LPR5Y", label: "5年期", color: c.accent, unit: "%" },
];

const SHIBOR_FIELDS = (c: ThemeColors) => [
  { key: "MONTH3", label: "3月", color: c.primary },
  { key: "MONTH6", label: "6月", color: c.accent },
  { key: "MONTH9", label: "9月", color: c.accent },
  { key: "YEAR1", label: "1年", color: c.down },
];

export default function FinanceTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const moneySupply = data?.monetary?.money_supply;
  const socialFin = data?.monetary?.social_financing;
  const lpr = data?.rates?.lpr;
  const shibor = data?.rates?.shibor;

  const m2 = moneySupply?.latest?.BASIC_CURRENCY != null ? (Number(moneySupply.latest.BASIC_CURRENCY) / 10_000).toFixed(2) : null;
  const lpr1y = lpr?.latest?.LPR1Y != null ? Number(lpr.latest.LPR1Y) : null;
  const lpr5y = lpr?.latest?.LPR5Y != null ? Number(lpr.latest.LPR5Y) : null;
  const termSpread = lpr1y != null && lpr5y != null ? Number((lpr5y - lpr1y).toFixed(2)) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无金融货币数据"
      errorTitle="金融数据加载失败"
      minHeight={280}
    >
      <div className="macro-insight-banner">
        <div className="macro-insight-banner__title">
          <span>💡 宏观金融与货币流动性环境总览</span>
          <Tag color="cyan">M2 流动性池 + 资金利率</Tag>
        </div>
        <div className="macro-insight-banner__body">
          广义货币 M2 总量 <strong>{m2 ?? "-"} 万亿元</strong>
          {termSpread != null ? <>，1Y LPR <strong>{lpr1y?.toFixed(2)}%</strong> / 5Y LPR <strong>{lpr5y?.toFixed(2)}%</strong>（期限利差 <strong className="financial-num">{termSpread}%</strong>）</> : null}。
          综合反映全社会流动性格局与银行间同业拆放资金面松紧度。
        </div>
      </div>

      <div className="macro-section-divider"><span>💰 货币供应量与信用派生</span></div>
      <Row className="macro-card-grid" gutter={[16, 16]}>
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
            title="社会融资规模"
            latest={socialFin?.latest ?? null}
            trend={socialFin?.trend ?? []}
            metadata={socialFin}
            fields={SOCIAL_FIN_FIELDS(c)}
          />
        </Col>
      </Row>

      <div className="macro-section-divider"><span>🏦 政策基准与市场资金利率</span></div>
      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="LPR 贷款市场报价利率"
            latest={lpr?.latest ?? null}
            trend={lpr?.trend ?? []}
            metadata={lpr}
            fields={LPR_FIELDS(c)}
          />
        </Col>
        <Col xs={24} xl={12}>
          <MacroIndicatorCard
            title="SHIBOR 上海银行间同业拆放利率"
            latest={shibor?.latest ?? null}
            trend={shibor?.trend ?? []}
            metadata={shibor}
            fields={SHIBOR_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
