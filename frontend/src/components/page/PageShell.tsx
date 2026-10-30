import type { CSSProperties, ReactNode } from "react";
import { Typography } from "antd";
import { useStyles } from "../../styles/ui";
import "./page-shell.css";

const { Paragraph } = Typography;

export interface PageHeaderProps {
  title: ReactNode;
  /** 标题前的图标 */
  icon?: ReactNode;
  /** 标题右侧的状态/标签（如「今日非交易日」「管理员」） */
  badge?: ReactNode;
  /** 一句话说明，最多两行 */
  description?: ReactNode;
  /** 右侧操作区：主操作在前，次操作收进「更多」 */
  actions?: ReactNode;
  /** 副标题上一行的小标签（如「今日市场」） */
  eyebrow?: ReactNode;
  id?: string;
}

/**
 * 页面统一头部。
 *
 * 把各页面手写的 `u-page-title + Paragraph + flex` 组合收敛到一处，
 * 保证标题字号、描述行高、操作区对齐在 12 个页面之间一致。
 */
export function PageHeader({
  title,
  icon,
  badge,
  description,
  actions,
  eyebrow,
  id = "page-title",
}: PageHeaderProps) {
  return (
    <header className="page-shell__header">
      <div className="page-shell__heading">
        {eyebrow ? <div className="page-shell__eyebrow">{eyebrow}</div> : null}
        <h1 className="page-shell__title" id={id}>
          {icon ? <span className="page-shell__title-icon">{icon}</span> : null}
          <span>{title}</span>
          {badge ? <span className="page-shell__title-badge">{badge}</span> : null}
        </h1>
        {description ? <Paragraph className="page-shell__description">{description}</Paragraph> : null}
      </div>
      {actions ? <div className="page-shell__actions">{actions}</div> : null}
    </header>
  );
}

export interface PageBodyProps {
  children: ReactNode;
  /** 页面内导航（分区胶囊 / Tabs），固定在内容上方 */
  nav?: ReactNode;
  className?: string;
  style?: CSSProperties;
}

/** 页面主体：统一间距与最小宽度约束 */
export function PageBody({ children, nav, className, style }: PageBodyProps) {
  return (
    <div className={["page-shell__body", className].filter(Boolean).join(" ")} style={style}>
      {nav ? <div className="page-shell__nav">{nav}</div> : null}
      {children}
    </div>
  );
}

export interface PageShellProps {
  children: ReactNode;
  /**
   * 容器宽度：
   * - `default` 统一最大宽度（设计 token）
   * - `full` 看板类页面占满可用宽度
   */
  width?: "default" | "full";
  className?: string;
}

/**
 * 页面骨架：统一宽度、左右留白与底部间距。
 */
export default function PageShell({ children, width = "default", className }: PageShellProps) {
  const { pageContainerStyle } = useStyles();

  return (
    <div
      className={["page-shell", `page-shell--${width}`, className].filter(Boolean).join(" ")}
      style={pageContainerStyle}
    >
      {children}
    </div>
  );
}
