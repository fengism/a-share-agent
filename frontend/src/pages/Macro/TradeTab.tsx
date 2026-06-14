import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const EXPORTS_IMPORTS_FIELDS = (c: ThemeColors) => [
  { key: "EXPORTS_SAME", label: "出口同比", color: c.primary, unit: "%" },
  { key: "IMPORTS_SAME", label: "进口同比", color: c.accent, unit: "%" },

];

const BALANCE_FIELDS = (c: ThemeColors) => [
  { key: "BALANCE", label: "贸易差额", color: c.accent, precision: 1 },

];

export default function TradeTab() {
  const c = useColors();
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
          fields={EXPORTS_IMPORTS_FIELDS(c)}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="贸易差额"
          latest={balance?.latest ?? null}
          trend={balance?.trend ?? []}
          fields={BALANCE_FIELDS(c)}
        />
      </Col>
    </Row>
  );
}
