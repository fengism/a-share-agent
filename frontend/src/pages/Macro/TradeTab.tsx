import { Row, Col } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
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
  const { data, isLoading, error, refetch } = useMacroAllData();

  const exportsImports = data?.trade?.exports_imports;
  const balance = data?.trade?.balance;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无进出口数据"
      errorTitle="进出口数据加载失败"
      minHeight={280}
    >
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
    </SectionDataState>
  );
}
