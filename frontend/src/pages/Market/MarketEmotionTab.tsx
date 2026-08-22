import type { ReactNode } from "react";
import { Button, Card, Col, Empty, Progress, Row, Space, Tag } from "antd";
import {
  DashboardOutlined,
  FireOutlined,
  LineChartOutlined,
  ReloadOutlined,
  RiseOutlined,
  WarningOutlined,
} from "@ant-design/icons";
import { useMarketEmotion } from "../../api/queries";
import RefreshBadge from "../../components/RefreshBadge";
import SectionDataState from "../../components/SectionDataState";
import { useColors, semanticTagStyle } from "../../styles/ui";
import type { ThemeColors } from "../../styles/ui";
import type { MarketEmotionDistribution } from "../../types/stock";
import "./market-emotion.css";

type EmotionTone = "cold" | "neutral" | "hot";
type MetricTone = "positive" | "warning" | "neutral";

function heatLabel(degree: number | null) {
  if (degree == null) return "暂无";
  if (degree <= 20) return "冰点";
  if (degree <= 40) return "偏冷";
  if (degree <= 60) return "中性";
  if (degree <= 80) return "活跃";
  return "亢奋";
}

function heatColor(degree: number | null, colors: ThemeColors) {
  if (degree == null) return colors.textMuted;
  if (degree <= 40) return colors.down;
  if (degree <= 60) return colors.warning;
  return colors.up;
}

function emotionTone(degree: number | null): EmotionTone {
  if (degree == null || degree <= 40) return "cold";
  if (degree <= 60) return "neutral";
  return "hot";
}

function heatDescription(degree: number | null) {
  if (degree == null) return "市场情绪评分等待更新";
  if (degree <= 20) return "情绪处于低位，等待盘面出现更明确的修复信号";
  if (degree <= 40) return "赚钱效应偏弱，市场交易情绪仍较谨慎";
  if (degree <= 60) return "多空相对均衡，行情以结构性分化为主";
  if (degree <= 80) return "市场交易活跃，赚钱效应正在扩散";
  return "情绪处于高位，活跃度与盘面波动同步提升";
}

function displayValue(value: string | number | null | undefined) {
  return value === null || value === undefined || value === "" ? "-" : value;
}

function formatFetchedAt(value: string | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}

function breadthLabel(riseCount: number, fallCount: number) {
  if (riseCount + fallCount === 0) return "涨跌等待更新";
  const differenceRatio = Math.abs(riseCount - fallCount) / (riseCount + fallCount);
  if (differenceRatio < 0.08) return "涨跌相对均衡";
  return riseCount > fallCount ? "个股涨多跌少" : "个股跌多涨少";
}

function breadthDescription(riseCount: number, fallCount: number) {
  if (riseCount + fallCount === 0) return "全市场涨跌家数等待更新";
  const difference = Math.abs(riseCount - fallCount);
  if (difference === 0) return "上涨与下跌家数持平";
  return riseCount > fallCount
    ? `上涨家数比下跌多 ${difference} 家`
    : `下跌家数比上涨多 ${difference} 家`;
}

function deltaTone(value: string | undefined) {
  return value?.trim().startsWith("-") ? "down" : "up";
}

function SectionHeading({
  icon,
  title,
  description,
  extra,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  extra?: ReactNode;
}) {
  return (
    <div className="emotion-section-heading">
      <span className="emotion-section-heading__icon">{icon}</span>
      <span>
        <span className="emotion-section-heading__title">{title}</span>
        <span className="emotion-section-heading__description">{description}</span>
      </span>
      {extra ? <span className="emotion-section-heading__extra">{extra}</span> : null}
    </div>
  );
}

