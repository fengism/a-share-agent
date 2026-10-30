import type { ReactNode } from "react";
import "./section-toolbar.css";

interface SectionToolbarProps {
  /** 左侧信息区：更新时间、数据日期、状态标签等 */
  meta?: ReactNode;
  /** 右侧操作区：刷新按钮、视图切换等 */
  actions?: ReactNode;
  /** 语义化标签，便于无障碍与测试定位 */
  ariaLabel?: string;
}

/**
 * 市场等数据页统一工具条：桌面端左右两端对齐，窄屏自动换行堆叠。
 * 消除各 Tab 各自手写 toolbar 造成的间距/对齐漂移。
 */
export default function SectionToolbar({ meta, actions, ariaLabel }: SectionToolbarProps) {
  return (
    <div className="section-toolbar" role="group" aria-label={ariaLabel}>
      {meta ? <div className="section-toolbar__meta">{meta}</div> : null}
      {actions ? <div className="section-toolbar__actions">{actions}</div> : null}
    </div>
  );
}
