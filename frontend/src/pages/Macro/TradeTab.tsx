import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { getColors } from "../../theme/store";

const EXPORTS_IMPORTS_FIELDS = [
  { key: "EXPORTS_SAME", label: "出口同比", color: getColors().primary, unit: "%" },
  { key: "IMPORTS_SAME", label: "进口同比", color: getColors().accent, unit: "%" },
];

const BALANCE_FIELDS = [
  { key: "BALANCE", label: "贸易差额", color: getColors().accent, precision: 1 },
];

export default function TradeTab() {
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const exportsImports = data?.trade?.exports_imports;
  const balance = data?.trade?.balance;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="进出口同比增速"
          latest={exportsImports?.latest ?? null}
          trend={exportsImports?.trend ?? []}
          fields={EXPORTS_IMPORTS_FIELDS}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="贸易差额"
          latest={balance?.latest ?? null}
          trend={balance?.trend ?? []}
          fields={BALANCE_FIELDS}
        />
      </Col>
    </Row>
  );
}
