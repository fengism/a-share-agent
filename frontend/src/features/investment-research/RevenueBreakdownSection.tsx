import { useEffect, useMemo, useState } from "react";
import { Card, Segmented, Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { useRevenueBreakdown } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../theme/hooks";
import type { RevenueBreakdown, RevenueBreakdownItem } from "../../types/stock";
import { formatAmount } from "../../utils/format";

const { Text } = Typography;
type DimensionKey = "by_product" | "by_business" | "by_region";

const DIMENSIONS: { key: DimensionKey; label: string }[] = [
  { key: "by_product", label: "产品" },
  { key: "by_business", label: "业务" },
  { key: "by_region", label: "地区" },
];

function formatPercentage(value: number | null) {
  return value === null ? "-" : `${value.toFixed(2)}%`;
}

function amountCell(value: number | null, color: string) {
  return <span className="financial-data-table__number" style={{ color }}>{formatAmount(value)}</span>;
}

export default function RevenueBreakdownSection({
  code,
  exportData,
  isExportingPdf = false,
}: {
  code: string;
  exportData?: RevenueBreakdown;
  isExportingPdf?: boolean;
}) {
  const c = useColors();
  const { cardStyle, sectionHeaderStyle } = useStyles();
  const query = useRevenueBreakdown(code);
  const data = exportData ?? query.data;
  const isLoading = !exportData && query.isLoading;
  const error = exportData ? null : query.error;
  const [activeDimension, setActiveDimension] = useState<DimensionKey>("by_product");
  const availableDimensions = useMemo(
    () => DIMENSIONS.filter(({ key }) => (data?.[key]?.length ?? 0) > 0),
    [data],
  );

  useEffect(() => {
    setActiveDimension("by_product");
  }, [code]);

  useEffect(() => {
    if (!availableDimensions.some(({ key }) => key === activeDimension) && availableDimensions[0]) {
      setActiveDimension(availableDimensions[0].key);
    }
  }, [activeDimension, availableDimensions]);

  const rows = useMemo(
    () => (data?.[activeDimension] ?? []).map((item, index) => ({
      ...item,
      row_key: `${activeDimension}-${item.id ?? "row"}-${index}`,
    })),
    [activeDimension, data],
  );
  const columns = useMemo<ColumnsType<RevenueBreakdownItem & { row_key: string }>>(() => [
    {
      title: "构成项",
      dataIndex: "class_name",
      key: "class_name",
      fixed: isExportingPdf ? undefined : "left",
      width: 190,
      render: (value: string, record: RevenueBreakdownItem) => (
        <Text
          strong={!record.is_sub_item}
          type={record.is_sub_item ? "secondary" : undefined}
          style={{ color: record.is_sub_item ? undefined : c.textPrimary, paddingInlineStart: record.is_sub_item ? 16 : 0 }}
        >
          {value}
        </Text>
      ),
    },
    {
      title: "营业收入",
      dataIndex: "revenue",
      key: "revenue",
      width: 130,
      align: "right",
      render: (value: number | null) => amountCell(value, value !== null && value < 0 ? c.down : c.textPrimary),
    },
    {
      title: "营业成本",
      dataIndex: "cost",
      key: "cost",
      width: 130,
      align: "right",
      render: (value: number | null) => amountCell(value, value !== null && value < 0 ? c.down : c.textSecondary),
    },
    {
      title: "毛利润",
      dataIndex: "gross_profit",
      key: "gross_profit",
      width: 130,
      align: "right",
      render: (value: number | null) => amountCell(value, value === null ? c.textMuted : value >= 0 ? c.up : c.down),
    },
    {
      title: "营收占比",
      dataIndex: "revenue_share_pct",
      key: "revenue_share_pct",
      width: 110,
      align: "right",
      render: (value: number | null) => <span className="financial-data-table__number">{formatPercentage(value)}</span>,
    },
    {
      title: "毛利率",
      dataIndex: "gross_margin_pct",
      key: "gross_margin_pct",
      width: 100,
      align: "right",
      render: (value: number | null) => <span className="financial-data-table__number">{formatPercentage(value)}</span>,
    },
  ], [c.down, c.textMuted, c.textPrimary, c.textSecondary, c.up, isExportingPdf]);

  const totalRows = availableDimensions.reduce(
    (count, { key }) => count + (data?.[key]?.length ?? 0),
    0,
  );

  return (
    <div
      data-pdf-group={isExportingPdf ? true : undefined}
      data-pdf-revenue-ready={!isLoading && !error && totalRows > 0 ? "true" : "false"}
      data-pdf-revenue-row-count={totalRows}
      className="financial-data-section"
    >
      <div style={sectionHeaderStyle}>
        <Text strong className="financial-data-section__header-title">营收与毛利构成</Text>
        <Text type="secondary" className="financial-data-section__header-note">新浪最新披露口径</Text>
      </div>
      <SectionDataState
        isLoading={isLoading}
        error={error}
        onRetry={() => query.refetch()}
        isEmpty={!data || availableDimensions.length === 0}
        emptyText="暂无营收与毛利构成数据"
        errorTitle="营收与毛利构成加载失败"
        skeletonRows={4}
        minHeight={180}
      >
        <Card size="small" className="financial-revenue-card" style={cardStyle}>
          {availableDimensions.length > 1 ? (
            <Segmented
              block
              value={activeDimension}
              onChange={(value) => setActiveDimension(value as DimensionKey)}
              options={availableDimensions.map(({ key, label }) => ({ value: key, label }))}
              className="financial-revenue-card__tabs"
            />
          ) : null}
          <div className="pdf-hide" data-testid="revenue-breakdown-interactive">
            <Table<RevenueBreakdownItem & { row_key: string }>
              dataSource={rows}
              columns={columns}
              rowKey="row_key"
              size="small"
              pagination={false}
              scroll={isExportingPdf ? undefined : { x: 790 }}
            />
          </div>
          <div className="revenue-breakdown-pdf">
            {availableDimensions.map(({ key, label }) => {
              const dimensionRows = (data?.[key] ?? []).map((item, index) => ({
                ...item,
                row_key: `${key}-${item.id ?? "row"}-${index}`,
              }));
              return (
                <div
                  key={key}
                  className="pdf-avoid-break financial-revenue-dimension"
                  data-pdf-section
                  data-testid="pdf-revenue-dimension"
                  data-pdf-row-count={dimensionRows.length}
                >
                  <Text strong className="financial-revenue-dimension__title">{label}</Text>
                  <Table<RevenueBreakdownItem & { row_key: string }>
                    dataSource={dimensionRows}
                    columns={columns}
                    rowKey="row_key"
                    size="small"
                    pagination={false}
                  />
                </div>
              );
            })}
          </div>
          <Text type="secondary" className="financial-data-section__footnote">
            上游未提供报告期；金额按上游原值展示（观测为人民币元，币种未声明）。不同维度或条目可能重叠，不做跨维度汇总；缩进项表示上游标记的子项。
          </Text>
        </Card>
      </SectionDataState>
    </div>
  );
}
