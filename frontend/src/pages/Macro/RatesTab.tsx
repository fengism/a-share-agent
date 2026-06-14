import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

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

export default function RatesTab() {
  const c = useColors();
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const lpr = data?.rates?.lpr;
  const shibor = data?.rates?.shibor;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="LPR 贷款市场报价利率"
          latest={lpr?.latest ?? null}
          trend={lpr?.trend ?? []}
          fields={LPR_FIELDS(c)}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="SHIBOR 上海银行间同业拆放利率"
          latest={shibor?.latest ?? null}
          trend={shibor?.trend ?? []}
          fields={SHIBOR_FIELDS(c)}
        />
      </Col>
    </Row>
  );
}
