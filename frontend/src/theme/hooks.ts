import type React from "react";
import { useMemo } from "react";
import { useThemeStore } from "./store";
import { themes } from "./themes";
import type { ThemeColors, ThemeMeta, DesignTokens } from "./themes";
import { APP_FONT_FAMILY, APP_MONO_FONT_FAMILY } from "./typography";

/** Subscribe to the current theme's color palette. */
export function useColors(): ThemeColors {
  const themeKey = useThemeStore((s) => s.themeKey);
  return themes[themeKey].colors;
}

/** Subscribe to the current theme's structured design tokens. */
export function useTokens(): DesignTokens {
  const themeKey = useThemeStore((s) => s.themeKey);
  return themes[themeKey].tokens;
}

/**
 * Flatten a theme's structured design tokens into CSS custom properties
 * (`{"--c-radius-md":"8px", ...}`).
 *
 * Called from `App.tsx` alongside the color variables, so all token CSS vars
 * live on `<html>` as the single source of truth. `--theme-*` aliases have been
 * retired — every consumer now references `--c-*` directly.
 */
export function tokensToCssVars(meta: ThemeMeta): Record<string, string> {
  const t = meta.tokens;
  const vars: Record<string, string> = {
    // radius
    "--c-radius-sm": t.radius.sm,
    "--c-radius-md": t.radius.md,
    "--c-radius-lg": t.radius.lg,
    "--c-radius-xl": t.radius.xl,
    "--c-radius-pill": t.radius.pill,
    // shadow
    "--c-shadow-xs": t.shadow.xs,
    "--c-shadow-sm": t.shadow.sm,
    "--c-shadow-md": t.shadow.md,
    "--c-shadow-lg": t.shadow.lg,
    // space
    "--c-space-1": t.space[1],
    "--c-space-2": t.space[2],
    "--c-space-3": t.space[3],
    "--c-space-4": t.space[4],
    "--c-space-5": t.space[5],
    "--c-space-6": t.space[6],
    "--c-space-7": t.space[7],
    "--c-space-8": t.space[8],
    // font
    "--c-font-xs": t.font.xs,
    "--c-font-sm": t.font.sm,
    "--c-font-md": t.font.md,
    "--c-font-base": t.font.base,
    "--c-font-lg": t.font.lg,
    "--c-font-xl": t.font.xl,
    "--c-font-2xl": t.font["2xl"],
    "--c-font-3xl": t.font["3xl"],
    "--c-font-display": t.font.display,
    // leading
    "--c-leading-tight": t.leading.tight,
    "--c-leading-normal": t.leading.normal,
    "--c-leading-relaxed": t.leading.relaxed,
    // weight
    "--c-weight-normal": t.weight.normal,
    "--c-weight-medium": t.weight.medium,
    "--c-weight-semibold": t.weight.semibold,
    "--c-weight-bold": t.weight.bold,
    "--c-weight-heavy": t.weight.heavy,
    // z
    "--c-z-header": t.z.header,
    "--c-z-sidebar": t.z.sidebar,
    "--c-z-drawer": t.z.drawer,
    "--c-z-modal": t.z.modal,
    // container
    "--c-container-page": t.container.page,
    "--c-container-feed": t.container.feed,
    "--c-container-wide": t.container.wide,
    // semantic colors (also surfaced as CSS vars for CSS-only consumers)
    "--c-success": meta.colors.success,
    "--c-warning": meta.colors.warning,
    "--c-error": meta.antToken.colorError,
    "--c-info": meta.colors.info,
    "--c-on-primary": meta.colors.onPrimary,
    // shared font stacks
    "--c-font-sans": APP_FONT_FAMILY,
    "--c-font-mono": APP_MONO_FONT_FAMILY,
    // double-rule borders (Feed newspaper style, width only — color stays var(--c-text-primary))
    "--c-border-double": "3px",
    "--c-border-double-wide": "4px",
  };

  return vars;
}

