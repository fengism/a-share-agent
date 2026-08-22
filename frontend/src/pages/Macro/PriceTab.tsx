import { Row, Col } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const CPI_FIELDS = (c: ThemeColors) => [
  { key: "NATIONAL_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "NATIONAL_SEQUENTIAL", label: "环比", color: c.accent, unit: "%" },
  { key: "NATIONAL_ACCUMULATE", label: "累计", color: c.primary, unit: "%" },

];

const PPI_FIELDS = (c: ThemeColors) => [
  { key: "BASE_SAME", label: "同比", color: c.up, unit: "%" },
  { key: "BASE_ACCUMULATE", label: "累计", color: c.primary, unit: "%" },

];

export default function PriceTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const cpi = data?.prices?.cpi;
  const ppi = data?.prices?.ppi;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无价格指标数据"
      errorTitle="宏观价格数据加载失败"
      minHeight={280}
    >
      <Row gutter={[16, 16]}>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="CPI 居民消费价格指数"
            latest={cpi?.latest ?? null}
            trend={cpi?.trend ?? []}
            metadata={cpi}
            fields={CPI_FIELDS(c)}
          />
        </Col>
        <Col xs={24} md={12}>
          <MacroIndicatorCard
            title="PPI 工业生产者出厂价格指数"
            latest={ppi?.latest ?? null}
            trend={ppi?.trend ?? []}
            metadata={ppi}
            fields={PPI_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
