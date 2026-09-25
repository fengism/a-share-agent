export type ThemeKey = "stellar-blue" | "light";

export interface ThemeColors {
  pageBg: string;
  cardBg: string;
  elevatedBg: string;
  nestedBg: string;
  primary: string;
  accent: string;
  up: string;
  down: string;
  upBg: string;
  downBg: string;
  upCardGradient: string;
  downCardGradient: string;
  /** Semantic colors — kept in sync with the antToken equivalents so
      business components can consume them through useColors() without
      reaching into antd token internals. */
  success: string;
  warning: string;
  info: string;
  /** Text color on top of `primary` fills (buttons, logo marks). */
  onPrimary: string;
  /** Interactive row/tile hover background — distinct from `elevatedBg`
      (which means "raised one layer above the card"), so hover feedback
      never reads as an elevation change. */
  hoverBg: string;
  /** Pressed/active interactive background, one step denser than hover. */
  activeBg: string;
  textPrimary: string;
  textSecondary: string;
  textMuted: string;
  border: string;
  headerGradient: string;
  logoGradient: string;
  focusRing: string;
  surfaceOverlay: string;
  authBackground: string;
  authHeroGradient: string;
  cardShadow: string;
}

/**
 * Structured design tokens (radius / shadow / spacing / typography /
 * elevation / container width). Each theme defines its own values so that
 * light themes can use softer shadows while dark themes use stronger ones.
 * Flattened to CSS custom properties by `tokensToCssVars()` and injected on
 * `<html>` from `App.tsx`.
 */
export interface DesignTokens {
  radius: { sm: string; md: string; lg: string; xl: string; pill: string };
  shadow: { xs: string; sm: string; md: string; lg: string };
  space: { 1: string; 2: string; 3: string; 4: string; 5: string; 6: string; 7: string; 8: string };
  font: { xs: string; sm: string; md: string; base: string; lg: string; xl: string; "2xl": string; "3xl": string; display: string };
  leading: { tight: string; normal: string; relaxed: string };
  weight: { normal: string; medium: string; semibold: string; bold: string; heavy: string };
  z: { header: string; sidebar: string; drawer: string; modal: string };
  container: { page: string; feed: string; wide: string };
}

export interface ThemeMeta {
  key: ThemeKey;
  label: string;
  labelEn: string;
  isLight: boolean;
  colors: ThemeColors;
  antToken: {
    colorPrimary: string;
    colorPrimaryHover: string;
    colorPrimaryActive: string;
    colorPrimaryBg: string;
    colorInfo: string;
    colorSuccess: string;
    colorWarning: string;
    colorError: string;
    colorBgLayout: string;
    colorBgContainer: string;
    colorBgElevated: string;
    colorBorder: string;
    colorBorderSecondary: string;
    colorText: string;
    colorTextSecondary: string;
  };
  siderBg: string;
  headerBg: string;
  tokens: DesignTokens;
}

// ── Structured design tokens ──────────────────────────────────────────────
// Shared scales differ between dark and light themes mostly in shadow depth:
// dark themes use stronger, lower-opacity shadows; light themes use softer,
// higher-opacity ones. Radius/spacing/font/leading/weight/z/container scales
// are identical across themes.

const SHARED_RADIUS: DesignTokens["radius"] = {
  sm: "6px",
  md: "8px",
  lg: "12px",
  xl: "16px",
  pill: "999px",
};

const SHARED_SPACE: DesignTokens["space"] = {
  1: "4px",
  2: "8px",
  3: "12px",
  4: "16px",
  5: "20px",
  6: "24px",
  7: "28px",
  8: "32px",
};

const SHARED_FONT: DesignTokens["font"] = {
  xs: "11px",
  sm: "12px",
  md: "13px",
  base: "14px",
  lg: "16px",
  xl: "18px",
  "2xl": "20px",
  "3xl": "24px",
  display: "32px",
};

const SHARED_LEADING: DesignTokens["leading"] = {
  tight: "1.2",
  normal: "1.5",
  relaxed: "1.7",
};

const SHARED_WEIGHT: DesignTokens["weight"] = {
  normal: "400",
  medium: "500",
  semibold: "600",
  bold: "700",
  heavy: "800",
};

const SHARED_Z: DesignTokens["z"] = {
  header: "100",
  sidebar: "110",
  drawer: "1000",
  modal: "1050",
};

const SHARED_CONTAINER: DesignTokens["container"] = {
  page: "1680px",
  feed: "1280px",
  wide: "1800px",
};

const DARK_TOKENS: DesignTokens = {
  radius: SHARED_RADIUS,
  shadow: {
    xs: "0 1px 2px rgba(0,0,0,0.20)",
    sm: "0 1px 3px rgba(0,0,0,0.24)",
    md: "0 4px 12px rgba(0,0,0,0.22)",
    lg: "0 12px 32px rgba(0,0,0,0.24)",
  },
  space: SHARED_SPACE,
  font: SHARED_FONT,
  leading: SHARED_LEADING,
  weight: SHARED_WEIGHT,
  z: SHARED_Z,
  container: SHARED_CONTAINER,
};

const LIGHT_TOKENS: DesignTokens = {
  radius: SHARED_RADIUS,
  shadow: {
    xs: "0 1px 2px rgba(16,24,40,0.06)",
    sm: "0 1px 3px rgba(16,24,40,0.08)",
    md: "0 4px 12px rgba(16,24,40,0.08)",
    lg: "0 10px 28px rgba(16,24,40,0.10)",
  },
  space: SHARED_SPACE,
  font: SHARED_FONT,
  leading: SHARED_LEADING,
  weight: SHARED_WEIGHT,
  z: SHARED_Z,
  container: SHARED_CONTAINER,
};

