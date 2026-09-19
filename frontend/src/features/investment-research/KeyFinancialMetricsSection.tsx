import { useEffect, useState } from "react";
import { Segmented, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useFinancial } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../theme/hooks";
import type { FundamentalExportData } from "../../types/stock";
import {
  buildKeyFinancialMetricGroups,
  formatKeyFinancialMetricValue,
  type KeyFinancialMetric,
  type KeyFinancialMetricGroup,
} from "./financialStatementPresentation";
import "./stock-research-typography.css";
import "./financial-data-sections.css";

const { Text } = Typography;
type MetricGroupKey = KeyFinancialMetricGroup["key"];

type FinancialMetricExportData = Pick<FundamentalExportData, "balance" | "profit" | "cashflow">;

export default function KeyFinancialMetricsSection({
  code,
  isExportingPdf = false,
  exportData,
  showHeader = true,
}: {
  code: string;
  isExportingPdf?: boolean;
  exportData?: FinancialMetricExportData;
  showHeader?: boolean;
}) {
  const colors = useColors();
  const { sectionHeaderStyle } = useStyles();
  const [activeGroup, setActiveGroup] = useState<MetricGroupKey>("profitability");
  const balanceQuery = useFinancial(code, "balance");
  const profitQuery = useFinancial(code, "profit");
  const cashflowQuery = useFinancial(code, "cashflow");
  const balance = exportData?.balance ?? balanceQuery.data;
  const profit = exportData?.profit ?? profitQuery.data;
  const cashflow = exportData?.cashflow ?? cashflowQuery.data;

  useEffect(() => {
    setActiveGroup("profitability");
  }, [code]);

  const isLoading = !exportData && (balanceQuery.isLoading || profitQuery.isLoading || cashflowQuery.isLoading);
  const error = exportData ? null : balanceQuery.error || profitQuery.error || cashflowQuery.error;
  const groups = buildKeyFinancialMetricGroups(balance, profit, cashflow);
  const selectedGroup = groups.find((group) => group.key === activeGroup);

  const renderTable = (group: KeyFinancialMetricGroup) => {
    if (group.periods.length === 0) {
      return <div className="financial-data-section__empty">暂无数据</div>;
    }
    const columns: ColumnsType<KeyFinancialMetric> = [
      {
        title: "指标",
        dataIndex: "label",
        key: "label",
        width: 220,
        fixed: isExportingPdf ? undefined : "left",
        render: (label: string) => (
          <Text strong className="financial-statement-table__metric" style={{ color: colors.textPrimary }}>
            {label}
          </Text>
        ),
      },
      ...group.periods.map(({ key, label }, periodIndex) => ({
        title: <span className="financial-statement-table__period">{label}</span>,
        key,
        width: 150,
        align: "right" as const,
        render: (_: unknown, row: KeyFinancialMetric) => (
          <span
            className="financial-statement-table__value"
            title={row.values[periodIndex] === null ? "" : String(row.values[periodIndex])}
            style={{ color: colors.textSecondary }}
          >
            {formatKeyFinancialMetricValue(row.values[periodIndex] ?? null, row.format)}
          </span>
        ),
      })),
    ];
    return (
      <div className="financial-statement-table-wrap">
        <Table
          dataSource={group.metrics}
          columns={columns}
          rowKey="key"
          size="small"
          scroll={isExportingPdf ? undefined : { x: 220 + group.periods.length * 150 }}
          pagination={false}
          rowClassName={() => "terminal-table-row"}
        />
      </div>
    );
  };

  const metricsReady = !isLoading && !error && groups.every((group) => group.periods.length > 0);
  const metricRowCount = groups.reduce((total, group) => total + group.metrics.length, 0);

  return (
    <div
      data-pdf-financial-ready={metricsReady ? "true" : "false"}
      className="financial-data-sections key-financial-metrics"
    >
      {showHeader ? (
        <div style={sectionHeaderStyle} data-pdf-group={isExportingPdf ? true : undefined}>
          <Text strong className="financial-data-section__header-title">关键财务指标</Text>
          <Text type="secondary" className="financial-data-section__header-note">最近四个报告期</Text>
        </div>
      ) : null}
      <SectionDataState
        isLoading={isLoading}
        error={error}
        onRetry={() => Promise.all([
          balanceQuery.refetch(),
          profitQuery.refetch(),
          cashflowQuery.refetch(),
        ])}
        errorTitle="关键财务指标加载失败"
        skeletonRows={6}
        minHeight={280}
      >
        <div style={{ width: "100%", minWidth: 0, overflowX: "hidden" }}>
          {isExportingPdf ? (
            <div
              className="pdf-key-financial-metrics financial-statement-section"
              data-pdf-section
              data-pdf-group
              data-testid="pdf-key-financial-metrics"
              data-pdf-row-count={metricRowCount}
            >
              {groups.map((group) => (
                <div key={group.key} className="pdf-avoid-break financial-metric-group">
                  <Text strong className="financial-statement-section__title">{group.label}</Text>
                  {renderTable(group)}
                </div>
              ))}
            </div>
          ) : (
            <>
              <Segmented
                block
                value={activeGroup}
                onChange={(value) => setActiveGroup(value as MetricGroupKey)}
                options={groups.map(({ key, label }) => ({ value: key, label }))}
                className="financial-statement-tabs"
              />
              {selectedGroup ? renderTable(selectedGroup) : null}
            </>
          )}
        </div>
      </SectionDataState>
    </div>
  );
}
