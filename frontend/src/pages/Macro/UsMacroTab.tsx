import { Alert, Col, Row, Space } from "antd";
import { useUsMacroData } from "../../api/queryHooks/market";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";

const DEFINITIONS = [
  ["gdp", "美国 GDP", [{ key: "VALUE", label: "GDP 增速", unit: "%" }]],
  ["cpi", "美国 CPI", [
    { key: "CPI_YOY", label: "同比", unit: "%" },
    { key: "CPI_MOM", label: "环比", unit: "%" },
    { key: "CORE_CPI_MOM", label: "核心环比", unit: "%" },
  ]],
  ["core_pce", "美国核心 PCE", [{ key: "VALUE", label: "核心 PCE", unit: "%" }]],
  ["labor", "美国就业", [
    { key: "UNEMPLOYMENT", label: "失业率", unit: "%" },
    { key: "NON_FARM", label: "非农就业", unit: "万人" },
    { key: "INITIAL_JOBLESS", label: "初请失业金", unit: "万人" },
  ]],
  ["pmi", "美国 PMI", [
    { key: "MANUFACTURING_PMI", label: "ISM 制造业" },
    { key: "SERVICES_PMI", label: "服务业" },
  ]],
  ["fed_rate", "美联储利率", [{ key: "VALUE", label: "目标利率", unit: "%" }]],
  ["retail_sales", "美国零售销售", [{ key: "VALUE", label: "月率", unit: "%" }]],
  ["trade_balance", "美国贸易差额", [{ key: "VALUE", label: "贸易差额", unit: "亿美元" }]],
] as const;

export default function UsMacroTab() {
  const { data, isLoading, error, refetch } = useUsMacroData();
  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!data}
      emptyText="暂无美国宏观数据"
      errorTitle="美国宏观数据加载失败"
      minHeight={280}
    >
      <Space orientation="vertical" size={12} style={{ width: "100%" }}>
        {data?.refreshing ? <Alert type="info" showIcon title="正在后台刷新美国宏观数据，当前展示最近成功快照" /> : null}
        {data?.failed_indicators && Object.keys(data.failed_indicators).length > 0 ? (
          <Alert type="warning" showIcon title={`部分指标刷新失败：${Object.keys(data.failed_indicators).join("、")}`} />
        ) : null}
      <Row gutter={[16, 16]}>
        {DEFINITIONS.map(([key, title, fields]) => {
          const indicator = data?.indicators?.[key];
          return (
            <Col xs={24} md={12} key={key}>
              <MacroIndicatorCard
                title={title}
                latest={indicator?.latest ?? null}
                trend={indicator?.trend ?? []}
                metadata={indicator}
                fields={[...fields]}
              />
            </Col>
          );
        })}
      </Row>
      </Space>
    </SectionDataState>
  );
}