export const themes: Record<ThemeKey, ThemeMeta> = {
  "stellar-blue": {
    key: "stellar-blue",
    label: "黑金终端",
    labelEn: "Black & Amber Gold",
    isLight: false,
    siderBg: "#0c0f17",
    headerBg: "#0c0f17",
    colors: {
      pageBg: "#0c0f17",
      cardBg: "#121722",
      elevatedBg: "#1b2230",
      nestedBg: "#0e131d",
      primary: "#b45309",
      accent: "#f59e0b",
      up: "#f04438",
      down: "#12b76a",
      upBg: "rgba(240, 68, 56, 0.10)",
      downBg: "rgba(18, 183, 106, 0.10)",
      upCardGradient: "linear-gradient(135deg, rgba(240, 68, 56, 0.10), rgba(240, 68, 56, 0.02))",
      downCardGradient: "linear-gradient(135deg, rgba(18, 183, 106, 0.10), rgba(18, 183, 106, 0.02))",
      success: "#12b76a",
      warning: "#f59e0b",
      info: "#d97706",
      onPrimary: "#ffffff",
      hoverBg: "rgba(255, 255, 255, 0.045)",
      activeBg: "rgba(245, 158, 11, 0.12)",
      textPrimary: "#f9fafb",
      textSecondary: "#9ca3af",
      textMuted: "#6b7280",
      border: "#1f2633",
      headerGradient: "linear-gradient(135deg, #121722, #0c0f17)",
      logoGradient: "linear-gradient(135deg, #d97706, #fbbf24)",
      focusRing: "rgba(245, 158, 11, 0.35)",
      surfaceOverlay: "rgba(12, 15, 23, 0.96)",
      authBackground:
        "radial-gradient(circle at 14% 12%, rgba(217, 119, 6, 0.08), transparent 32%), radial-gradient(circle at 86% 82%, rgba(245, 158, 11, 0.06), transparent 28%), #0c0f17",
      authHeroGradient: "linear-gradient(145deg, rgba(18, 23, 34, 0.97), rgba(12, 15, 23, 0.92))",
      cardShadow: "0 4px 16px rgba(0, 0, 0, 0.25)",
    },
    antToken: {
      colorPrimary: "#b45309",
      colorPrimaryHover: "#d97706",
      colorPrimaryActive: "#92400e",
      colorPrimaryBg: "rgba(245, 158, 11, 0.12)",
      colorInfo: "#d97706",
      colorSuccess: "#12b76a",
      colorWarning: "#f59e0b",
      colorError: "#f04438",
      colorBgLayout: "#0c0f17",
      colorBgContainer: "#121722",
      colorBgElevated: "#1b2230",
      colorBorder: "#1f2633",
      colorBorderSecondary: "#171e2b",
      colorText: "#f9fafb",
      colorTextSecondary: "#9ca3af",
    },
    tokens: DARK_TOKENS,
  },

  "light": {
    key: "light",
    label: "暖萃米白",
    labelEn: "Warm Cream",
    isLight: true,
    siderBg: "#f7f4ee",
    headerBg: "#f7f4ee",
    colors: {
      pageBg: "#fbf9f5",
      cardBg: "#fdfcf9",
      elevatedBg: "#fdfcf9",
      nestedBg: "#f4f0e8",
      primary: "#b45309",
      accent: "#d97706",
      up: "#d92d20",
      down: "#039855",
      upBg: "rgba(217, 45, 32, 0.08)",
      downBg: "rgba(3, 152, 85, 0.08)",
      upCardGradient: "linear-gradient(135deg, rgba(217, 45, 32, 0.08), rgba(217, 45, 32, 0.02))",
      downCardGradient: "linear-gradient(135deg, rgba(3, 152, 85, 0.08), rgba(3, 152, 85, 0.02))",
      success: "#039855",
      warning: "#dc6803",
      info: "#b45309",
      onPrimary: "#ffffff",
      hoverBg: "#f0ece2",
      activeBg: "#fef3c7",
      textPrimary: "#1c1917",
      textSecondary: "#57534e",
      textMuted: "#78716c",
      border: "#e7e2d7",
      headerGradient: "linear-gradient(135deg, #f7f4ee, #fbf9f5)",
      logoGradient: "linear-gradient(135deg, #b45309, #d97706)",
      focusRing: "rgba(180, 83, 9, 0.22)",
      surfaceOverlay: "rgba(251, 249, 245, 0.98)",
      authBackground:
        "radial-gradient(circle at 14% 12%, rgba(180, 83, 9, 0.06), transparent 32%), radial-gradient(circle at 86% 82%, rgba(217, 119, 6, 0.04), transparent 28%), #fbf9f5",
      authHeroGradient: "linear-gradient(145deg, rgba(253, 252, 249, 0.98), rgba(251, 249, 245, 0.95))",
      cardShadow: "0 1px 3px rgba(44, 34, 20, 0.04), 0 4px 12px rgba(44, 34, 20, 0.03)",
    },
    antToken: {
      colorPrimary: "#b45309",
      colorPrimaryHover: "#d97706",
      colorPrimaryActive: "#92400e",
      colorPrimaryBg: "#fef3c7",
      colorInfo: "#b45309",
      colorSuccess: "#039855",
      colorWarning: "#dc6803",
      colorError: "#d92d20",
      colorBgLayout: "#fbf9f5",
      colorBgContainer: "#fdfcf9",
      colorBgElevated: "#fdfcf9",
      colorBorder: "#e7e2d7",
      colorBorderSecondary: "#efebe2",
      colorText: "#1c1917",
      colorTextSecondary: "#57534e",
    },
    tokens: LIGHT_TOKENS,
  },
};

export const THEME_LIST = Object.values(themes);
