import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";

const PMI_FIELDS = [
  { key: "MAKE_INDEX", label: "制造业", color: "#3b82f6" },
  { key: "NMAKE_INDEX", label: "非制造业", color: "#6366f1" },
];

export default function PmiTab() {
  const { data, isLoading } = useMacroAllData();

  if (isLoading) {
    return <div style={{ textAlign: "center", padding: 40 }}><Spin size="large" /></div>;
  }

  const pmi = data?.sentiment?.pmi;

  return (
    <Row gutter={[16, 16]}>
      <Col xs={24}>
        <MacroIndicatorCard
          title="PMI 采购经理人指数"
          latest={pmi?.latest ?? null}
          trend={pmi?.trend ?? []}
          fields={PMI_FIELDS}
        />
      </Col>
    </Row>
  );
}
