import { useMemo, useState } from "react";
import { AppstoreOutlined, TableOutlined } from "@ant-design/icons";
import { Card, Empty, Segmented, Table, Tooltip, Typography } from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
import { useColors, useStyles } from "../../../styles/ui";
import { formatPercent } from "./formatters";

const { Text } = Typography;

interface MonthlyReturnsHeatmapProps {
  monthlyReturns: QuantBacktestResult["monthly_returns"];
}

interface YearRow {
  year: string;
  months: Record<number, number | undefined>; // 1-12
  yearTotal: number | undefined;
}

const MONTH_COLS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12];

export default function MonthlyReturnsHeatmap({ monthlyReturns }: MonthlyReturnsHeatmapProps) {
  const [viewMode, setViewMode] = useState<"heatmap" | "list">("heatmap");
  const colors = useColors();
  const { cardStyle } = useStyles();

  // Process data into matrix by Year
  const { rows, maxAbsReturn } = useMemo(() => {
    if (!monthlyReturns || monthlyReturns.length === 0) {
      return { rows: [], maxAbsReturn: 10 };
    }

    const byYear: Record<string, Record<number, number>> = {};
    let maxAbs = 5;

    for (const item of monthlyReturns) {
      if (!item.month) continue;
      const [yearStr, monthStr] = item.month.split("-");
      if (!yearStr || !monthStr) continue;
      const monthNum = parseInt(monthStr, 10);
      if (isNaN(monthNum) || monthNum < 1 || monthNum > 12) continue;

      if (!byYear[yearStr]) {
        byYear[yearStr] = {};
      }
      byYear[yearStr][monthNum] = item.return_pct;
      if (Math.abs(item.return_pct) > maxAbs) {
        maxAbs = Math.abs(item.return_pct);
      }
    }

    const sortedYears = Object.keys(byYear).sort((a, b) => b.localeCompare(a)); // Descending by year
    const resultRows: YearRow[] = sortedYears.map((year) => {
      const months = byYear[year];
      // Compounded year return: (product(1 + r/100) - 1) * 100
      let compoundFactor = 1;
      let hasData = false;
      for (const m of MONTH_COLS) {
        if (months[m] !== undefined) {
          compoundFactor *= 1 + months[m] / 100;
          hasData = true;
        }
      }
      const yearTotal = hasData ? (compoundFactor - 1) * 100 : undefined;
      return { year, months, yearTotal };
    });

    return { rows: resultRows, maxAbsReturn: Math.max(maxAbs, 10) };
  }, [monthlyReturns]);

  // Compute heatmap cell style
  const getCellStyle = (val: number | undefined) => {
    if (val === undefined) {
      return { background: "transparent", color: "var(--c-text-muted)" };
    }
    const ratio = Math.min(Math.abs(val) / maxAbsReturn, 1);
    const alpha = Math.max(0.12, ratio * 0.75);
    const bgBase = val >= 0 ? colors.up : colors.down;
    return {
      background: `color-mix(in srgb, ${bgBase} ${Math.round(alpha * 100)}%, transparent)`,
      color: "var(--c-text-primary)",
      fontWeight: Math.abs(val) > 3 ? 600 : 400,
    };
  };

  return (
    <Card
      title={(
        <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span>月度收益分布</span>
          <Tooltip title="对冲基金标准月度收益率热力图，红涨绿跌，右侧为各自然年几何复合累计收益">
            <span style={{ fontSize: 12, color: "var(--c-text-muted)", cursor: "pointer" }}>ⓘ</span>
          </Tooltip>
        </span>
      )}
      extra={(
        <Segmented
          size="small"
          options={[
            { label: "热力矩阵", value: "heatmap", icon: <AppstoreOutlined /> },
            { label: "明细列表", value: "list", icon: <TableOutlined /> },
          ]}
          value={viewMode}
          onChange={(v) => setViewMode(v as "heatmap" | "list")}
          aria-label="月度收益视图切换"
        />
      )}
      size="small"
      style={cardStyle}
      className="quant-result-card quant-table-card"
    >
      {monthlyReturns.length === 0 ? (
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无月度收益" />
      ) : viewMode === "heatmap" ? (
        <div style={{ overflowX: "auto", paddingBottom: 4 }}>
          <table
            style={{
              width: "100%",
              minWidth: 620,
              borderCollapse: "separate",
              borderSpacing: "3px",
              textAlign: "center",
              fontSize: 12,
              fontVariantNumeric: "tabular-nums",
            }}
            aria-label="月度收益热力矩阵"
          >
            <thead>
              <tr style={{ color: "var(--c-text-muted)" }}>
                <th style={{ padding: "4px 6px", textAlign: "left", width: 56 }}>年份</th>
                {MONTH_COLS.map((m) => (
                  <th key={m} style={{ padding: "4px 2px", fontWeight: 500 }}>
                    {m}月
                  </th>
                ))}
                <th style={{ padding: "4px 6px", textAlign: "right", width: 72 }}>全年累计</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ year, months, yearTotal }) => (
                <tr key={year}>
                  <td style={{ padding: "5px 6px", textAlign: "left", fontWeight: 600 }}>{year}</td>
                  {MONTH_COLS.map((m) => {
                    const val = months[m];
                    const style = getCellStyle(val);
                    return (
                      <td
                        key={m}
                        style={{
                          padding: "5px 2px",
                          borderRadius: 3,
                          transition: "all 0.2s",
                          ...style,
                        }}
                        title={val !== undefined ? `${year}年${m}月: ${formatPercent(val)}` : `${year}年${m}月: 无交易`}
                      >
                        {val !== undefined ? (
                          <span style={{ fontSize: 11 }}>
                            <span style={{ display: "none" }}>{`${year}-${String(m).padStart(2, "0")}`}</span>
                            {val > 0 ? `+${val.toFixed(1)}%` : `${val.toFixed(1)}%`}
                          </span>
                        ) : (
                          <span style={{ opacity: 0.3 }}>-</span>
                        )}
                      </td>
                    );
                  })}
                  <td
                    style={{
                      padding: "5px 6px",
                      textAlign: "right",
                      fontWeight: 700,
                      borderRadius: 3,
                      ...getCellStyle(yearTotal),
                    }}
                  >
                    {yearTotal !== undefined ? (
                      <Text style={{ color: yearTotal >= 0 ? colors.up : colors.down }}>
                        {formatPercent(yearTotal)}
                      </Text>
                    ) : (
                      "-"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        /* List fallback view */
        <Table
          size="small"
          rowKey="month"
          pagination={monthlyReturns.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
          dataSource={monthlyReturns}
          locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无月度收益" /> }}
          columns={[
            { title: "月份", dataIndex: "month" },
            {
              title: "收益率",
              dataIndex: "return_pct",
              align: "right",
              className: "financial-num",
              render: (value: number) => (
                <Text style={{ color: value >= 0 ? colors.up : colors.down }}>
                  {formatPercent(value)}
                </Text>
              ),
            },
          ]}
        />
      )}
    </Card>
  );
}
