import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import "./section-anchor-nav.css";

export interface SectionAnchorItem {
  id: string;
  label: string;
  /** 右侧摘要（如「3 条」），用于一眼判断是否值得展开 */
  badge?: ReactNode;
}

interface SectionAnchorNavProps {
  items: SectionAnchorItem[];
  ariaLabel: string;
  /** 目录点击后滚动定位的吸顶偏移 */
  scrollOffset?: number;
}

/**
 * 分区目录条（chips）。
 *
 * 长页面（复盘、设置等）用它把「这一页有哪几段」直接摆在顶部，
 * 点击滚动到对应锚点；窄屏横向可滑动，当前项自动滚入视野。
 */
export default function SectionAnchorNav({ items, ariaLabel, scrollOffset = 96 }: SectionAnchorNavProps) {
  const [activeId, setActiveId] = useState(items[0]?.id ?? "");
  const navRef = useRef<HTMLDivElement | null>(null);

  const handleJump = useCallback((id: string) => {
    setActiveId(id);
    const target = typeof document === "undefined" ? null : document.getElementById(id);
    if (!target) return;
    const top = target.getBoundingClientRect().top + window.scrollY - scrollOffset;
    window.scrollTo({ top, behavior: "smooth" });
  }, [scrollOffset]);

  useEffect(() => {
    const nav = navRef.current;
    if (!nav || !activeId) return;
    const active = nav.querySelector<HTMLElement>(`[data-anchor-id="${activeId}"]`);
    active?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [activeId]);

  if (items.length === 0) return null;

  return (
    <div className="section-anchor-nav" ref={navRef} role="navigation" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          data-anchor-id={item.id}
          className="section-anchor-nav__chip"
          aria-current={item.id === activeId ? "true" : undefined}
          onClick={() => handleJump(item.id)}
        >
          <span>{item.label}</span>
          {item.badge ? <span className="section-anchor-nav__badge">{item.badge}</span> : null}
        </button>
      ))}
    </div>
  );
}
