import { Row, Col } from "antd";
import { useMacroAllData } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../theme/themes";

const GDP_FIELDS = (c: ThemeColors) => [
  { key: "GDP_VALUE", label: "当季值", color: c.primary, precision: 1 },
  { key: "GDP_SAME", label: "同比增长", color: c.up, unit: "%" },
];

export default function GrowthTab() {
  const c = useColors();
  const { data, isLoading, error, refetch } = useMacroAllData();

  const gdp = data?.growth?.gdp;

  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无 GDP 数据"
      errorTitle="GDP 数据加载失败"
      minHeight={280}
    >
      <Row gutter={[16, 16]}>
        <Col xs={24}>
          <MacroIndicatorCard
            title="GDP 国内生产总值（季度）"
            latest={gdp?.latest ?? null}
            trend={gdp?.trend ?? []}
            fields={GDP_FIELDS(c)}
          />
        </Col>
      </Row>
    </SectionDataState>
  );
}
