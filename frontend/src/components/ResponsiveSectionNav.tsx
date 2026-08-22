import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { Select, Tabs } from "antd";
import type { SelectProps } from "antd";
import { useMediaQuery } from "../hooks/useMediaQuery";
import "./responsive-section-nav.css";

export interface ResponsiveSectionNavItem {
  key: string;
  label: ReactNode;
  mobileLabel?: ReactNode;
  group?: string;
  children: ReactNode;
  onIntent?: () => void;
  preserve?: boolean;
}

interface ResponsiveSectionNavProps {
  items: ResponsiveSectionNavItem[];
  activeKey: string;
  onChange: (key: string) => void;
  ariaLabel: string;
  desktopMode?: "tabs" | "rail";
  size?: "small" | "middle" | "large";
  tabBarStyle?: CSSProperties;
  tabBarGutter?: number;
  collapseQuery?: string;
  preserveVisited?: boolean;
}

function buildSelectOptions(items: ResponsiveSectionNavItem[]): NonNullable<SelectProps<string>["options"]> {
  const hasGroups = items.some((item) => item.group);
  if (!hasGroups) {
    return items.map((item) => ({
      value: item.key,
      label: item.mobileLabel ?? item.label,
    }));
  }

  const groups = new Map<string, ResponsiveSectionNavItem[]>();
  for (const item of items) {
    const group = item.group ?? "其他";
    groups.set(group, [...(groups.get(group) ?? []), item]);
  }

  return Array.from(groups, ([label, groupItems]) => ({
    label,
    options: groupItems.map((item) => ({
      value: item.key,
      label: item.mobileLabel ?? item.label,
    })),
  }));
}

export default function ResponsiveSectionNav({
  items,
  activeKey,
  onChange,
  ariaLabel,
  desktopMode = "tabs",
  size = "large",
  tabBarStyle,
  tabBarGutter,
  collapseQuery = "(max-width: 767px)",
  preserveVisited = false,
}: ResponsiveSectionNavProps) {
  const isMobile = useMediaQuery(collapseQuery);
  const activeItem = items.find((item) => item.key === activeKey) ?? items[0];
  const activeItemKey = activeItem?.key;
  const [visitedKeys, setVisitedKeys] = useState<ReadonlySet<string>>(
    () => new Set(activeItemKey ? [activeItemKey] : []),
  );

  useEffect(() => {
    if (!preserveVisited || !activeItemKey || activeItem?.preserve === false) return;
    setVisitedKeys((current) => {
      if (current.has(activeItemKey)) return current;
      const next = new Set(current);
      next.add(activeItemKey);
      return next;
    });
  }, [activeItem?.preserve, activeItemKey, preserveVisited]);

  const handleChange = (key: string) => {
    items.find((item) => item.key === key)?.onIntent?.();
    if (preserveVisited && items.find((item) => item.key === key)?.preserve !== false) {
      setVisitedKeys((current) => {
        if (current.has(key)) return current;
        const next = new Set(current);
        next.add(key);
        return next;
      });
    }
    onChange(key);
  };

  if (!activeItem) return null;

  const sectionContent = preserveVisited ? items
    .filter((item) => item.key === activeItem.key || (item.preserve !== false && visitedKeys.has(item.key)))
    .map((item) => (
      <div
        key={item.key}
        className="responsive-section-nav__panel"
        hidden={item.key !== activeItem.key}
      >
        {item.children}
      </div>
    )) : activeItem.children;

  if (isMobile) {
    return (
      <section className="responsive-section-nav__mobile" aria-label={ariaLabel}>
        <Select
          value={activeItem.key}
          onChange={handleChange}
          options={buildSelectOptions(items)}
          size="large"
          className="responsive-section-nav__select"
          aria-label={ariaLabel}
        />
        <div className="responsive-section-nav__content">{sectionContent}</div>
      </section>
    );
  }

  if (desktopMode === "rail") {
    const groups = new Map<string, ResponsiveSectionNavItem[]>();
    for (const item of items) {
      const group = item.group ?? "";
      groups.set(group, [...(groups.get(group) ?? []), item]);
    }

    return (
      <section className="responsive-section-nav responsive-section-nav--rail">
        <nav className="responsive-section-nav__rail" aria-label={ariaLabel}>
          {Array.from(groups, ([group, groupItems]) => (
            <div className="responsive-section-nav__rail-group" key={group || "default"}>
              {group && <div className="responsive-section-nav__rail-title">{group}</div>}
              {groupItems.map((item) => (
                <button
                  type="button"
                  key={item.key}
                  className="responsive-section-nav__rail-item"
                  aria-current={item.key === activeItem.key ? "page" : undefined}
                  onPointerEnter={item.onIntent}
                  onTouchStart={item.onIntent}
                  onFocus={item.onIntent}
                  onClick={() => handleChange(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="responsive-section-nav__content">{sectionContent}</div>
      </section>
    );
  }

  return (
    <Tabs
      activeKey={activeItem.key}
      onChange={handleChange}
      size={size}
      tabBarGutter={tabBarGutter}
      items={items.map(({ key, label, children, onIntent, preserve }) => ({
        key,
        label: onIntent ? (
          <span onPointerEnter={onIntent} onTouchStart={onIntent}>{label}</span>
        ) : label,
        children,
        destroyOnHidden: preserveVisited && preserve === false,
      }))}
      destroyOnHidden={!preserveVisited}
      tabBarStyle={tabBarStyle}
      className="responsive-section-nav__tabs"
      style={{ background: "transparent" }}
    />
  );
}
