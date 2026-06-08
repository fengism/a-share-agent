import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";

const GDP_FIELDS = [
  { key: "GDP_VALUE", label: "当季值", color: "#3b82f6", precision: 1 },
  { key: "GDP_SAME", label: "同比增长", color: "#ef4444", unit: "%" },
];

export default function GrowthTab() {
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const gdp = data?.growth?.gdp;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24}>
        <MacroIndicatorCard
          title="GDP 国内生产总值（季度）"
          latest={gdp?.latest ?? null}
          trend={gdp?.trend ?? []}
          fields={GDP_FIELDS}
        />
      </Col>
    </Row>
  );
}
