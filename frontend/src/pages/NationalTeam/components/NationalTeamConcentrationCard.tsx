import { useMemo } from "react";
import { Card, Col, Progress, Row, Space, Statistic, Tag, Tooltip, Typography } from "antd";
import { FireOutlined, FundProjectionScreenOutlined, InfoCircleOutlined, ThunderboltOutlined } from "@ant-design/icons";
import { useColors } from "../../../styles/ui";
import { formatNumberWithSeparators } from "../../../utils/format";
import type { NationalTeamDailyFlow, NationalTeamEtfSeries } from "../../../types/stock";

const { Text } = Typography;

function formatSignedFlow(val: number | null | undefined, unit = "") {
  if (val == null || !Number.isFinite(val)) return "-";
  return `${val > 0 ? "+" : ""}${formatNumberWithSeparators(val, 1)}${unit ? " " + unit : ""}`;
}

const HEATMAP_INDICES = [
  "沪深300",
  "上证50",
  "中证A500",
  "中证500",
  "中证1000",
  "中证2000",
  "科创50",
  "科创100",
  "创业板",
  "红利低波",
] as const;

interface ConcentrationCardProps {
  etfs?: NationalTeamEtfSeries[];
  dailyFlows?: NationalTeamDailyFlow[];
  asOfDate?: string | null;
}

