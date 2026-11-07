import type { CSSProperties, ReactNode } from "react";
import "./dashboard-grid.css";

export interface DashboardGridProps {
  children: ReactNode;
  columns?: 1 | 2 | 3 | 4 | "auto";
  gap?: number | string;
  minItemWidth?: number;
  className?: string;
  style?: CSSProperties;
  id?: string;
}

/**
 * 仪表板 / 看板统一响应式网格组件。
 *
 * 规范：
 * - 桌面端自适应 1~4 列，或 auto 模式；
 * - 平板端 (<=1100px) 自动折叠至 2 列；
 * - 移动端 (<=768px) 自动单列流式堆叠；
 * - 支持 CSS 自定义属性控制网格间距与最小项宽。
 */
export default function DashboardGrid({
  children,
  columns = 3,
  gap = 16,
  minItemWidth = 300,
  className,
  style,
  id,
}: DashboardGridProps) {
  const isAuto = columns === "auto";
  const colsClass = isAuto ? "dashboard-grid--auto" : `dashboard-grid--cols-${columns}`;

  const customStyle: CSSProperties = {
    ...style,
    ...(gap != null ? { "--dashboard-grid-gap": typeof gap === "number" ? `${gap}px` : gap } as CSSProperties : {}),
    ...(isAuto && minItemWidth ? { "--dashboard-grid-min": `${minItemWidth}px` } as CSSProperties : {}),
  };

  return (
    <div
      id={id}
      className={["dashboard-grid", colsClass, className].filter(Boolean).join(" ")}
      style={customStyle}
    >
      {children}
    </div>
  );
}
