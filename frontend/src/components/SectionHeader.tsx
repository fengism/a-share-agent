import type { CSSProperties, ReactNode } from "react";
import "./section-header.css";

export interface SectionHeaderProps {
  title: ReactNode;
  icon?: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  extra?: ReactNode;
  className?: string;
  style?: CSSProperties;
  id?: string;
}

/**
 * 统一板块/卡片内小节头部组件。
 *
 * 将散落在各页面的标题、图标、副标题、标签及右侧操作区统一为标准化语义结构：
 * - 保持图标背景、字号与内外间距全站一致；
 * - 响应式自适应折行，移动端/窄栏友好；
 * - 支持 actions 与 extra 组合。
 */
export default function SectionHeader({
  title,
  icon,
  subtitle,
  badge,
  actions,
  extra,
  className,
  style,
  id,
}: SectionHeaderProps) {
  const rightSlot = actions ?? extra;

  return (
    <header
      id={id}
      className={["section-header", className].filter(Boolean).join(" ")}
      style={style}
    >
      <div className="section-header__main">
        {icon ? <span className="section-header__icon">{icon}</span> : null}
        <div className="section-header__text">
          <div className="section-header__title-row">
            <h3 className="section-header__title">{title}</h3>
            {badge ? <span className="section-header__badge">{badge}</span> : null}
          </div>
          {subtitle ? <p className="section-header__subtitle">{subtitle}</p> : null}
        </div>
      </div>
      {rightSlot ? <div className="section-header__actions">{rightSlot}</div> : null}
    </header>
  );
}
