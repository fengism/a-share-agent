import { useMemo } from "react";
import { useThemeStore } from "./store";
import { themes } from "./themes";
import type { ThemeColors } from "./themes";

/** Subscribe to the current theme's color palette. */
export function useColors(): ThemeColors {
  const themeKey = useThemeStore((s) => s.themeKey);
  return themes[themeKey].colors;
}

/** Generate all shared style objects based on the current theme. */
export function useStyles() {
  const c = useColors();

  return useMemo(
    () => ({
      pageContainerStyle: {
        maxWidth: 1280,
        margin: "0 auto" as const,
        padding: "0 8px 24px",
      },

      pageHeaderStyle: { marginBottom: 20 },
      pageTitleStyle: { margin: 0, color: c.textPrimary },
      pageDescriptionStyle: { fontSize: 14, marginTop: 8, color: c.textSecondary },

      cardStyle: {
        borderRadius: 10,
        border: `1px solid ${c.border}`,
        boxShadow: "0 1px 2px rgba(0,0,0,0.20)",
        background: c.cardBg,
      },

      softCardStyle: {
        borderRadius: 10,
        border: `1px solid ${c.border}`,
        boxShadow: "0 1px 2px rgba(0,0,0,0.12)",
        background: c.nestedBg,
      },

      mutedTextStyle: { color: c.textSecondary },

      sectionCardBodyStyle: { padding: "18px 22px" },

      metricTileStyle: {
        padding: "14px 16px",
        background: c.elevatedBg,
        border: `1px solid ${c.border}`,
        borderRadius: 8,
        textAlign: "center" as const,
      },

      cardContentStyle: {
        padding: "14px 16px",
        background: c.elevatedBg,
        border: `1px solid ${c.border}`,
        borderRadius: 8,
      },

      tagStyle: { marginBottom: 8, borderRadius: 999, paddingInline: 10 },

      fieldLabelStyle: { marginBottom: 4, color: c.textSecondary, fontSize: 12 },

      sectionHeaderStyle: {
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "10px 12px",
        borderRadius: 8,
        background: c.nestedBg,
        border: `1px solid ${c.border}`,
        marginBottom: 12,
      },

      metricValueEmphasisStyle: {
        fontSize: 20,
        fontWeight: 700,
        color: c.textPrimary,
        lineHeight: 1.2,
        letterSpacing: 0.1,
      },

      metricValueSecondaryStyle: {
        fontSize: 16,
        fontWeight: 600,
        color: c.textPrimary,
        lineHeight: 1.2,
      },

      gradientHeaderStyle: {
        background: c.headerGradient,
        border: `1px solid ${c.border}`,
      },
    }),
    [c],
  );
}
