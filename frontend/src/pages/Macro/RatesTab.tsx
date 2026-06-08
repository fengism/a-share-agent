import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";

const LPR_FIELDS = [
  { key: "LPR1Y", label: "1年期", color: "#3b82f6", unit: "%" },
  { key: "LPR5Y", label: "5年期", color: "#6366f1", unit: "%" },
];

const SHIBOR_FIELDS = [
  { key: "MONTH3", label: "3月", color: "#3b82f6" },
  { key: "MONTH6", label: "6月", color: "#6366f1" },
  { key: "MONTH9", label: "9月", color: "#8b5cf6" },
  { key: "YEAR1", label: "1年", color: "#22c55e" },
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