function DistributionChart({ distribution }: { distribution: MarketEmotionDistribution }) {
  const rows = [
    { label: "8%以上", down: distribution.down_10, up: distribution.up_10 },
    { label: "6%～8%", down: distribution.down_8, up: distribution.up_8 },
    { label: "4%～6%", down: distribution.down_6, up: distribution.up_6 },
    { label: "2%～4%", down: distribution.down_4, up: distribution.up_4 },
    { label: "0%～2%", down: distribution.down_2, up: distribution.up_2 },
  ];
  const maxValue = Math.max(1, ...rows.flatMap((row) => [row.down, row.up]));
  const barWidth = (value: number) => value === 0 ? 0 : Math.max(3, (value / maxValue) * 100);

  return (
    <div className="emotion-distribution" aria-label="涨跌幅区间分布">
      <div className="emotion-distribution__header" aria-hidden="true">
        <span>下跌家数</span>
        <span>涨跌幅</span>
        <span>上涨家数</span>
      </div>
      {rows.map((row) => (
        <div key={row.label} className="emotion-distribution__row">
          <div className="emotion-distribution__side emotion-distribution__side--down">
            <strong>{row.down}</strong>
            <div className="emotion-distribution__track">
              <span style={{ width: `${barWidth(row.down)}%` }} />
            </div>
          </div>
          <span className="emotion-distribution__label">{row.label}</span>
          <div className="emotion-distribution__side emotion-distribution__side--up">
            <div className="emotion-distribution__track">
              <span style={{ width: `${barWidth(row.up)}%` }} />
            </div>
            <strong>{row.up}</strong>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function MarketEmotionTab() {
  const colors = useColors();
  const { data, isLoading, isFetching, error, refetch } = useMarketEmotion();
  const distribution = data?.up_down_dis;
  const hasData = Boolean(
    data && (
      data.market_degree != null
      || data.shsz_balance
      || data.preview_balance
      || data.limit_up_board.length > 0
      || distribution?.status
    ),
  );
  const degree = data?.market_degree ?? null;
  const gaugePercent = Math.min(100, Math.max(0, degree ?? 0));
  const gaugeColor = heatColor(degree, colors);
  const riseCount = distribution?.rise_num ?? 0;
  const fallCount = distribution?.fall_num ?? 0;
  const breadthTotal = riseCount + fallCount;
  const risePercent = breadthTotal > 0 ? (riseCount / breadthTotal) * 100 : 0;
  const fallPercent = breadthTotal > 0 ? 100 - risePercent : 0;
  const shortTermMetrics: Array<{
    title: string;
    value: string | number;
    hint: string;
    tone: MetricTone;
  }> = [
    { title: "封板率", value: displayValue(data?.up_ratio), hint: "涨停后成功封住", tone: "positive" },
    { title: "涨停家数", value: displayValue(data?.up_ratio_num), hint: "当日涨停数量", tone: "positive" },
    { title: "炸板家数", value: displayValue(data?.up_open_num), hint: "触板后未能封住", tone: "warning" },
    { title: "涨停股表现", value: displayValue(data?.performance), hint: "涨停股整体表现", tone: "positive" },
    { title: "炸板率", value: displayValue(data?.up_open_ratio), hint: "触板后打开比例", tone: "warning" },
    { title: "昨日涨停收益", value: displayValue(data?.profit_ratio), hint: "昨日涨停股今日表现", tone: "neutral" },
  ];

  return (
    <SectionDataState
      isLoading={isLoading && !hasData}
      error={hasData ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!isLoading && !error && !hasData}
      emptyText="暂无市场情绪数据"
      errorTitle="市场情绪加载失败"
      minHeight={480}
      skeletonRows={10}
    >
      <div className="market-emotion">
        <div className="emotion-toolbar">
          <Space size={12} wrap>
            <span>数据来源：{data?.source || "财联社"}</span>
            <span>更新时间：{formatFetchedAt(data?.fetched_at)}</span>
            <RefreshBadge />
          </Space>
          <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
            刷新
          </Button>
        </div>

        <section className={`emotion-hero emotion-hero--${emotionTone(degree)}`}>
          <Row align="stretch">
            <Col xs={24} lg={11} className="emotion-hero__summary-column">
              <div className="emotion-hero__summary">
                <div className="emotion-kicker"><DashboardOutlined /> 今日市场体感</div>
                <h2>{heatLabel(degree)} · {breadthLabel(riseCount, fallCount)}</h2>
                <p>{heatDescription(degree)}；{breadthDescription(riseCount, fallCount)}。</p>
                <Space size={[8, 8]} wrap>
                  <Tag style={semanticTagStyle("up")}>上涨 {riseCount}</Tag>
                  <Tag style={semanticTagStyle("down")}>下跌 {fallCount}</Tag>
                  <Tag>平盘 {distribution?.flat_num ?? 0}</Tag>
                </Space>
              </div>
            </Col>

            <Col xs={24} sm={10} lg={5} className="emotion-hero__gauge-column">
              <div className="emotion-gauge" aria-label={`市场热度 ${degree ?? "暂无"}`}>
                <Progress
                  type="dashboard"
                  percent={gaugePercent}
                  strokeColor={gaugeColor}
                  railColor={colors.border}
                  size={164}
                  format={() => (
                    <span className="emotion-gauge__value" style={{ color: gaugeColor }}>
                      <strong>{displayValue(degree)}</strong>
                      <small>/100</small>
                      <span>{heatLabel(degree)}</span>
                    </span>
                  )}
                />
                <div className="emotion-gauge__scale"><span>冰点</span><span>中性</span><span>亢奋</span></div>
              </div>
            </Col>

            <Col xs={24} sm={14} lg={8} className="emotion-hero__turnover-column">
              <div className="emotion-turnover">
                <div className="emotion-kicker"><LineChartOutlined /> 成交活跃度</div>
                <div className="emotion-turnover__item">
                  <span>当前两市成交额</span>
                  <strong>{displayValue(data?.shsz_balance)}</strong>
                  <small className={`emotion-delta emotion-delta--${deltaTone(data?.shsz_balance_change_px)}`}>
                    较前一日 {displayValue(data?.shsz_balance_change_px)}
                  </small>
                </div>
                <div className="emotion-turnover__item">
                  <span>预计全天成交额</span>
                  <strong>{displayValue(data?.preview_balance)}</strong>
                  <small className={`emotion-delta emotion-delta--${deltaTone(data?.preview_balance_change_px)}`}>
                    较前一日 {displayValue(data?.preview_balance_change_px)}
                  </small>
                </div>
              </div>
            </Col>
          </Row>
        </section>

        <Card
          className="emotion-section-card"
          title={(
            <SectionHeading
              icon={<FireOutlined />}
              title="短线赚钱效应"
              description="用涨停、炸板和昨日涨停表现判断短线强弱"
            />
          )}
        >
          <div className="emotion-metric-grid">
            {shortTermMetrics.map((metric) => (
              <div key={metric.title} className={`emotion-metric emotion-metric--${metric.tone}`}>
                <span>{metric.title}</span>
                <strong>{metric.value}</strong>
                <small>{metric.hint}</small>
              </div>
            ))}
          </div>
        </Card>

        <Row gutter={[16, 16]}>
          <Col xs={24} lg={14}>
            <Card
              className="emotion-section-card emotion-section-card--fill"
              title={(
                <SectionHeading
                  icon={<RiseOutlined />}
                  title="全市场涨跌结构"
                  description="看上涨是否扩散，以及涨跌幅主要集中在哪些区间"
                  extra={<Tag style={semanticTagStyle(riseCount >= fallCount ? "up" : "down")}>上涨占比 {risePercent.toFixed(1)}%</Tag>}
                />
              )}
            >
              <div className="emotion-breadth" aria-label={`上涨占比 ${risePercent.toFixed(1)}%`}>
                <div className="emotion-breadth__counts">
                  <span><small>上涨</small><strong className="is-up">{riseCount}</strong></span>
                  <span><small>下跌</small><strong className="is-down">{fallCount}</strong></span>
                </div>
                <div className="emotion-breadth__bar">
                  <span className="is-up" style={{ width: `${risePercent}%` }} />
                  <span className="is-down" style={{ width: `${fallPercent}%` }} />
                </div>
                <div className="emotion-breadth__legend">
                  <span>上涨 {risePercent.toFixed(1)}%</span>
                  <span>下跌 {fallPercent.toFixed(1)}%</span>
                </div>
              </div>

              <div className="emotion-market-status">
                <span><small>平盘</small><strong>{distribution?.flat_num ?? 0}</strong></span>
                <span><small>停牌</small><strong>{distribution?.suspend_num ?? 0}</strong></span>
                <span><small>涨停</small><strong className="is-up">{distribution?.up_num ?? 0}</strong></span>
                <span><small>跌停</small><strong className="is-down">{distribution?.down_num ?? 0}</strong></span>
              </div>

              {distribution ? <DistributionChart distribution={distribution} /> : null}
            </Card>
          </Col>

          <Col xs={24} lg={10}>
            <Card
              className="emotion-section-card emotion-section-card--fill"
              title={(
                <SectionHeading
                  icon={<WarningOutlined />}
                  title="连板梯队"
                  description="观察高标数量和晋级延续性"
                />
              )}
            >
              {(data?.limit_up_board.length || 0) > 0 ? (
                <div className="emotion-ladder">
                  {(data?.limit_up_board || []).map((item, index) => (
                    <div className="emotion-ladder__item" key={item.name}>
                      <span className="emotion-ladder__index">{index + 1}</span>
                      <span className="emotion-ladder__name">
                        <strong>{item.name}</strong>
                        <small>{item.promotion_rate ? `晋级率 ${item.promotion_rate}` : "观察市场高度"}</small>
                      </span>
                      <span className="emotion-ladder__count"><strong>{item.count}</strong> 只</span>
                    </div>
                  ))}
                </div>
              ) : (
                <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无连板数据" />
              )}
            </Card>
          </Col>
        </Row>
      </div>
    </SectionDataState>
  );
}
