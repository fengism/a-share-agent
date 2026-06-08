import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";

const MONEY_SUPPLY_FIELDS = [
  { key: "BASIC_CURRENCY", label: "M2", color: "#3b82f6", precision: 1 },
  { key: "CURRENCY", label: "M1", color: "#6366f1", precision: 1 },
  { key: "FREE_CASH", label: "M0", color: "#f59e0b", precision: 1 },
];

const SOCIAL_FIN_FIELDS = [
  { key: "RMB_LOAN", label: "新增贷款", color: "#3b82f6", precision: 0 },
  { key: "RMB_LOAN_SAME", label: "同比", color: "#ef4444", unit: "%" },
  { key: "RMB_LOAN_SEQUENTIAL", label: "环比", color: "#f59e0b", unit: "%" },
];

export default function MonetaryTab() {
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const moneySupply = data?.monetary?.money_supply;
  const socialFin = data?.monetary?.social_financing;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="货币供应量 M0/M1/M2"
          latest={moneySupply?.latest ?? null}
          trend={moneySupply?.trend ?? []}
          fields={MONEY_SUPPLY_FIELDS}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="社会融资规模"
          latest={socialFin?.latest ?? null}
          trend={socialFin?.trend ?? []}
          fields={SOCIAL_FIN_FIELDS}
        />
      </Col>
    </Row>
  );
}
