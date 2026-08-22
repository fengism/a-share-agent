import { Row, Col } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const PMI_FIELDS = (c: ThemeColors) => [
  { key: "MAKE_INDEX", label: "制造业", color: c.primary },
  { key: "NMAKE_INDEX", label: "非制造业", color: c.accent },

];

export default function PmiTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const pmi = data?.sentiment?.pmi;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无 PMI 数据"
      errorTitle="PMI 数据加载失败"
      minHeight={280}
    >
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <MacroIndicatorCard
            title="PMI 采购经理人指数"
            latest={pmi?.latest ?? null}
            trend={pmi?.trend ?? []}
            metadata={pmi}
            fields={PMI_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
