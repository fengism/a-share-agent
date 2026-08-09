import type { CSSProperties, ReactNode } from "react";
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
}

interface ResponsiveSectionNavProps {
  items: ResponsiveSectionNavItem[];
  activeKey: string;
  onChange: (key: string) => void;
  ariaLabel: string;
  desktopMode?: "tabs" | "rail";
  size?: "small" | "middle" | "large";
  tabBarStyle?: CSSProperties;
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
}: ResponsiveSectionNavProps) {
  const isMobile = useMediaQuery("(max-width: 767px)");
  const activeItem = items.find((item) => item.key === activeKey) ?? items[0];

  if (!activeItem) return null;

  if (isMobile) {
    return (
      <section className="responsive-section-nav__mobile" aria-label={ariaLabel}>
        <Select
          value={activeItem.key}
          onChange={onChange}
          options={buildSelectOptions(items)}
          size="large"
          className="responsive-section-nav__select"
          aria-label={ariaLabel}
        />
        <div className="responsive-section-nav__content">{activeItem.children}</div>
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
                  onClick={() => onChange(item.key)}
                >
                  {item.label}
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="responsive-section-nav__content">{activeItem.children}</div>
      </section>
    );
  }

  return (
    <Tabs
      activeKey={activeItem.key}
      onChange={onChange}
      size={size}
      items={items.map(({ key, label, children }) => ({ key, label, children }))}
      destroyOnHidden
      tabBarStyle={tabBarStyle}
      style={{ background: "transparent" }}
    />
  );
}
