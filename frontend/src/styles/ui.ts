/**
 * Shared style tokens for the A-Share Agent UI.
 *
 * Static exports are kept for backward compatibility with files that
 * haven't been migrated to the hook-based API yet.  New code should
 * prefer `useColors()` and `useStyles()` from `../theme/hooks` (or
 * re-exported below) so that styles update reactively when the user
 * switches themes.
 */

import { themes } from "../theme/themes";

// ── Static (default = stellar-blue) – backward compat ──────────────
export const darkColors = themes["stellar-blue"].colors;

export const pageContainerStyle = {
  maxWidth: 1280,
  margin: "0 auto",
  padding: "0 8px 24px",
};

export const pageHeaderStyle = {
  marginBottom: 20,
};

export const pageTitleStyle = {
  margin: 0,
  color: "#e5e7eb",
};

export const pageDescriptionStyle = {
  fontSize: 14,
  marginTop: 8,
  color: "#9ca3af",
};

export const gradientHeaderStyle = {
  background: "linear-gradient(135deg, #1e3a5f, #0f172a)",
  border: "1px solid #1e293b",
};

export const cardStyle = {
  borderRadius: 12,
  border: "1px solid #1e293b",
  boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
  background: "#111827",
};

export const softCardStyle = {
  borderRadius: 12,
  border: "1px solid #1e293b",
  boxShadow: "0 2px 8px rgba(0,0,0,0.2)",
  background: "#0f1720",
};

export const mutedTextStyle = {
  color: "#9ca3af",
};

export const sectionCardBodyStyle = {
  padding: "18px 22px",
};

export const metricTileStyle = {
  padding: "14px 16px",
  background: "#1a2332",
  border: "1px solid #1e293b",
  borderRadius: 10,
  textAlign: "center" as const,
};

export const tagStyle = {
  marginBottom: 8,
  borderRadius: 999,
  paddingInline: 10,
};

export const fieldLabelStyle = {
  marginBottom: 4,
  color: "#9ca3af",
  fontSize: 12,
};

export const sectionHeaderStyle = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  padding: "10px 12px",
  borderRadius: 8,
  background: "#0f1720",
  border: "1px solid #1e293b",
  marginBottom: 12,
};

export const metricValueEmphasisStyle = {
  fontSize: 20,
  fontWeight: 700,
  color: "#e5e7eb",
  lineHeight: 1.2,
  letterSpacing: 0.1,
};

export const metricValueSecondaryStyle = {
  fontSize: 16,
  fontWeight: 600,
  color: "#e5e7eb",
  lineHeight: 1.2,
};

// ── Hook-based (reactive) – preferred ──────────────────────────────
export { useColors, useStyles } from "../theme/hooks";
export { useThemeStore } from "../theme/store";
export { THEME_LIST } from "../theme/themes";
export type { ThemeKey, ThemeColors } from "../theme/themes";
export { getAntToken } from "../theme/store";
export { getColors } from "../theme/store";