/** Generate all shared style objects based on the current theme. */
export function useStyles() {
  const c = useColors();
  const t = useTokens();

  return useMemo(
    () => ({
      pageContainerStyle: {
        maxWidth: t.container.page,
        width: "100%",
        margin: "0 auto" as const,
        padding: `0 ${t.space[3]} ${t.space[6]}`,
        boxSizing: "border-box" as const,
      },

      pageHeaderStyle: { marginBottom: t.space[5] },
      pageTitleStyle: { margin: 0, color: c.textPrimary },
      pageDescriptionStyle: { fontSize: t.font.base, marginTop: t.space[2], color: c.textSecondary },

      cardStyle: {
        borderRadius: t.radius.md,
        border: `1px solid ${c.border}`,
        boxShadow: t.shadow.xs,
        background: c.cardBg,
      },

      softCardStyle: {
        borderRadius: t.radius.md,
        border: `1px solid ${c.border}`,
        boxShadow: t.shadow.xs,
        background: c.nestedBg,
      },

      mutedTextStyle: { color: c.textSecondary },

      sectionCardBodyStyle: { padding: `${t.space[5]} ${t.space[6]}` },

      metricTileStyle: {
        padding: `${t.space[3]} ${t.space[4]}`,
        background: c.hoverBg,
        border: `1px solid ${c.border}`,
        borderRadius: t.radius.md,
        textAlign: "center" as const,
      },

      cardContentStyle: {
        padding: `${t.space[3]} ${t.space[4]}`,
        background: c.hoverBg,
        border: `1px solid ${c.border}`,
        borderRadius: t.radius.md,
      },

      tagStyle: { marginBottom: t.space[2], borderRadius: t.radius.pill, paddingInline: t.space[3] },

      fieldLabelStyle: { marginBottom: t.space[1], color: c.textSecondary, fontSize: t.font.sm },

      sectionHeaderStyle: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: `${t.space[2]} ${t.space[3]}`,
        borderRadius: t.radius.md,
        background: c.nestedBg,
        border: `1px solid ${c.border}`,
        marginBottom: t.space[3],
      },

      metricValueEmphasisStyle: {
        fontSize: t.font["2xl"],
        fontWeight: Number(t.weight.bold),
        color: c.textPrimary,
        lineHeight: Number(t.leading.tight),
        letterSpacing: 0.1,
        fontFamily: "var(--c-font-mono)",
        fontVariantNumeric: "tabular-nums",
      },

      metricValueSecondaryStyle: {
        fontSize: t.font.lg,
        fontWeight: Number(t.weight.semibold),
        color: c.textPrimary,
        lineHeight: Number(t.leading.tight),
        fontFamily: "var(--c-font-mono)",
        fontVariantNumeric: "tabular-nums",
      },

      gradientHeaderStyle: {
        background: c.headerGradient,
        border: `1px solid ${c.border}`,
      },

      /** Row gutter scales (antd Row.gutter takes a number → px). */
      rowGutter: parseFloat(t.space[3]),
      rowGutterLarge: parseFloat(t.space[4]),
    }),
    [c, t],
  );
}

/**
 * Semantic tag color token names. antd `<Tag color={hex}>` computes a 0.95
 * lightness background for any non-preset/non-status color (see
 * `antd/es/tag/hooks/useColor.js`), which produces light-filled chips in dark
 * theme. Passing one of these token names — resolved to a CSS var — keeps the
 * background a transparent tint that reads correctly in both themes.
 */
export type SemanticTagColor =
  | "up"
  | "down"
  | "warning"
  | "primary"
  | "accent"
  | "info"
  | "success";

const SEMANTIC_TAG_VARS: Record<SemanticTagColor, string> = {
  up: "var(--c-up)",
  down: "var(--c-down)",
  warning: "var(--c-warning)",
  primary: "var(--c-primary)",
  accent: "var(--c-accent)",
  info: "var(--c-info)",
  success: "var(--c-success)",
};

/**
 * Inline style for a semantic antd `<Tag>`: transparent tinted background +
 * colored hairline border + colored text. Matches the chip treatment already
 * used in chat.css (`.chat-plan-step-status.is-*`), so Tags stop rendering as
 * light-filled chips in dark theme while keeping the A-share up=red / down=green
 * convention.
 *
 * Use on a plain `<Tag>` (no `color` prop) so the `Tag.defaultBg: transparent`
 * ConfigProvider override is the base, e.g. `<Tag style={semanticTagStyle("up")}>`.
 */
export function semanticTagStyle(color: SemanticTagColor): React.CSSProperties {
  const v = SEMANTIC_TAG_VARS[color];
  return {
    color: v,
    borderColor: `var(--c-border)`,
    background: `var(--c-hover-bg)`,
  };
}
