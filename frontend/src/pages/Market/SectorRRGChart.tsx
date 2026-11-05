import { useMemo, useState } from "react";
import { Space, Tag, Typography } from "antd";
import { RadarChartOutlined } from "@ant-design/icons";
import type { IndustryRankItem } from "../../types/stock";
import { formatAmount } from "../../utils/format";
import "./sector-rrg-chart.css";

const { Text } = Typography;

export interface SectorRRGChartProps {
  sectors: IndustryRankItem[];
  onSelectSector?: (sector: { code: string; name: string }) => void;
  /** 行业历史演变尾巴轨迹映射表，key 为行业代码，值为历史各交易日状态序列 */
  historyTrails?: Record<string, Array<{ x: number; y: number; date?: string }>>;
}

interface SectorPoint {
  sector: IndustryRankItem;
  x: number; // 涨跌幅 %
  y: number; // 净流入比率 % (net_inflow / amount)
  radius: number; // 基于成交额计算气泡大小
  quadrant: "leading" | "weakening" | "lagging" | "improving";
}

export default function SectorRRGChart({ sectors, onSelectSector, historyTrails }: SectorRRGChartProps) {
  const [activeSector, setActiveSector] = useState<IndustryRankItem | null>(null);
  const [showTrails, setShowTrails] = useState(true);

  const { points, xMax, yMax, quadrantCounts } = useMemo(() => {
    let maxAbsX = 2;
    let maxAbsY = 2;
    let maxAmount = 1;

    const validSectors = sectors.filter((s) => s.code && s.name);

    validSectors.forEach((s) => {
      const chg = Math.abs(s.change_pct ?? 0);
      if (chg > maxAbsX) maxAbsX = chg;

      const amt = Math.max(s.amount ?? 0, 1);
      if (amt > maxAmount) maxAmount = amt;

      const net = s.net_inflow ?? ((s.buy_amount ?? 0) + (s.sell_amount ?? 0));
      const netRatio = Math.abs((net / amt) * 100);
      if (netRatio > maxAbsY) maxAbsY = netRatio;
    });

    // 留出 15% 边距，坐标轴更匀称
    const boundedX = Math.max(maxAbsX * 1.15, 3);
    const boundedY = Math.max(maxAbsY * 1.15, 5);

    const counts = { leading: 0, weakening: 0, lagging: 0, improving: 0 };

    const calculated: SectorPoint[] = validSectors.map((s) => {
      const x = s.change_pct ?? 0;
      const amt = Math.max(s.amount ?? 0, 1);
      const net = s.net_inflow ?? ((s.buy_amount ?? 0) + (s.sell_amount ?? 0));
      const y = (net / amt) * 100;

      let quadrant: SectorPoint["quadrant"] = "lagging";
      if (x >= 0 && y >= 0) {
        quadrant = "leading";
        counts.leading += 1;
      } else if (x >= 0 && y < 0) {
        quadrant = "weakening";
        counts.weakening += 1;
      } else if (x < 0 && y >= 0) {
        quadrant = "improving";
        counts.improving += 1;
      } else {
        quadrant = "lagging";
        counts.lagging += 1;
      }

      // 气泡半径在 6 到 18 之间
      const radius = 6 + Math.sqrt(amt / maxAmount) * 12;

      return { sector: s, x, y, radius, quadrant };
    });

    return {
      points: calculated,
      xMax: boundedX,
      yMax: boundedY,
      quadrantCounts: counts,
    };
  }, [sectors]);

  // SVG 画布尺寸
  const width = 800;
  const height = 480;
  const pad = 40;
  const plotW = width - pad * 2;
  const plotH = height - pad * 2;
  const cx = pad + plotW / 2;
  const cy = pad + plotH / 2;

  const toSvgX = (val: number) => cx + (val / xMax) * (plotW / 2);
  const toSvgY = (val: number) => cy - (val / yMax) * (plotH / 2);

  if (!sectors.length) {
    return <div className="sector-rrg-empty">暂无行业轮动数据</div>;
  }

  return (
    <div className="sector-rrg-container" role="region" aria-label="行业轮动四象限全景">
      {/* 顶部象限统计药丸栏 */}
      <div className="sector-rrg-header">
        <div className="sector-rrg-title-row">
          <RadarChartOutlined style={{ color: "var(--c-primary)", fontSize: 18 }} />
          <strong style={{ fontSize: 15 }}>行业板块轮动四象限全景 (RRG)</strong>
          <Text type="secondary" style={{ fontSize: 12 }}>
            横轴：当日涨跌幅 · 纵轴：主力净流入率 · 气泡大小：总成交额
          </Text>
        </div>

        <Space size={10} wrap className="sector-rrg-pill-badges">
          <Tag
            className={`rrg-trail-switch ${showTrails ? "is-active" : ""}`}
            style={{ cursor: "pointer", userSelect: "none" }}
            onClick={() => setShowTrails((prev) => !prev)}
          >
            {showTrails ? "🐾 轨迹连线已开启" : "🐾 显示历史轨迹"}
          </Tag>
          <Tag className="rrg-tag rrg-tag--leading">
            🚀 领先加速 ({quadrantCounts.leading})
          </Tag>
          <Tag className="rrg-tag rrg-tag--improving">
            💎 拐点改善 ({quadrantCounts.improving})
          </Tag>
          <Tag className="rrg-tag rrg-tag--weakening">
            🔄 冲高回落 ({quadrantCounts.weakening})
          </Tag>
          <Tag className="rrg-tag rrg-tag--lagging">
            📉 筑底滞后 ({quadrantCounts.lagging})
          </Tag>
        </Space>
      </div>

      {/* SVG 四象限旋转图 */}
      <div className="sector-rrg-svg-wrapper">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="sector-rrg-svg"
          preserveAspectRatio="xMidYMid meet"
        >
          {/* 四个象限背景底色 */}
          {/* 第一象限: 右上 (Leading 领先加速) */}
          <rect
            x={cx}
            y={pad}
            width={plotW / 2}
            height={plotH / 2}
            className="rrg-quadrant-bg rrg-quadrant-bg--leading"
          />
          {/* 第二象限: 左上 (Improving 拐点改善) */}
          <rect
            x={pad}
            y={pad}
            width={plotW / 2}
            height={plotH / 2}
            className="rrg-quadrant-bg rrg-quadrant-bg--improving"
          />
          {/* 第三象限: 左下 (Lagging 筑底滞后) */}
          <rect
            x={pad}
            y={cy}
            width={plotW / 2}
            height={plotH / 2}
            className="rrg-quadrant-bg rrg-quadrant-bg--lagging"
          />
          {/* 第四象限: 右下 (Weakening 冲高回落) */}
          <rect
            x={cx}
            y={cy}
            width={plotW / 2}
            height={plotH / 2}
            className="rrg-quadrant-bg rrg-quadrant-bg--weakening"
          />

          {/* 象限文字水印提示 */}
          <text x={width - pad - 12} y={pad + 24} textAnchor="end" className="rrg-quadrant-label rrg-label--leading">
            领先加速区 ➔ 强势主升
          </text>
          <text x={pad + 12} y={pad + 24} textAnchor="start" className="rrg-quadrant-label rrg-label--improving">
            拐点改善区 ➔ 资金低吸
          </text>
          <text x={pad + 12} y={height - pad - 14} textAnchor="start" className="rrg-quadrant-label rrg-label--lagging">
            筑底滞后区 ➔ 弱势防守
          </text>
          <text x={width - pad - 12} y={height - pad - 14} textAnchor="end" className="rrg-quadrant-label rrg-label--weakening">
            冲高回落区 ➔ 逢高派发
          </text>

          {/* 十字坐标轴 */}
          <line x1={pad} y1={cy} x2={width - pad} y2={cy} className="rrg-axis-line" />
          <line x1={cx} y1={pad} x2={cx} y2={height - pad} className="rrg-axis-line" />

          {/* 坐标轴刻度与标签 */}
          <text x={width - pad} y={cy + 16} textAnchor="end" className="rrg-axis-text">
            涨幅 +{xMax.toFixed(1)}%
          </text>
          <text x={pad} y={cy + 16} textAnchor="start" className="rrg-axis-text">
            跌幅 -{xMax.toFixed(1)}%
          </text>
          <text x={cx + 6} y={pad + 14} textAnchor="start" className="rrg-axis-text">
            净流入率 +{yMax.toFixed(1)}%
          </text>
          <text x={cx + 6} y={height - pad - 6} textAnchor="start" className="rrg-axis-text">
            净流出率 -{yMax.toFixed(1)}%
          </text>

          {/* 历史轨迹连线渲染 (Tail Animation / Trail Lines) */}
          {showTrails && points.map((p) => {
            const trails = historyTrails?.[p.sector.code];
            if (!trails || trails.length < 2) return null;

            const isHovered = activeSector?.code === p.sector.code;
            const strokeOpacity = activeSector ? (isHovered ? 0.95 : 0.15) : 0.45;
            const strokeWidth = isHovered ? 2.5 : 1.5;

            // 构造折线路径
            const pathPoints = trails.map((t) => `${toSvgX(t.x)},${toSvgY(t.y)}`).join(" L ");

            return (
              <g key={`trail-${p.sector.code}`} className="rrg-trail-group">
                <path
                  d={`M ${pathPoints}`}
                  fill="none"
                  className={`rrg-trail-path rrg-trail-path--${p.quadrant}`}
                  strokeWidth={strokeWidth}
                  strokeOpacity={strokeOpacity}
                  strokeDasharray={isHovered ? undefined : "3 3"}
                />
                {/* 历史起点小圆点 */}
                <circle
                  cx={toSvgX(trails[0].x)}
                  cy={toSvgY(trails[0].y)}
                  r={isHovered ? 3.5 : 2}
                  className={`rrg-trail-origin rrg-trail-origin--${p.quadrant}`}
                  opacity={strokeOpacity}
                />
              </g>
            );
          })}

          {/* 各行业气泡节点 */}
          {points.map((p) => {
            const svgX = toSvgX(p.x);
            const svgY = toSvgY(p.y);
            const isHovered = activeSector?.code === p.sector.code;

            return (
              <g
                key={p.sector.code}
                className={`rrg-bubble-group ${isHovered ? "rrg-bubble-group--active" : ""}`}
                onClick={() => onSelectSector?.({ code: p.sector.code, name: p.sector.name })}
                onMouseEnter={() => setActiveSector(p.sector)}
                onMouseLeave={() => setActiveSector(null)}
                style={{ cursor: "pointer" }}
              >
                <circle
                  cx={svgX}
                  cy={svgY}
                  r={isHovered ? p.radius + 3 : p.radius}
                  className={`rrg-circle rrg-circle--${p.quadrant}`}
                />
                <text
                  x={svgX}
                  y={svgY - p.radius - 4}
                  textAnchor="middle"
                  className={`rrg-bubble-text ${isHovered ? "rrg-bubble-text--active" : ""}`}
                >
                  {p.sector.name}
                </text>
              </g>
            );
          })}
        </svg>

        {/* 悬停卡片 */}
        {activeSector ? (
          <div className="sector-rrg-hover-card">
            <div className="hover-card-title">
              <strong>{activeSector.name}</strong>
              <Tag>{activeSector.code}</Tag>
            </div>
            <div className="hover-card-row">
              <span>涨跌幅:</span>
              <span className={Number(activeSector.change_pct) >= 0 ? "text-up" : "text-down"}>
                {Number(activeSector.change_pct) >= 0 ? "+" : ""}
                {activeSector.change_pct?.toFixed(2)}%
              </span>
            </div>
            <div className="hover-card-row">
              <span>成交额:</span>
              <span>{formatAmount(activeSector.amount)}</span>
            </div>
            <div className="hover-card-row">
              <span>净流入:</span>
              <span className={Number(activeSector.net_inflow) >= 0 ? "text-up" : "text-down"}>
                {formatAmount(activeSector.net_inflow)}
              </span>
            </div>
            <div className="hover-card-tip">点击查看成分股 ➔</div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
