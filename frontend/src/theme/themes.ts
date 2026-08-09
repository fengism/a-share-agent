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
}

export const themes: Record<ThemeKey, ThemeMeta> = {
  "stellar-blue": {
    key: "stellar-blue",
    label: "专业深色",
    labelEn: "Professional Dark",
    isLight: false,
    siderBg: "#0d121a",
    headerBg: "#0d121a",
    colors: {
      pageBg: "#0b0f14",
      cardBg: "#151b24",
      elevatedBg: "#1b2430",
      nestedBg: "#111821",
      primary: "#6f63d9",
      accent: "#a89af4",
      up: "#f04438",
      down: "#12b76a",
      upBg: "rgba(240,68,56,0.10)",
      downBg: "rgba(18,183,106,0.10)",
      upCardGradient: "linear-gradient(135deg, rgba(240,68,56,0.12), rgba(240,68,56,0.04))",
      downCardGradient: "linear-gradient(135deg, rgba(18,183,106,0.12), rgba(18,183,106,0.04))",
      textPrimary: "#f2f4f7",
      textSecondary: "#a7b0be",
      textMuted: "#6f7a89",
      border: "#283241",
      headerGradient: "linear-gradient(135deg, #18212d, #131a24)",
      logoGradient: "linear-gradient(135deg, #6c60db, #9b8cf2)",
      focusRing: "rgba(111,99,217,0.34)",
      surfaceOverlay: "rgba(21,27,36,0.96)",
      authBackground:
        "radial-gradient(circle at 14% 12%, rgba(111,99,217,0.12), transparent 32%), radial-gradient(circle at 86% 82%, rgba(168,154,244,0.07), transparent 28%), #0b0f14",
      authHeroGradient: "linear-gradient(145deg, rgba(24,33,45,0.96), rgba(13,18,26,0.86))",
      cardShadow: "0 12px 32px rgba(0,0,0,0.24)",
    },
    antToken: {
      colorPrimary: "#6f63d9",
      colorPrimaryHover: "#7266dd",
      colorPrimaryActive: "#6256c7",
      colorPrimaryBg: "#211e38",
      colorInfo: "#4c8dff",
      colorSuccess: "#12b76a",
      colorWarning: "#f79009",
      colorError: "#f04438",
      colorBgLayout: "#0b0f14",
      colorBgContainer: "#151b24",
      colorBgElevated: "#1b2430",
      colorBorder: "#283241",
      colorBorderSecondary: "#202a37",
      colorText: "#f2f4f7",
      colorTextSecondary: "#a7b0be",
    },
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
      elevatedBg: "#f0f3f7",
      nestedBg: "#f8fafc",
      primary: "#6658be",
      accent: "#8a79d0",
      up: "#d92d20",
      down: "#039855",
      upBg: "rgba(217,45,32,0.08)",
      downBg: "rgba(3,152,85,0.08)",
      upCardGradient: "linear-gradient(135deg, rgba(217,45,32,0.09), rgba(217,45,32,0.03))",
      downCardGradient: "linear-gradient(135deg, rgba(3,152,85,0.09), rgba(3,152,85,0.03))",
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
      colorBgElevated: "#ffffff",
      colorBorder: "#e2e8f0",
      colorBorderSecondary: "#eef1f5",
      colorText: "#182230",
      colorTextSecondary: "#475467",
    },
  },
};

export const THEME_LIST = Object.values(themes);
