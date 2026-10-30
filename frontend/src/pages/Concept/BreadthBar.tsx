import { useColors } from "../../styles/ui";

interface BreadthBarProps {
  up: number;
  flat: number;
  down: number;
  /** 是否显示「涨 x · 平 y · 跌 z」文字（默认显示） */
  showLabels?: boolean;
}

/**
 * 涨跌家数分布：一根红绿比例条 + 数字。
 * 全为 0（尚无行情）时只渲染空条，不显示误导性的「涨 0」。
 */
export default function BreadthBar({ up, flat, down, showLabels = true }: BreadthBarProps) {
  const c = useColors();
  const total = up + flat + down;

  return (
    <span className="concept-breadth" aria-label={`上涨 ${up} 平 ${flat} 下跌 ${down}`}>
      <span className="concept-breadth__bar" aria-hidden="true">
        <span style={{ flexGrow: up, background: c.up }} />
        <span style={{ flexGrow: flat, background: c.textMuted, opacity: 0.45 }} />
        <span style={{ flexGrow: down, background: c.down }} />
      </span>
      {showLabels ? (
        <span className="concept-breadth__labels">
          <span style={{ color: total ? c.up : c.textMuted }}>涨 {up}</span>
          {flat > 0 ? <span style={{ color: c.textMuted }}>平 {flat}</span> : null}
          <span style={{ color: total ? c.down : c.textMuted }}>跌 {down}</span>
        </span>
      ) : null}
    </span>
  );
}
