import { useCallback, useId, useState } from "react";
import { CheckOutlined, SkinOutlined } from "@ant-design/icons";
import { THEME_LIST, useThemeStore } from "../styles/ui";
import { useDismissibleLayer } from "../hooks/useDismissibleLayer";
import "./theme-selector.css";

interface ThemeSelectorProps {
  iconOnly?: boolean;
}

export default function ThemeSelector({ iconOnly = false }: ThemeSelectorProps) {
  const [open, setOpen] = useState(false);
  const menuId = useId();
  const themeKey = useThemeStore((state) => state.themeKey);
  const setThemeKey = useThemeStore((state) => state.setThemeKey);
  const activeTheme = THEME_LIST.find((theme) => theme.key === themeKey) ?? THEME_LIST[0];
  const dismiss = useCallback(() => setOpen(false), []);
  const { containerRef, triggerRef } = useDismissibleLayer(open, dismiss);

  return (
    <div ref={containerRef} className="theme-selector">
      <button
        ref={triggerRef}
        type="button"
        className={`theme-selector-trigger${iconOnly ? " theme-selector-trigger--icon" : ""}`}
        aria-label={`切换主题，当前为${activeTheme.label}`}
        aria-controls={open ? menuId : undefined}
        aria-expanded={open}
        aria-haspopup="true"
        title={iconOnly ? `当前主题：${activeTheme.label}` : undefined}
        onClick={() => setOpen((current) => !current)}
      >
        <SkinOutlined />
        {!iconOnly && <span>{activeTheme.label}</span>}
      </button>
      {open && (
        <div id={menuId} className="theme-selector-menu" role="radiogroup" aria-label="选择界面主题">
          <div className="theme-selector-menu__title">界面主题</div>
          {THEME_LIST.map((theme) => (
            <button
              type="button"
              role="radio"
              aria-checked={theme.key === themeKey}
              className="theme-selector-option"
              key={theme.key}
              onClick={() => {
                setThemeKey(theme.key);
                setOpen(false);
              }}
            >
              <span className="theme-selector-option__swatch" style={{ background: theme.colors.logoGradient }}>
                <span style={{ background: theme.colors.pageBg }} />
                <span style={{ background: theme.colors.cardBg }} />
              </span>
              <span className="theme-selector-option__text">
                <strong>{theme.label}</strong>
                <small>{theme.labelEn}</small>
              </span>
              {theme.key === themeKey && <CheckOutlined className="theme-selector-option__check" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
