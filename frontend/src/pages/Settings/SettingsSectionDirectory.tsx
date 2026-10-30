import { useCallback, useEffect, useRef, useState } from "react";
import { SETTINGS_SCROLL_OFFSET, type SettingsDirectoryItem } from "./settingsSections";
import "./settings.css";

interface SettingsSectionDirectoryProps {
  items: SettingsDirectoryItem[];
  ariaLabel: string;
}

/**
 * 分区内卡片目录条。
 *
 * 设置页单分区可能包含多张大卡片，纵向很长；目录条让用户直接跳到目标分组，
 * 同时作为"本分区有哪些配置"的概览。
 */
export default function SettingsSectionDirectory({ items, ariaLabel }: SettingsSectionDirectoryProps) {
  const [activeId, setActiveId] = useState(items[0]?.id ?? "");
  const navRef = useRef<HTMLDivElement | null>(null);

  const handleJump = useCallback((id: string) => {
    setActiveId(id);
    const target = typeof document === "undefined" ? null : document.getElementById(id);
    if (!target) return;
    const top = target.getBoundingClientRect().top + window.scrollY - SETTINGS_SCROLL_OFFSET;
    window.scrollTo({ top, behavior: "smooth" });
  }, []);

  // 当前选中的目录项保持在可视区域内（窄屏横向滚动时尤其重要）
  useEffect(() => {
    const nav = navRef.current;
    if (!nav || !activeId) return;
    const active = nav.querySelector<HTMLElement>(`[data-directory-id="${activeId}"]`);
    active?.scrollIntoView?.({ block: "nearest", inline: "nearest" });
  }, [activeId]);

  if (items.length === 0) return null;

  return (
    <div className="settings-directory" ref={navRef} role="navigation" aria-label={ariaLabel}>
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          data-directory-id={item.id}
          className="settings-directory__chip"
          aria-current={item.id === activeId ? "true" : undefined}
          onClick={() => handleJump(item.id)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
