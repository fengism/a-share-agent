import { useMemo, useState } from "react";
import { ApartmentOutlined, LinkOutlined } from "@ant-design/icons";
import { Card, Segmented, Space, Table, Tag, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { Link } from "react-router-dom";
import { useHKIndustryComparison, type HKIndustryPeerItem } from "../../api/queryHooks/hk";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useStyles } from "../../styles/ui";
import StockSectionTitle from "./StockSectionTitle";

const { Text } = Typography;

function formatVal(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function calculateMedian(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export default function HKIndustryComparisonSection({ code }: { code: string }) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const [selectedPeriod, setSelectedPeriod] = useState<string>("");

  const query = useHKIndustryComparison(code, selectedPeriod);
  const data = query.data;

  const currentPeriod = selectedPeriod || data?.current_period || data?.periods?.[0] || "";
  const peers = useMemo(() => data?.peers ?? [], [data?.peers]);

  // 计算行业中位数与当前股票排名
  const stats = useMemo(() => {
    if (!peers.length) return null;
    const peValues = peers.map((p) => p.pe).filter((v): v is number => typeof v === "number" && v > 0);
    const pbValues = peers.map((p) => p.pb).filter((v): v is number => typeof v === "number" && v > 0);

    const normCode = code.replace(/^(?:hk)?0*/i, "").padStart(5, "0");

    // 资产总计排序
    const sortedByAssets = [...peers]
      .filter((p) => p.total_assets !== null)
      .sort((a, b) => (b.total_assets ?? 0) - (a.total_assets ?? 0));
    const assetRank = sortedByAssets.findIndex((p) => p.code.padStart(5, "0") === normCode) + 1;

    // 税后利润排序
    const sortedByProfit = [...peers]
      .filter((p) => p.net_profit !== null)
      .sort((a, b) => (b.net_profit ?? 0) - (a.net_profit ?? 0));
    const profitRank = sortedByProfit.findIndex((p) => p.code.padStart(5, "0") === normCode) + 1;

    return {
      peMedian: calculateMedian(peValues),
      pbMedian: calculateMedian(pbValues),
      assetRank: assetRank > 0 ? assetRank : null,
      profitRank: profitRank > 0 ? profitRank : null,
      totalCount: peers.length,
    };
  }, [peers, code]);

  const columns: ColumnsType<HKIndustryPeerItem> = useMemo(() => {
    const normCode = code.replace(/^(?:hk)?0*/i, "").padStart(5, "0");

    return [
      {
        title: "代码",
        dataIndex: "code",
        key: "code",
        width: 100,
        fixed: "left",
        render: (itemCode: string) => {
          const isCurrent = itemCode.padStart(5, "0") === normCode;
          return (
            <Space orientation="horizontal" size={4}>
              <Link
                to={`/stock/${itemCode}`}
                style={{
                  fontWeight: isCurrent ? 700 : 500,
                  color: isCurrent ? colors.primary : undefined,
                  fontFamily: "var(--c-font-mono)",
                }}
              >
                {itemCode}
              </Link>
              {isCurrent && <Tag color="blue" style={{ fontSize: 10, marginInlineEnd: 0 }}>本股</Tag>}
            </Space>
          );
        },
      },
      {
        title: "股票简称",
        dataIndex: "name",
        key: "name",
        width: 130,
        fixed: "left",
        render: (name: string, record) => {
          const isCurrent = record.code.padStart(5, "0") === normCode;
          return <span style={{ fontWeight: isCurrent ? 700 : 400 }}>{name}</span>;
        },
      },
      {
        title: "市盈率",
        dataIndex: "pe",
        key: "pe",
        width: 100,
        align: "right",
        sorter: (a, b) => (a.pe ?? -9999) - (b.pe ?? -9999),
        render: (val: number | null, record) => {
          if (record.is_pe_loss) return <Text type="danger" style={{ fontSize: 12 }}>亏损</Text>;
          return <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatVal(val)}</span>;
        },
      },
      {
        title: "市净率",
        dataIndex: "pb",
        key: "pb",
        width: 90,
        align: "right",
        sorter: (a, b) => (a.pb ?? -9999) - (b.pb ?? -9999),
        render: (val: number | null) => (
          <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatVal(val)}</span>
        ),
      },
      {
        title: "资产总计(亿)",
        dataIndex: "total_assets",
        key: "total_assets",
        width: 120,
        align: "right",
        sorter: (a, b) => (a.total_assets ?? 0) - (b.total_assets ?? 0),
        defaultSortOrder: "descend",
        render: (val: number | null) => (
          <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatVal(val)}</span>
        ),
      },
      {
        title: "流动资产(亿)",
        dataIndex: "current_assets",
        key: "current_assets",
        width: 120,
        align: "right",
        sorter: (a, b) => (a.current_assets ?? 0) - (b.current_assets ?? 0),
        render: (val: number | null) => (
          <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatVal(val)}</span>
        ),
      },
      {
        title: "负债合计(亿)",
        dataIndex: "total_liabilities",
        key: "total_liabilities",
        width: 120,
        align: "right",
        sorter: (a, b) => (a.total_liabilities ?? 0) - (b.total_liabilities ?? 0),
        render: (val: number | null) => (
          <span style={{ fontFamily: "var(--c-font-mono)" }}>{formatVal(val)}</span>
        ),
      },
      {
        title: "资产负债率",
        dataIndex: "debt_to_assets_ratio",
        key: "debt_to_assets_ratio",
        width: 110,
        align: "right",
        sorter: (a, b) => (a.debt_to_assets_ratio ?? 0) - (b.debt_to_assets_ratio ?? 0),
        render: (val: number | null) =>
          val != null ? (
            <span style={{ fontFamily: "var(--c-font-mono)" }}>{val.toFixed(2)}%</span>
          ) : (
            "-"
          ),
      },
      {
        title: "税后利润(亿)",
        dataIndex: "net_profit",
        key: "net_profit",
        width: 120,
        align: "right",
        sorter: (a, b) => (a.net_profit ?? 0) - (b.net_profit ?? 0),
        render: (val: number | null) => {
          if (val == null) return "-";
          const isPos = val > 0;
          return (
            <span
              style={{
                fontFamily: "var(--c-font-mono)",
                color: isPos ? colors.up : val < 0 ? colors.down : undefined,
                fontWeight: 600,
              }}
            >
              {val > 0 ? `+${formatVal(val)}` : formatVal(val)}
            </span>
          );
        },
      },
    ];
  }, [code, colors]);

  const periods = data?.periods ?? [];

  return (
    <Card
      className="stock-section-card"
      title={
        <StockSectionTitle
          icon={<ApartmentOutlined />}
          title="行业地位与同业对比"
          description={
            data?.industry_path
              ? `${data.industry_path}（共 ${data.company_count || peers.length} 家公司）`
              : "港股同行业可比公司核心指标对比 (同花顺 F10)"
          }
        />
      }
      extra={
        <Space wrap size={12}>
          {periods.length > 1 && (
            <Segmented
              size="small"
              options={periods.map((p) => ({ label: p, value: p }))}
              value={currentPeriod}
              onChange={(val) => setSelectedPeriod(String(val))}
            />
          )}
          {data?.source_url && (
            <a
              href={data.source_url}
              target="_blank"
              rel="noopener noreferrer"
              style={{ fontSize: 12, display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              同花顺F10 <LinkOutlined />
            </a>
          )}
        </Space>
      }
      style={cardStyle}
    >
      <SectionDataState
        isLoading={query.isLoading}
        error={query.error}
        onRetry={() => query.refetch()}
        isEmpty={peers.length === 0}
        emptyText="暂无港股行业对比数据"
        errorTitle="行业对比数据加载失败"
        minHeight={260}
      >
        {stats && (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
              gap: 12,
              marginBottom: 16,
            }}
          >
            <div
              style={{
                padding: "8px 12px",
                background: colors.nestedBg,
                borderRadius: 8,
                borderLeft: `3px solid ${colors.primary}`,
              }}
            >
              <div style={{ fontSize: 12, color: colors.textSecondary }}>所属行业</div>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 13,
                  marginTop: 2,
                  color: colors.textPrimary,
                  whiteSpace: "nowrap",
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                }}
                title={data?.industry_path}
              >
                {data?.segment || data?.sub_industry || data?.industry || "港股板块"}
              </div>
            </div>

            <div
              style={{
                padding: "8px 12px",
                background: colors.nestedBg,
                borderRadius: 8,
                borderLeft: `3px solid ${colors.info}`,
              }}
            >
              <div style={{ fontSize: 12, color: colors.textSecondary }}>资产规模排名</div>
              <div style={{ fontWeight: 600, fontSize: 14, marginTop: 2, color: colors.textPrimary }}>
                {stats.assetRank != null ? (
                  <>
                    第 <span style={{ color: colors.primary }}>{stats.assetRank}</span> / {stats.totalCount} 名
                  </>
                ) : (
                  "-"
                )}
              </div>
            </div>

            <div
              style={{
                padding: "8px 12px",
                background: colors.nestedBg,
                borderRadius: 8,
                borderLeft: `3px solid ${colors.accent}`,
              }}
            >
              <div style={{ fontSize: 12, color: colors.textSecondary }}>税后利润排名</div>
              <div style={{ fontWeight: 600, fontSize: 14, marginTop: 2, color: colors.textPrimary }}>
                {stats.profitRank != null ? (
                  <>
                    第 <span style={{ color: colors.accent }}>{stats.profitRank}</span> / {stats.totalCount} 名
                  </>
                ) : (
                  "-"
                )}
              </div>
            </div>

            <div
              style={{
                padding: "8px 12px",
                background: colors.nestedBg,
                borderRadius: 8,
                borderLeft: `3px solid ${colors.warning}`,
              }}
            >
              <div style={{ fontSize: 12, color: colors.textSecondary }}>行业 PE 中位数</div>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  marginTop: 2,
                  color: colors.textPrimary,
                  fontFamily: "var(--c-font-mono)",
                }}
              >
                {stats.peMedian != null ? formatVal(stats.peMedian) : "-"}
              </div>
            </div>

            <div
              style={{
                padding: "8px 12px",
                background: colors.nestedBg,
                borderRadius: 8,
                borderLeft: `3px solid ${colors.success}`,
              }}
            >
              <div style={{ fontSize: 12, color: colors.textSecondary }}>行业 PB 中位数</div>
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 14,
                  marginTop: 2,
                  color: colors.textPrimary,
                  fontFamily: "var(--c-font-mono)",
                }}
              >
                {stats.pbMedian != null ? formatVal(stats.pbMedian) : "-"}
              </div>
            </div>
          </div>
        )}

        <Table<HKIndustryPeerItem>
          rowKey="code"
          size="small"
          columns={columns}
          dataSource={peers}
          pagination={{ pageSize: 10, showSizeChanger: true, pageSizeOptions: ["10", "20", "50"] }}
          scroll={{ x: 960 }}
          rowClassName={(record) => {
            const normCode = code.replace(/^(?:hk)?0*/i, "").padStart(5, "0");
            return record.code.padStart(5, "0") === normCode ? "stock-table-row-highlight" : "";
          }}
        />
        <div style={{ marginTop: 8, fontSize: 12, color: colors.textSecondary }}>
          注：财务与估值对比数据来源于同花顺 F10 行业地位，货币单位已折算为港元 (HKD)。当前报告期：{currentPeriod || "最新"}。
        </div>
      </SectionDataState>
    </Card>
  );
}