export default function NationalTeamConcentrationCard({
  etfs = [],
  dailyFlows = [],
  asOfDate,
}: ConcentrationCardProps) {
  const colors = useColors();

  // 1. 头部集中度 (CR3 / CR5) 计算：按单只 ETF 估算净申购计算
  const concentration = useMemo(() => {
    const positiveEtfs = etfs
      .filter((e) => (e.latest_estimated_net_flow_100m ?? 0) > 0)
      .sort((a, b) => (b.latest_estimated_net_flow_100m ?? 0) - (a.latest_estimated_net_flow_100m ?? 0));

    const totalPosFlow = positiveEtfs.reduce((sum, e) => sum + (e.latest_estimated_net_flow_100m ?? 0), 0);
    if (totalPosFlow <= 0 || positiveEtfs.length === 0) {
      return {
        hasData: false,
        cr3: 0,
        cr5: 0,
        top3Etfs: [],
        top5Etfs: [],
        totalPosFlow: 0,
        tag: "资金流出/中性",
        tagColor: "default",
      };
    }

    const top3Etfs = positiveEtfs.slice(0, 3);
    const top5Etfs = positiveEtfs.slice(0, 5);
    const top3Sum = top3Etfs.reduce((sum, e) => sum + (e.latest_estimated_net_flow_100m ?? 0), 0);
    const top5Sum = top5Etfs.reduce((sum, e) => sum + (e.latest_estimated_net_flow_100m ?? 0), 0);

    const cr3 = Math.min(100, Math.round((top3Sum / totalPosFlow) * 100));
    const cr5 = Math.min(100, Math.round((top5Sum / totalPosFlow) * 100));

    let tag = "广泛分散 · 全市场承接";
    let tagColor = "blue";
    if (cr3 >= 70) {
      tag = "高度集中 · 定点旗舰护盘";
      tagColor = "gold";
    } else if (cr3 >= 50) {
      tag = "适度集中 · 核心宽基为主";
      tagColor = "cyan";
    }

    return {
      hasData: true,
      cr3,
      cr5,
      top3Etfs,
      top5Etfs,
      totalPosFlow,
      tag,
      tagColor,
    };
  }, [etfs]);

  // 2. 连续流入/流出天数统计 (基于各宽基指数最近交易日序列)
  const indexStreaks = useMemo(() => {
    if (!dailyFlows || dailyFlows.length === 0) return [];
    // 交易日序列（升序：最新在最后）
    const flowsAsc = [...dailyFlows].sort((a, b) => a.date.localeCompare(b.date));

    return HEATMAP_INDICES.map((indexName) => {
      let streak = 0;
      let streakType: "inflow" | "outflow" | "none" = "none";
      let cumAmount = 0;

      for (let i = flowsAsc.length - 1; i >= 0; i--) {
        const flowVal = flowsAsc[i].flows_by_index?.[indexName] ?? 0;
        if (i === flowsAsc.length - 1) {
          if (flowVal > 0.05) {
            streakType = "inflow";
            streak = 1;
            cumAmount += flowVal;
          } else if (flowVal < -0.05) {
            streakType = "outflow";
            streak = 1;
            cumAmount += flowVal;
          } else {
            streakType = "none";
            break;
          }
        } else {
          if (streakType === "inflow" && flowVal > 0.05) {
            streak++;
            cumAmount += flowVal;
          } else if (streakType === "outflow" && flowVal < -0.05) {
            streak++;
            cumAmount += flowVal;
          } else {
            break;
          }
        }
      }

      // 统计近 20 日内流入天数比率 (胜率)
      const recent20 = flowsAsc.slice(-20);
      const posDays = recent20.filter((f) => (f.flows_by_index?.[indexName] ?? 0) > 0.05).length;
      const winRate = recent20.length > 0 ? Math.round((posDays / recent20.length) * 100) : 0;

      return {
        name: indexName,
        streak,
        streakType,
        cumAmount,
        winRate,
      };
    }).sort((a, b) => {
      // 优先展示流入天数最多的
      if (a.streakType === "inflow" && b.streakType !== "inflow") return -1;
      if (a.streakType !== "inflow" && b.streakType === "inflow") return 1;
      return b.streak - a.streak;
    });
  }, [dailyFlows]);

  return (
    <Card
      className="national-team-concentration-card"
      size="small"
      data-testid="national-team-concentration-card"
      title={
        <div className="national-team-concentration__head">
          <Space size={8} align="center">
            <FundProjectionScreenOutlined className="national-team-concentration__title-icon" />
            <span className="national-team-concentration__title">资金集中度与主力持续建仓动向</span>
            <Tag color={concentration.tagColor} className="national-team-concentration__tag">
              {concentration.tag}
            </Tag>
          </Space>
          <Text type="secondary" className="national-team-concentration__subtitle">
            样本池 {etfs.length} 只 ETF · 截至 {asOfDate || "最新"}
          </Text>
        </div>
      }
    >
      <Row gutter={[16, 16]}>
        {/* 左侧：CR3 与 CR5 集中度 */}
        <Col xs={24} md={10}>
          <div className="national-team-concentration__panel">
            <div className="national-team-concentration__panel-head">
              <Space size={6}>
                <FireOutlined className="national-team-concentration__icon-up" />
                <Text strong className="national-team-concentration__panel-title">头部主力聚集度 (CR3 / CR5)</Text>
              </Space>
              <Tooltip title="统计全市场当日获正向估算净申购的 ETF 中，净买入前 3 大及前 5 大 ETF 所占的资金比重。比例越高表明主力资金越集中于少数超级龙头宽基。">
                <InfoCircleOutlined className="national-team-concentration__info-icon" />
              </Tooltip>
            </div>

            <Row gutter={[10, 10]} className="national-team-concentration__cr-row">
              <Col span={12}>
                <Statistic
                  title="CR3 资金集中度"
                  value={concentration.hasData ? `${concentration.cr3}%` : "-"}
                  styles={{ content: { fontFamily: "var(--c-font-mono)", fontSize: 18, fontWeight: 700, color: concentration.cr3 >= 70 ? colors.up : colors.textPrimary } }}
                />
                <Progress
                  percent={concentration.cr3}
                  size="small"
                  showInfo={false}
                  strokeColor={concentration.cr3 >= 70 ? colors.up : colors.primary}
                  className="national-team-concentration__progress"
                />
                <Text type="secondary" className="national-team-concentration__hint">前 3 只 ETF 净流入贡献比</Text>
              </Col>
              <Col span={12}>
                <Statistic
                  title="CR5 资金集中度"
                  value={concentration.hasData ? `${concentration.cr5}%` : "-"}
                  styles={{ content: { fontFamily: "var(--c-font-mono)", fontSize: 18, fontWeight: 700, color: colors.textPrimary } }}
                />
                <Progress
                  percent={concentration.cr5}
                  size="small"
                  showInfo={false}
                  strokeColor={colors.primary}
                  className="national-team-concentration__progress"
                />
                <Text type="secondary" className="national-team-concentration__hint">前 5 只 ETF 净流入贡献比</Text>
              </Col>
            </Row>

            {concentration.top3Etfs.length > 0 && (
              <div className="national-team-concentration__top-list-wrap">
                <Text type="secondary" className="national-team-concentration__top-label">
                  今日净申购领跑旗舰 ETF：
                </Text>
                <div className="national-team-concentration__top-list">
                  {concentration.top3Etfs.map((item, idx) => (
                    <div key={item.code} className="national-team-concentration__top-row">
                      <Space size={6}>
                        <Tag color={idx === 0 ? "orange" : idx === 1 ? "gold" : "blue"} className="national-team-concentration__rank-tag">
                          No.{idx + 1}
                        </Tag>
                        <span className="national-team-concentration__item-name">{item.name}</span>
                        <span className="national-team-concentration__item-code">({item.code})</span>
                      </Space>
                      <span className="national-team-concentration__flow is-up">
                        {formatSignedFlow(item.latest_estimated_net_flow_100m, "亿元")}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Col>

        {/* 右侧：连续流入/流出天数与近 20 日胜率 */}
        <Col xs={24} md={14}>
          <div className="national-team-concentration__panel">
            <div className="national-team-concentration__panel-head">
              <Space size={6}>
                <ThunderboltOutlined className="national-team-concentration__icon-warning" />
                <Text strong className="national-team-concentration__panel-title">各宽基连续净申赎趋势与近 20 日流入率</Text>
              </Space>
              <Text type="secondary" className="national-team-concentration__panel-title-sub">识别主力持续建仓方向</Text>
            </div>

            <div className="national-team-concentration__streak-grid">
              {indexStreaks.slice(0, 6).map((item) => {
                const isInflow = item.streakType === "inflow";
                const isOutflow = item.streakType === "outflow";
                const streakText = isInflow
                  ? `连续 ${item.streak} 日流入 (+${formatNumberWithSeparators(item.cumAmount, 1)}亿)`
                  : isOutflow
                  ? `连续 ${item.streak} 日流出 (${formatNumberWithSeparators(item.cumAmount, 1)}亿)`
                  : "今日中性平稳";

                return (
                  <div key={item.name} className="national-team-concentration__streak-item">
                    <div className="national-team-concentration__streak-head">
                      <span className="national-team-concentration__streak-name">{item.name}</span>
                      <Tag
                        color={isInflow ? (item.streak >= 3 ? "red" : "volcano") : isOutflow ? "green" : "default"}
                        className="national-team-concentration__streak-tag"
                      >
                        {isInflow ? `连增 ${item.streak} 天` : isOutflow ? `连减 ${item.streak} 天` : "中性"}
                      </Tag>
                    </div>
                    <div className={`national-team-concentration__streak-text ${isInflow ? "is-up" : isOutflow ? "is-down" : "is-neutral"}`}>
                      {streakText}
                    </div>
                    <div className="national-team-concentration__streak-footer">
                      <span>近20日流入率</span>
                      <span className="national-team-concentration__streak-value">{item.winRate}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Col>
      </Row>
    </Card>
  );
}
