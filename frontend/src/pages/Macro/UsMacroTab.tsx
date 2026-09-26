import { ReloadOutlined } from "@ant-design/icons";
import { Alert, Button, Col, Row, Space, Typography } from "antd";
import dayjs from "dayjs";
import { useForceRefreshUsMacroData, useUsMacroData } from "../../api/queryHooks/market";
import SectionDataState from "../../components/SectionDataState";
import MacroIndicatorCard from "./MacroIndicatorCard";

const { Text } = Typography;

const DEFINITIONS = [
  ["gdp", "美国 GDP", [{ key: "VALUE", label: "GDP 增速", unit: "%" }]],
  ["cpi", "美国 CPI", [
    { key: "CPI_YOY", label: "同比", unit: "%" },
    { key: "CPI_MOM", label: "环比", unit: "%" },
    { key: "CORE_CPI_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_CPI_MOM", label: "核心环比", unit: "%" },
  ]],
  ["ppi", "美国 PPI", [
    { key: "PPI_YOY", label: "同比", unit: "%" },
    { key: "PPI_MOM", label: "环比", unit: "%" },
    { key: "CORE_PPI_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_PPI_MOM", label: "核心环比", unit: "%" },
  ]],
  ["pce", "美国 PCE", [
    { key: "PCE_YOY", label: "同比", unit: "%" },
    { key: "PCE_MOM", label: "环比", unit: "%" },
    { key: "CORE_PCE_YOY", label: "核心同比", unit: "%" },
    { key: "CORE_PCE_MOM", label: "核心环比", unit: "%" },
  ]],
  ["labor", "美国就业", [
    { key: "UNEMPLOYMENT", label: "失业率", unit: "%" },
    // NON_FARM 是当月新增就业人数（万人），不是就业存量水平，三个数据源口径一致
    { key: "NON_FARM", label: "新增非农", unit: "万人" },
    { key: "INITIAL_JOBLESS", label: "初请失业金", unit: "万人" },
  ]],
  ["employment_details", "美国就业细项", [
    { key: "CIVILIAN_LABOR_PARTICIPATION", label: "劳动参与率", unit: "%" },
    // 时薪环比是变化率（~0.3%），与参与率水平值（~62%）量级差两个数量级，必须走副轴
    { key: "AVG_HOURLY_EARNINGS_MOM", label: "平均时薪环比", unit: "%", secondaryAxis: true },
  ]],
  ["consumer_confidence", "美国消费者信心", [{ key: "VALUE", label: "信心指数" }]],
  ["credit_spread", "美国信用利差", [{ key: "VALUE", label: "高收益利差", unit: "%" }]],
  ["pmi", "美国 PMI", [
    { key: "MANUFACTURING_PMI", label: "ISM 制造业" },
    { key: "SERVICES_PMI", label: "服务业" },
  ]],
  ["fed_rate", "美联储利率", [{ key: "VALUE", label: "目标利率", unit: "%" }]],
  ["retail_sales", "美国零售销售", [{ key: "VALUE", label: "月率", unit: "%" }]],
  ["trade_balance", "美国贸易差额", [{ key: "VALUE", label: "贸易差额", unit: "亿美元" }]],
] as const;

const INDICATOR_LABELS: Record<string, string> = Object.fromEntries(
  DEFINITIONS.map(([key, title]) => [key, title]),
);

function formatSnapshotTime(value?: string | null) {
  if (!value) return "暂无快照更新时间";
  const parsed = dayjs(value);
  return parsed.isValid() ? `快照更新于 ${parsed.format("YYYY-MM-DD HH:mm")}` : "暂无快照更新时间";
}

export default function UsMacroTab() {
  const { data, isLoading, error } = useUsMacroData();
  const forceRefresh = useForceRefreshUsMacroData();
  const failedIndicatorNames = Object.keys(data?.failed_indicators ?? {})
    .map((key) => INDICATOR_LABELS[key] ?? key);
  return (
    <SectionDataState
      isLoading={isLoading && !data}
      error={data ? undefined : error}
      onRetry={() => forceRefresh.mutate()}
      isEmpty={!data}
      emptyText="暂无美国宏观数据"
      errorTitle="美国宏观数据加载失败"
      minHeight={280}
    >
      <Space className="macro-page__alerts" orientation="vertical" size={12}>
        <div className="macro-page__snapshot-status">
          <Text type="secondary">{formatSnapshotTime(data?.updated_at)}</Text>
          <Button
            aria-label="刷新美国数据"
            icon={<ReloadOutlined />}
            loading={forceRefresh.isPending}
            onClick={() => forceRefresh.mutate()}
          >
            刷新美国数据
          </Button>
        </div>
        {data?.refreshing ? <Alert type="info" showIcon title="正在后台刷新美国宏观数据，当前展示最近成功快照" /> : null}
        {failedIndicatorNames.length > 0 ? (
          <Alert
            type="warning"
            showIcon
            title={`部分指标刷新失败：${failedIndicatorNames.join("、")}`}
            action={(
              <Button
                size="small"
                loading={forceRefresh.isPending}
                onClick={() => forceRefresh.mutate()}
              >
                重新刷新
              </Button>
            )}
          />
        ) : null}
        {data && !data.indicators?.pce?.latest ? (
          <Alert
            type="info"
            showIcon
            title="PCE 暂无数据"
            description="PCE、就业细项、消费者信心与信用利差仅由 FRED 提供，请检查管理员 FRED API Key 配置或稍后重试。"
          />
        ) : null}
        <Row className="macro-card-grid" gutter={[16, 16]}>
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
