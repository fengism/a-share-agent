import { useMemo } from "react";
import { Alert, Space, Tag, Typography } from "antd";
import { CheckCircleOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamResponse } from "../../../types/stock";

const { Text } = Typography;

interface AnomalyBannerProps {
  data?: NationalTeamResponse;
}

export default function NationalTeamAnomalyBanner({ data }: AnomalyBannerProps) {
  const colors = useColors();

  const signals = useMemo(() => {
    if (!data) return [];
    const list: Array<{ type: "warning" | "info" | "success"; title: string; desc: string }> = [];

    // 1. 盘中主力放量异动
    const abnormalEtfs = (data.etfs || []).filter((e) => e.is_abnormal_volume);
    if (abnormalEtfs.length > 0) {
      const topAbnormal = [...abnormalEtfs].sort((a, b) => (b.latest_amount_100m ?? 0) - (a.latest_amount_100m ?? 0))[0];
      const desc = `今日监测到 ${abnormalEtfs.length} 只核心宽基出现 1.8x 以上异常放量。其中 ${topAbnormal.name}（${topAbnormal.code}）成交额达 ${formatNumberWithSeparators(topAbnormal.latest_amount_100m, 1)} 亿元，量比 ${topAbnormal.volume_ratio?.toFixed(1) || "-"}x。`;
      list.push({
        type: "warning",
        title: "盘中主力异常放量",
        desc,
      });
    }

    // 2. 逆势托底背离监测
    const flows = data.daily_flows || [];
    if (flows.length >= 2) {
      const latest = flows[flows.length - 1];
      const prev = flows[flows.length - 2];
      const benchChangePct = (latest.benchmark_close && prev.benchmark_close)
        ? ((latest.benchmark_close - prev.benchmark_close) / prev.benchmark_close) * 100
        : 0;
      const netFlow = latest.total_flow_100m ?? 0;

      if (benchChangePct <= -0.3 && netFlow >= 15.0) {
        list.push({
          type: "success",
          title: "指数与资金逆势托底背离",
          desc: `基准指数下跌 ${benchChangePct.toFixed(2)}%，但核心宽基 ETF 逆势实现强力估算净申购 +${formatNumberWithSeparators(netFlow, 1)} 亿元，展现典型逢跌托底特征。`,
        });
      }
    }

    // 3. 连续净申购建仓方向
    if (flows.length >= 3) {
      let consecutiveDays = 0;
      let cumSum = 0;
      for (let i = flows.length - 1; i >= 0; i--) {
        const f = flows[i].total_flow_100m ?? 0;
        if (f > 1.0) {
          consecutiveDays++;
          cumSum += f;
        } else {
          break;
        }
      }
      if (consecutiveDays >= 3) {
        list.push({
          type: "info",
          title: "连续多日资金净流入",
          desc: `核心宽基 ETF 已连续 ${consecutiveDays} 个交易日保持正向资金流入，区间累计估算增持 +${formatNumberWithSeparators(cumSum, 1)} 亿元。`,
        });
      }
    }

    // 4. 托底强度指数活跃提示
    if (data.support_score && data.support_score.score >= 65) {
      list.push({
        type: "warning",
        title: "国家队托底雷达高景气",
        desc: `当前托底强度评分为 ${Math.round(data.support_score.score)} 分（${data.support_score.status === "strong" ? "强力托底" : "积极托底"}），资金托底与板块扩散显著。`,
      });
    }

    return list;
  }, [data]);

  if (!data) return null;

  if (signals.length === 0) {
    return (
      <Alert
        data-testid="national-team-anomaly-banner"
        message={
          <Space size={8} align="center">
            <CheckCircleOutlined style={{ color: colors.down }} />
            <Text strong style={{ fontSize: 12 }}>资金动向处于常态平稳区间</Text>
            <Text type="secondary" style={{ fontSize: 11 }}>未监测到异常极端放量或大幅度指数背离异动。</Text>
          </Space>
        }
        type="info"
        showIcon={false}
        className="national-team-anomaly-alert"
        style={{ marginBottom: 10, borderRadius: 6, padding: "4px 10px", background: "transparent", border: "1px dashed var(--c-border)" }}
      />
    );
  }

  return (
    <div data-testid="national-team-anomaly-banner" style={{ marginBottom: 12 }}>
      {signals.map((sig, idx) => (
        <Alert
          key={idx}
          type={sig.type}
          showIcon
          icon={<ThunderboltOutlined style={{ color: sig.type === "warning" ? "#faad14" : sig.type === "success" ? colors.up : colors.primary }} />}
          message={
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 6 }}>
              <Space size={6} align="center">
                <Text strong style={{ fontSize: 13 }}>{sig.title}</Text>
                <Tag color={sig.type === "warning" ? "gold" : sig.type === "success" ? "red" : "blue"} style={{ fontSize: 10, lineHeight: "16px", padding: "0 4px" }}>
                  实时信号
                </Tag>
              </Space>
              <Text type="secondary" style={{ fontSize: 12 }}>{sig.desc}</Text>
            </div>
          }
          style={{ marginBottom: idx < signals.length - 1 ? 6 : 0, borderRadius: 8, padding: "7px 12px" }}
        />
      ))}
    </div>
  );
}
