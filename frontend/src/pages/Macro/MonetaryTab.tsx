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

export default function MonetaryTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const moneySupply = data?.monetary?.money_supply;
  const socialFin = data?.monetary?.social_financing;

  const m2 = moneySupply?.latest?.BASIC_CURRENCY != null ? (Number(moneySupply.latest.BASIC_CURRENCY) / 10_000).toFixed(2) : null;
  const inc = socialFin?.latest?.SOCIAL_FINANCING_INCREMENT != null ? Number(socialFin.latest.SOCIAL_FINANCING_INCREMENT).toFixed(0) : null;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无货币数据"
      errorTitle="货币数据加载失败"
      minHeight={280}
    >
      {m2 != null ? (
        <div className="macro-insight-banner">
          <div className="macro-insight-banner__title">
            <span>💡 宏观流动性与信用派生观察</span>
            <Tag color="cyan">流动性充裕度监测</Tag>
          </div>
          <div className="macro-insight-banner__body">
            广义货币 M2 总量 <strong>{m2} 万亿元</strong>{inc != null ? <>，当期社会融资规模增量 <strong>{Number(inc).toLocaleString()} 亿元</strong></> : null}。
            M2 反映全社会总购买力与流动性池深度，社融增量刻画金融体系对实体经济资金支持力度。
          </div>
        </div>
      ) : null}

      <Row className="macro-card-grid" gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="货币供应量 M0/M1/M2（万亿元）"
            latest={moneySupply?.latest ?? null}
            trend={moneySupply?.trend ?? []}
            metadata={moneySupply}
            fields={MONEY_SUPPLY_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="社会融资规模"
            latest={socialFin?.latest ?? null}
            trend={socialFin?.trend ?? []}
            metadata={socialFin}
            fields={SOCIAL_FIN_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
