import { useMemo } from "react";
import { Card, Col, Row, Tag, Typography } from "antd";
import { FallOutlined, RiseOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamDailyFlow, NationalTeamEtfSeries } from "../../../types/stock";

const { Text } = Typography;

function formatSignedFlow(value: number | null | undefined, unit = "") {
  if (value == null || !Number.isFinite(value)) return "-";
  return `${value > 0 ? "+" : ""}${formatNumberWithSeparators(value, 1)} ${unit}`.trim();
}

const CATEGORIES_CONFIG = [
  { key: "core_broad", label: "核心大盘", desc: "沪深300 · 上证50", color: "#1677ff", tagColor: "blue" },
  { key: "a500", label: "新质A500", desc: "中证A500新一代基准", color: "#faad14", tagColor: "gold" },
  { key: "growth", label: "中小成长", desc: "中证500/1000/2000 · 双创", color: "#13c2c2", tagColor: "cyan" },
  { key: "dividend", label: "红利防御", desc: "红利低波高股息底仓", color: "#f5222d", tagColor: "red" },
] as const;

interface CategoryOverviewCardsProps {
  etfs?: NationalTeamEtfSeries[];
  latestDailyFlow?: NationalTeamDailyFlow;
}

export default function CategoryOverviewCards({ etfs = [], latestDailyFlow }: CategoryOverviewCardsProps) {
  const colors = useColors();

  const categoryStats = useMemo(() => {
    return CATEGORIES_CONFIG.map((cat) => {
      const catEtfs = etfs.filter((e) => (e.category || "core_broad") === cat.key);
      const memberCount = catEtfs.length;
      const totalShares = catEtfs.reduce((sum, e) => sum + (e.latest_shares_100m || 0), 0);
      const totalTurnover = catEtfs.reduce((sum, e) => sum + (e.latest_amount_100m || 0), 0);

      // 优先从 latestDailyFlow.flows_by_category 取聚合净申购，兜底从 etfs 累加
      const flow1d = latestDailyFlow?.flows_by_category?.[cat.key] ??
        catEtfs.reduce((sum, e) => sum + (e.latest_estimated_net_flow_100m || 0), 0);

      // 选出该类别下净申购或成交最活跃的代表 ETF
      const topEtf = [...catEtfs].sort(
        (a, b) => (b.latest_estimated_net_flow_100m ?? -9999) - (a.latest_estimated_net_flow_100m ?? -9999),
      )[0];

      return {
        ...cat,
        memberCount,
        totalShares,
        totalTurnover,
        flow1d,
        topEtf,
      };
    });
  }, [etfs, latestDailyFlow]);

  return (
    <div className="national-team-category-overview" data-testid="national-team-category-cards" style={{ marginBottom: 12 }}>
      <Row gutter={[10, 10]}>
        {categoryStats.map((item) => {
          const isPos = item.flow1d > 0;
          const isNeg = item.flow1d < 0;
          const flowColor = isPos ? colors.up : isNeg ? colors.down : colors.textPrimary;

          return (
            <Col xs={24} sm={12} lg={6} key={item.key}>
              <Card
                className="national-team-category-card"
                size="small"
                style={{
                  borderTop: `3px solid ${item.color}`,
                  borderRadius: 8,
                  background: "var(--c-bg-card)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <Text strong style={{ fontSize: 14 }}>{item.label}</Text>
                    <Tag color={item.tagColor} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px", margin: 0 }}>
                      {item.memberCount} 只
                    </Tag>
                  </div>
                  <Text type="secondary" style={{ fontSize: 11 }}>{item.desc}</Text>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, margin: "6px 0" }}>
                  <div>
                    <Text type="secondary" style={{ fontSize: 11 }}>1日估算净申购</Text>
                    <div
                      style={{
                        fontFamily: "var(--c-font-mono)",
                        fontWeight: 700,
                        fontSize: 16,
                        color: flowColor,
                        display: "flex",
                        alignItems: "center",
                        gap: 2,
                      }}
                    >
                      {isPos ? <RiseOutlined style={{ fontSize: 12 }} /> : isNeg ? <FallOutlined style={{ fontSize: 12 }} /> : null}
                      {item.flow1d !== 0 ? formatSignedFlow(item.flow1d, "亿元") : "-"}
                    </div>
                  </div>

                  <div>
                    <Text type="secondary" style={{ fontSize: 11 }}>当日成交额</Text>
                    <div style={{ fontFamily: "var(--c-font-mono)", fontWeight: 600, fontSize: 15, color: colors.textPrimary }}>
                      {item.totalTurnover > 0 ? `${formatNumberWithSeparators(item.totalTurnover, 1)} 亿元` : "-"}
                    </div>
                  </div>
                </div>

                <div style={{ borderTop: `1px dashed var(--c-border)`, paddingTop: 4, marginTop: 4, display: "flex", justifyContent: "space-between", fontSize: 11, color: colors.textSecondary }}>
                  <span>总份额: {formatNumberWithSeparators(item.totalShares, 0)} 亿份</span>
                  {item.topEtf && (
                    <span title={`净申购领跑：${item.topEtf.name}`}>
                      领跑: <Text strong style={{ fontSize: 11 }}>{item.topEtf.name} ({item.topEtf.code})</Text> ({formatSignedFlow(item.topEtf.latest_estimated_net_flow_100m, "亿")})
                    </span>
                  )}
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
