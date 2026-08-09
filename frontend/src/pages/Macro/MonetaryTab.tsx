import { Row, Col } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const MONEY_SUPPLY_FIELDS = (c: ThemeColors) => [
  { key: "BASIC_CURRENCY", label: "M2", color: c.primary, precision: 1 },
  { key: "CURRENCY", label: "M1", color: c.accent, precision: 1 },
  { key: "FREE_CASH", label: "M0", color: c.accent, precision: 1 },

];

const SOCIAL_FIN_FIELDS = (c: ThemeColors) => [
  { key: "RMB_LOAN", label: "新增贷款", color: c.primary, precision: 0 },
  { key: "RMB_LOAN_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "RMB_LOAN_SEQUENTIAL", label: "环比", color: c.accent, unit: "%" },

];

export default function MonetaryTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const moneySupply = data?.monetary?.money_supply;
  const socialFin = data?.monetary?.social_financing;

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
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="货币供应量 M0/M1/M2"
            latest={moneySupply?.latest ?? null}
            trend={moneySupply?.trend ?? []}
            fields={MONEY_SUPPLY_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="社会融资规模"
            latest={socialFin?.latest ?? null}
            trend={socialFin?.trend ?? []}
            fields={SOCIAL_FIN_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
