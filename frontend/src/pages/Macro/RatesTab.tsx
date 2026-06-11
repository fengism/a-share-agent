import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { getColors } from "../../theme/store";

const LPR_FIELDS = [
  { key: "LPR1Y", label: "1年期", color: getColors().primary, unit: "%" },
  { key: "LPR5Y", label: "5年期", color: getColors().accent, unit: "%" },
];

const SHIBOR_FIELDS = [
  { key: "MONTH3", label: "3月", color: getColors().primary },
  { key: "MONTH6", label: "6月", color: getColors().accent },
  { key: "MONTH9", label: "9月", color: getColors().accent },
  { key: "YEAR1", label: "1年", color: getColors().down },
];

export default function RatesTab() {
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
          fields={LPR_FIELDS}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="SHIBOR 上海银行间同业拆放利率"
          latest={shibor?.latest ?? null}
          trend={shibor?.trend ?? []}
          fields={SHIBOR_FIELDS}
        />
      </Col>
    </Row>
  );
}
