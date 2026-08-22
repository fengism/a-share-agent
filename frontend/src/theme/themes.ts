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
  xs: "10px",
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
  page: "1280px",
  feed: "1180px",
  wide: "1400px",
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
    label: "专业深色",
    labelEn: "Professional Dark",
    isLight: false,
    siderBg: "#0d121a",
    headerBg: "#0d121a",
    colors: {
      pageBg: "#080c16",
      cardBg: "#101725",
      elevatedBg: "#151e2e",
      nestedBg: "#0c1320",
      primary: "#087f98",
      accent: "#20c6e5",
      up: "#ec5d52",
      down: "#3ec98f",
      upBg: "rgba(236,93,82,0.10)",
      downBg: "rgba(62,201,143,0.10)",
      upCardGradient: "linear-gradient(135deg, rgba(236,93,82,0.12), rgba(236,93,82,0.04))",
      downCardGradient: "linear-gradient(135deg, rgba(62,201,143,0.12), rgba(62,201,143,0.04))",
      success: "#3ec98f",
      warning: "#f79009",
      info: "#4c8dff",
      onPrimary: "#ffffff",
      hoverBg: "rgba(32,198,229,0.045)",
      activeBg: "rgba(32,198,229,0.10)",
      textPrimary: "#eef7fb",
      textSecondary: "#9cafbd",
      textMuted: "#627487",
      border: "#203044",
      headerGradient: "linear-gradient(135deg, #111a29, #0d1421)",
      logoGradient: "linear-gradient(135deg, #087f98, #20c6e5)",
      focusRing: "rgba(32,198,229,0.34)",
      surfaceOverlay: "rgba(12,19,32,0.97)",
      authBackground:
        "radial-gradient(circle at 14% 12%, rgba(32,198,229,0.10), transparent 32%), radial-gradient(circle at 86% 82%, rgba(8,127,152,0.08), transparent 28%), #080c16",
      authHeroGradient: "linear-gradient(145deg, rgba(16,23,37,0.97), rgba(8,12,22,0.90))",
      cardShadow: "0 12px 32px rgba(0,0,0,0.24)",
    },
    antToken: {
      colorPrimary: "#087f98",
      colorPrimaryHover: "#0b96b2",
      colorPrimaryActive: "#066b82",
      colorPrimaryBg: "#0b2632",
      colorInfo: "#4c8dff",
      colorSuccess: "#3ec98f",
      colorWarning: "#f79009",
      colorError: "#ec5d52",
      colorBgLayout: "#080c16",
      colorBgContainer: "#101725",
      colorBgElevated: "#151e2e",
      colorBorder: "#203044",
      colorBorderSecondary: "#18273a",
      colorText: "#eef7fb",
      colorTextSecondary: "#9cafbd",
    },
    tokens: DARK_TOKENS,
  },

  "light": {
    key: "light",
    label: "清爽浅色",
    labelEn: "Clean Light",
    isLight: true,
    siderBg: "#ffffff",
    headerBg: "#ffffff",
    colors: {
      pageBg: "#f5f7fa",
      cardBg: "#ffffff",
      elevatedBg: "#fbfcfd",
      nestedBg: "#f8fafc",
      primary: "#6658be",
      accent: "#8a79d0",
      up: "#d92d20",
      down: "#039855",
      upBg: "rgba(217,45,32,0.08)",
      downBg: "rgba(3,152,85,0.08)",
      upCardGradient: "linear-gradient(135deg, rgba(217,45,32,0.09), rgba(217,45,32,0.03))",
      downCardGradient: "linear-gradient(135deg, rgba(3,152,85,0.09), rgba(3,152,85,0.03))",
      success: "#039855",
      warning: "#dc6803",
      info: "#3b82f6",
      onPrimary: "#ffffff",
      hoverBg: "#f0f3f7",
      activeBg: "#e9edf3",
      textPrimary: "#182230",
      textSecondary: "#475467",
      textMuted: "#98a2b3",
      border: "#e2e8f0",
      headerGradient: "linear-gradient(135deg, #f8fafc, #f1f4f8)",
      logoGradient: "linear-gradient(135deg, #6658be, #9484d8)",
      focusRing: "rgba(102,88,190,0.22)",
      surfaceOverlay: "rgba(255,255,255,0.97)",
      authBackground:
        "radial-gradient(circle at 14% 12%, rgba(102,88,190,0.08), transparent 32%), radial-gradient(circle at 86% 82%, rgba(138,121,208,0.05), transparent 28%), #f5f7fa",
      authHeroGradient: "linear-gradient(145deg, rgba(248,250,252,0.98), rgba(240,243,247,0.92))",
      cardShadow: "0 10px 28px rgba(16,24,40,0.08)",
    },
    antToken: {
      colorPrimary: "#6658be",
      colorPrimaryHover: "#584bb0",
      colorPrimaryActive: "#4b409b",
      colorPrimaryBg: "#f0eefb",
      colorInfo: "#3b82f6",
      colorSuccess: "#039855",
      colorWarning: "#dc6803",
      colorError: "#d92d20",
      colorBgLayout: "#f5f7fa",
      colorBgContainer: "#ffffff",
      colorBgElevated: "#fbfcfd",
      colorBorder: "#e2e8f0",
      colorBorderSecondary: "#eef1f5",
      colorText: "#182230",
      colorTextSecondary: "#475467",
    },
    tokens: LIGHT_TOKENS,
  },
};

export const THEME_LIST = Object.values(themes);
