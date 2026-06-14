import { Row, Col, Spin } from "antd";
import { useMacroAllData } from "../../api/queries";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const PMI_FIELDS = (c: ThemeColors) => [
  { key: "MAKE_INDEX", label: "制造业", color: c.primary },
  { key: "NMAKE_INDEX", label: "非制造业", color: c.accent },

];

export default function PmiTab() {
  const c = useColors();
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
          fields={PMI_FIELDS(c)}
        />
      </Col>
    </Row>
  );
}
