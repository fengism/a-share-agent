import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { getColors } from "../../theme/store";

const CPI_FIELDS = [
  { key: "NATIONAL_SAME", label: "同比", color: getColors().up, unit: "%" },
  { key: "NATIONAL_SEQUENTIAL", label: "环比", color: getColors().accent, unit: "%" },
  { key: "NATIONAL_ACCUMULATE", label: "累计", color: getColors().primary, unit: "%" },
];

const PPI_FIELDS = [
  { key: "BASE_SAME", label: "同比", color: getColors().up, unit: "%" },
  { key: "BASE_ACCUMULATE", label: "累计", color: getColors().primary, unit: "%" },
];

export default function PriceTab() {
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const cpi = data?.prices?.cpi;
  const ppi = data?.prices?.ppi;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="CPI 居民消费价格指数"
          latest={cpi?.latest ?? null}
          trend={cpi?.trend ?? []}
          fields={CPI_FIELDS}
        />
      </Col>
      <Col xs={24} md={12}>
        <MacroIndicatorCard
          title="PPI 工业生产者出厂价格指数"
          latest={ppi?.latest ?? null}
          trend={ppi?.trend ?? []}
          fields={PPI_FIELDS}
        />
      </Col>
    </Row>
  );
}
